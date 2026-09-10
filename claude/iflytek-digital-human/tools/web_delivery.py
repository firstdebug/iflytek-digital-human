#!/usr/bin/env python3
"""Deterministic Web SDK delivery state machine.

The command owns credential preparation, one project-scoped Node process,
the selected port, runtime verification, and telemetry completion ordering.
"""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path

import sdk_artifact
import telemetry
import web_sdk_gate
import websocket_auth
import write_env_safe


STATE_VERSION = 1
STATE_NAME = "web-delivery.json"
SERVER_NAME = "web-server.json"
STATIC_FILES = (
    ".env",
    ".env.local",
    "server.js",
    "xfyun-auth.mjs",
    "package.json",
    "public/app.js",
    ".runtime/sdk-artifact.json",
    ".runtime/websocket-auth.json",
)
WEB_PROFILE_KEYS = (
    "APP_ID",
    "API_KEY",
    "API_SECRET",
    "SCENE_ID",
    "AVATAR_ID",
    "VCN",
    "WS_URL",
)


def _write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _runtime_dir(project):
    return project / ".runtime"


def _state_path(project):
    return _runtime_dir(project) / STATE_NAME


def _server_path(project):
    return _runtime_dir(project) / SERVER_NAME


def _load_state(project):
    state = _read_json(_state_path(project)) or {}
    if state.get("schema_version") != STATE_VERSION:
        return {}
    return state


def _save_state(project, state):
    state = dict(state)
    state["schema_version"] = STATE_VERSION
    state["project"] = str(project)
    state["updated_at_epoch"] = time.time()
    _write_json_atomic(_state_path(project), state)
    return state


def _write_verification_marker(project, status, issues, next_action=None):
    payload = {
        "status": status,
        "ready_to_deliver": False,
        "issues_found": len(issues),
        "issues_fixed": 0,
        "remaining_issues": list(issues),
        "gate": "web_delivery",
    }
    if next_action:
        payload["next_action"] = next_action
    _write_json_atomic(
        _runtime_dir(project) / "verification-result.json",
        payload,
    )


def _read_env(project):
    values = {}
    for name in (".env", ".env.local"):
        path = project / name
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _logical_env(values, logical_name):
    for alias in web_sdk_gate.ENV_ALIASES[logical_name]:
        if values.get(alias):
            return values[alias]
    return None


def _credential_issues(project):
    values = _read_env(project)
    has_logical_credentials = all(
        _logical_env(values, name)
        for name in ("app_id", "api_key", "api_secret", "scene_id")
    )
    if has_logical_credentials and not all(values.get(name) for name in WEB_PROFILE_KEYS):
        return ["credential_profile_mismatch:web-sdk"]
    issues = websocket_auth.credential_issues(values)
    generic_issues = web_sdk_gate._credential_issues(project)
    for issue in generic_issues:
        if issue not in issues:
            issues.append(issue)
    if not issues and not all(values.get(name) for name in WEB_PROFILE_KEYS):
        issues.append("credential_profile_mismatch:web-sdk")
    return issues


def _credential_fingerprint(values):
    fields = (
        _logical_env(values, "app_id"),
        _logical_env(values, "api_key"),
        _logical_env(values, "api_secret"),
        _logical_env(values, "scene_id"),
        _logical_env(values, "ws_url"),
    )
    if not all(fields):
        return None
    return hashlib.sha256("\0".join(fields).encode("utf-8")).hexdigest()


def _port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", int(port)))
            return True
        except OSError:
            return False


def _choose_initial_port(requested=None):
    start = int(requested) if requested is not None else 3000
    # An explicit port is a contract, not a hint constrained to the default
    # 3000-3100 window.  Keep the fallback scan for automatic allocation, but
    # allow any valid requested TCP port and only probe the requested value.
    if requested is not None:
        if 1 <= start <= 65535 and _port_is_free(start):
            return start
        raise RuntimeError("no_free_port")
    for port in range(start, 3101):
        if _port_is_free(port):
            return port
    raise RuntimeError("no_free_port")


def _pid_alive(pid):
    """Return whether pid is a live process on the current OS.

    Windows' ``os.kill(pid, 0)`` is not a process probe: for some valid or
    stale PIDs it raises WinError 87/SystemError. Query the process exit code
    through Win32 instead so state files work across shells.
    """
    try:
        value = int(pid)
        if value <= 0:
            return False
        if os.name == "nt":
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, value
            )
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        os.kill(value, 0)
        return True
    except (OSError, TypeError, ValueError, SystemError, AttributeError):
        return False


def _managed_process_alive(project, server_state):
    if not server_state or server_state.get("project") != str(project):
        return False
    return _pid_alive(server_state.get("pid"))


def _start_server(project, port, credential_fingerprint):
    runtime = _runtime_dir(project)
    runtime.mkdir(parents=True, exist_ok=True)
    stdout = (runtime / "web-server.log").open("ab")
    stderr = (runtime / "web-server.err.log").open("ab")
    env = os.environ.copy()
    env["PORT"] = str(port)
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            ["node", "server.js"],
            cwd=str(project),
            env=env,
            stdout=stdout,
            stderr=stderr,
            creationflags=flags,
            start_new_session=os.name != "nt",
        )
    finally:
        stdout.close()
        stderr.close()
    state = {
        "schema_version": STATE_VERSION,
        "project": str(project),
        "pid": process.pid,
        "port": int(port),
        "started_at_epoch": time.time(),
        "credential_fingerprint": credential_fingerprint,
        "command": ["node", "server.js"],
    }
    _write_json_atomic(_server_path(project), state)
    return state


def _fetch_json(url, timeout=2):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _server_health(project, server_state, timeout=10):
    if not _managed_process_alive(project, server_state):
        return False, ["managed_server_not_running"]
    port = int(server_state["port"])
    base = "http://127.0.0.1:{}".format(port)
    deadline = time.time() + timeout
    last_issue = "server_start_timeout"
    while time.time() < deadline:
        if not _pid_alive(server_state.get("pid")):
            return False, ["managed_server_exited"]
        try:
            config = _fetch_json(base + "/api/config")
            auth = _fetch_json(base + "/api/avatar-auth")
            values = _read_env(project)
            expected = {
                "appId": _logical_env(values, "app_id"),
                "sceneId": _logical_env(values, "scene_id"),
                "avatarId": _logical_env(values, "avatar_id"),
                "vcn": _logical_env(values, "vcn"),
                "wsUrl": _logical_env(values, "ws_url"),
            }
            missing = [name for name, value in expected.items() if not value]
            if missing:
                return False, ["credential_missing:" + name for name in missing]
            mismatched = [
                name for name, value in expected.items() if config.get(name) != value
            ]
            if mismatched:
                return False, ["config_mismatch:" + name for name in mismatched]
            if not auth.get("signedUrl"):
                return False, ["auth_endpoint_failed"]
            auth_issues = websocket_auth.signed_url_issues(
                auth["signedUrl"], values
            )
            if auth_issues:
                return False, auth_issues
            return True, []
        except Exception as exc:
            last_issue = "server_unavailable:" + exc.__class__.__name__
            time.sleep(0.15)
    return False, [last_issue]


def _project_changed_since(project, since_epoch):
    for relative in STATIC_FILES:
        path = project / relative
        if path.is_file() and path.stat().st_mtime > since_epoch:
            return True
    return False


def _runtime_evidence_is_fresh(project, prepared_at, url, credential_fingerprint, interaction):
    path = _runtime_dir(project) / "web-runtime-evidence.json"
    evidence = _read_json(path)
    if not evidence:
        return False
    if evidence.get("source") not in ("playwright", "browser"):
        return False
    if evidence.get("prepared_at_epoch") != prepared_at:
        return False
    if evidence.get("credential_fingerprint") != credential_fingerprint:
        return False
    if evidence.get("url") != url:
        return False
    if evidence.get("target_interaction") != interaction:
        return False
    return all(evidence.get(name) is True for name in (
        "connected", "stream_start", "first_frame", "target_interaction_passed"
    ))


def _runtime_verification_action(project, url, interaction):
    tools_dir = Path(__file__).resolve().parent
    python = str(Path(sys.executable).resolve())
    project = Path(project).resolve()
    return {
        "action": "run_web_runtime_evidence",
        "required": True,
        "commands": [
            ('"{}" "{}" --project "{}" --url "{}" --interaction "{}"'
             .format(python, tools_dir / "web_runtime_evidence.py", project,
                     url, interaction)),
            ('"{}" "{}" run --project "{}" --interaction "{}"'
             .format(python, Path(__file__).resolve(), project, interaction)),
        ],
        "rules": [
            "do not hand-write .runtime/web-runtime-evidence.json",
            "the evidence script must click the page and collect browser state",
            "run the same web_delivery command only after evidence collection succeeds",
        ],
    }


def _next_action(project, status):
    if status != "blocked_missing_credentials":
        return None
    tools_dir = Path(__file__).resolve().parent
    python = str(Path(sys.executable).resolve())
    return {
        "action": "run_avatar_credentials",
        "required": True,
        "commands": [
            '"{}" "{}" login'.format(python, tools_dir / "xfyun_common.py"),
            '"{}" "{}"'.format(python, tools_dir / "xfyun_query_services.py"),
            (
                '"{}" "{}" run --project "{}" --app-id <appId> '
                '--scene-id <sceneId> --interaction <text|voice|audio>'
            ).format(python, Path(__file__).resolve(), Path(project).resolve()),
        ],
        "rules": [
            "execute commands instead of asking the user to provide WS_URL",
            "use only appId and sceneId returned by the platform query",
            "do not invent or manually compose console or WebSocket URLs",
        ],
    }


def _blocked(project, status, issues, state=None):
    state = dict(state or {})
    state.update({"phase": status, "ready_to_deliver": False, "issues": issues})
    _save_state(project, state)
    _write_verification_marker(project, status, issues)
    reported, report_reason = telemetry.report_gate(
        "web_delivery", status, issues, project_dir=Path(project).resolve()
    )
    payload = {
        "status": status,
        "issues": issues,
        "telemetry": "reported" if reported else "skipped:" + str(report_reason),
    }
    next_action = _next_action(project, status)
    if next_action:
        payload["next_action"] = next_action
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2


def prepare(project, app_id=None, scene_id=None, interaction="text", port=None,
            refresh_credentials=False, open_browser=True):
    project = Path(project).resolve()
    if not (project / "server.js").is_file():
        return _blocked(project, "blocked_server_lifecycle", ["server_js_missing"])

    state = _load_state(project)
    env_path = project / ".env"
    credential_issues = _credential_issues(project)
    if credential_issues or refresh_credentials:
        if not app_id or not scene_id:
            return _blocked(
                project,
                "blocked_missing_credentials",
                credential_issues + ["app_id_and_scene_id_required"],
                state,
            )
        if not write_env_safe.write_env(
            app_id, scene_id, env_path, profile="web-sdk"
        ):
            return _blocked(
                project, "blocked_missing_credentials", ["platform_fetch_failed"], state
            )

    credential_issues = _credential_issues(project)
    if credential_issues:
        return _blocked(project, "blocked_missing_credentials", credential_issues, state)

    websocket_auth.install(project)
    server_usage_issues = websocket_auth.server_usage_issues(project)
    if server_usage_issues:
        return _blocked(
            project, "blocked_server_lifecycle", server_usage_issues, state
        )
    artifact = sdk_artifact.ensure_artifact("web", project)
    if artifact.get("artifact_status") != "ready":
        return _blocked(
            project,
            "blocked_missing_sdk",
            [artifact.get("reason") or "sdk_not_ready"],
            state,
        )

    server_state = _read_json(_server_path(project)) or {}
    previous_port = server_state.get("port")
    values = _read_env(project)
    fingerprint = _credential_fingerprint(values)
    server_reusable = (
        _managed_process_alive(project, server_state)
        and server_state.get("credential_fingerprint") == fingerprint
        and (port is None or int(server_state.get("port", -1)) == int(port))
    )
    if server_reusable:
        selected_port = int(server_state["port"])
    else:
        try:
            selected_port = _choose_initial_port(port or previous_port)
        except RuntimeError as exc:
            return _blocked(project, "blocked_server_lifecycle", [str(exc)], state)
    if not server_reusable:
        try:
            server_state = _start_server(project, selected_port, fingerprint)
        except OSError as exc:
            return _blocked(
                project,
                "blocked_server_lifecycle",
                ["server_start_failed:" + exc.__class__.__name__],
                state,
            )

    healthy, issues = _server_health(project, server_state)
    if not healthy:
        return _blocked(project, "blocked_server_lifecycle", issues, state)

    prepared_at = time.time()
    url = "http://127.0.0.1:{}".format(selected_port)
    state.update(
        {
            "phase": "awaiting_runtime_verification",
            "ready_to_deliver": False,
            "interaction": interaction,
            "port": selected_port,
            "pid": server_state.get("pid"),
            "prepared_at_epoch": prepared_at,
            "credential_fingerprint": fingerprint,
            "url": url,
            "issues": ["connected", "stream_start", "first_frame", interaction],
        }
    )
    _save_state(project, state)
    _write_verification_marker(
        project,
        "needs_runtime_verification",
        ["connected", "stream_start", "first_frame", interaction],
        next_action=_runtime_verification_action(project, url, interaction),
    )
    reported, report_reason = telemetry.report_gate(
        "web_delivery",
        "awaiting_runtime_verification",
        ["connected", "stream_start", "first_frame", interaction],
        project_dir=project,
    )
    if open_browser:
        webbrowser.open(url)
    print(
        json.dumps(
            {
                "status": "awaiting_runtime_verification",
                "port": selected_port,
                "url": url,
                "next": "run web_runtime_evidence.py, then run the same web_delivery command",
                "next_action": _runtime_verification_action(project, url, interaction),
                "telemetry": "reported" if reported else "skipped:" + str(report_reason),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 3


def finish(project, interaction="text"):
    project = Path(project).resolve()
    state = _load_state(project)
    server_state = _read_json(_server_path(project)) or {}
    healthy, issues = _server_health(project, server_state, timeout=2)
    if not healthy:
        return _blocked(project, "blocked_server_lifecycle", issues, state)
    result = web_sdk_gate.run_checks(project, interaction)
    state.update(
        {
            "phase": result["status"],
            "ready_to_deliver": result["ready_to_deliver"],
            "issues": result["remaining_issues"],
        }
    )
    if not result["ready_to_deliver"]:
        _save_state(project, state)
        telemetry.report_gate(
            "web_delivery",
            result["status"],
            result["remaining_issues"],
            project_dir=project,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result["status"] == "needs_runtime_verification" else 2

    completed, reason = telemetry.report_complete(
        workflow_type="sdk_integration", project_dir=project
    )
    state["telemetry"] = "completed" if completed else "skipped:" + str(reason)
    _save_state(project, state)
    print(
        json.dumps(
            {
                "status": "ready_to_deliver",
                "ready_to_deliver": True,
                "telemetry": state["telemetry"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run(project, app_id=None, scene_id=None, interaction="text", port=None,
        refresh_credentials=False, open_browser=True):
    project = Path(project).resolve()
    state = _load_state(project)
    prepared_at = state.get("prepared_at_epoch", 0)
    if (
        state.get("phase") == "awaiting_runtime_verification"
        and prepared_at
        and not _project_changed_since(project, prepared_at)
    ):
        server_state = _read_json(_server_path(project)) or {}
        healthy, health_issues = _server_health(project, server_state, timeout=2)
        if not healthy:
            return prepare(
                project,
                app_id=app_id,
                scene_id=scene_id,
                interaction=interaction,
                port=port,
                refresh_credentials=False,
                open_browser=open_browser,
            )
        if _runtime_evidence_is_fresh(
            project,
            prepared_at,
            state.get("url"),
            state.get("credential_fingerprint"),
            state.get("interaction", interaction),
        ):
            return finish(project, interaction)
        print(
            json.dumps(
                {
                    "status": "awaiting_runtime_verification",
                    "port": state.get("port"),
                    "url": state.get("url"),
                    "issues": state.get("issues", []),
                    "next_action": _runtime_verification_action(
                        project, state.get("url"), state.get("interaction", interaction)
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 3
    if state.get("phase") == "ready_to_deliver" and not _project_changed_since(
        project, state.get("updated_at_epoch", 0)
    ):
        print(json.dumps({"status": "ready_to_deliver"}, indent=2))
        return 0
    return prepare(
        project,
        app_id=app_id,
        scene_id=scene_id,
        interaction=interaction,
        port=port,
        refresh_credentials=refresh_credentials,
        open_browser=open_browser,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    command = sub.add_parser("run")
    command.add_argument("--project", required=True)
    command.add_argument("--app-id")
    command.add_argument("--scene-id")
    command.add_argument("--interaction", choices=("text", "voice", "audio"), default="text")
    command.add_argument("--port", type=int)
    command.add_argument("--refresh-credentials", action="store_true")
    command.add_argument("--no-browser", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--project", required=True)
    args = parser.parse_args(argv)
    cmd = args.command
    if cmd == "run":
        return run(
            args.project,
            app_id=args.app_id,
            scene_id=args.scene_id,
            interaction=args.interaction,
            port=args.port,
            refresh_credentials=args.refresh_credentials,
            open_browser=not args.no_browser,
        )
    if cmd == "status":
        project = Path(args.project).resolve()
        print(json.dumps(_load_state(project), ensure_ascii=False, indent=2))
        return 0
    parser.error("command required")


if __name__ == "__main__":
    sys.exit(main())
