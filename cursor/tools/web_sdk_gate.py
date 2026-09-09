#!/usr/bin/env python3
"""Static and runtime delivery gate for Web avatar SDK projects."""

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket_auth


ENV_ALIASES = {
    "app_id": ("APP_ID", "XF_APP_ID"),
    "api_key": ("API_KEY", "XF_API_KEY"),
    "api_secret": ("API_SECRET", "XF_API_SECRET"),
    "scene_id": ("SCENE_ID", "XF_SCENE_ID"),
    "avatar_id": ("AVATAR_ID", "XF_AVATAR_ID"),
    "vcn": ("VCN", "XF_VCN"),
    "ws_url": ("WS_URL", "XF_WS_URL"),
}
MIN_LENGTH = {
    "app_id": 8,
    "api_key": 12,
    "api_secret": 24,
    "scene_id": 8,
    "avatar_id": 3,
    "vcn": 3,
    "ws_url": 12,
}
HALLUCINATED_APIS = ("setServerUrl", "getPlayer")
REQUIRED_SDK_METHODS = ("setApiInfo", "setGlobalParams", "start", "writeText")
AUTH_FAILURE_CODES = (1008, 10110, 10113, 10114, 10120, 10121, 11203)
AUTH_FAILURE_TEXT = ("avatar authentication failed", "authorization invalid")
AUTH_FAILURE_CODES = (1008, 10110, 10113, 10114, 10120, 10121, 11203)
AUTH_FAILURE_TEXT = ("avatar authentication failed", "authorization invalid")


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _has_authentication_failure(evidence):
    candidates = [evidence.get("errors"), evidence.get("close_code"),
                  evidence.get("close_reason"), evidence.get("error_code")]
    value = json.dumps(candidates, ensure_ascii=False, default=str).lower()
    if any(marker in value for marker in AUTH_FAILURE_TEXT):
        return True
    return any(re.search(r"(?<!\d){}(?!\d)".format(code), value)
                   for code in AUTH_FAILURE_CODES)


def _logical_env(values, logical_name):
    for alias in ENV_ALIASES[logical_name]:
        if values.get(alias):
            return values[alias]
    return None


def _credential_fingerprint(values):
    fields = (_logical_env(values, "app_id"), _logical_env(values, "api_key"),
              _logical_env(values, "api_secret"), _logical_env(values, "scene_id"),
              _logical_env(values, "ws_url"))
    if not all(fields):
        return None
    return hashlib.sha256("\0".join(fields).encode("utf-8")).hexdigest()


def _has_authentication_failure(evidence):
    """Recognize auth rejection in the current browser evidence only."""
    candidates = [evidence.get("errors"), evidence.get("close_code"),
                  evidence.get("close_reason"), evidence.get("error_code")]
    text = json.dumps(candidates, ensure_ascii=False, default=str).lower()
    if any(marker in text for marker in AUTH_FAILURE_TEXT):
        return True
    return any(re.search(r"(?<!\d){}(?!\d)".format(code), text)
               for code in AUTH_FAILURE_CODES)


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


def _credential_issues(project):
    values = _read_env(project)
    issues = []
    for logical_name, aliases in ENV_ALIASES.items():
        value = next((values[name] for name in aliases if values.get(name)), None)
        if value is None:
            issues.append("credential_missing:" + logical_name)
            continue
        if len(value) < MIN_LENGTH[logical_name] or "*" in value:
            issues.append("credential_invalid:" + logical_name)
    return issues


def _sdk_issues(project):
    manifest_path = project / ".runtime" / "sdk-artifact.json"
    manifest = _read_json(manifest_path)
    if not manifest or manifest.get("artifact_status") != "ready":
        return ["sdk_manifest_missing_or_blocked"], None
    entry_value = manifest.get("entry")
    if not entry_value:
        return ["sdk_entry_missing"], None
    entry = (project / entry_value).resolve()
    try:
        entry.relative_to(project.resolve())
    except ValueError:
        return ["sdk_entry_outside_project"], None
    if not entry.is_file() or _sha256(entry) != manifest.get("sha256"):
        return ["sdk_entry_hash_mismatch"], None
    types = entry.with_suffix(".d.ts")
    if not types.is_file():
        return ["sdk_types_missing"], None
    declaration = types.read_text(encoding="utf-8", errors="ignore")
    issues = []
    if not re.search(r"\bas\s+default\b", declaration):
        issues.append("sdk_default_export_missing")
    for method in REQUIRED_SDK_METHODS:
        if not re.search(r"\b" + re.escape(method) + r"\s*\(", declaration):
            issues.append("sdk_method_missing:" + method)
    return issues, entry


def _project_sources(project):
    texts = []
    ignored = {"sdk", "node_modules", ".runtime", ".git"}
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".js", ".mjs", ".ts"}:
            continue
        if any(part in ignored for part in path.relative_to(project).parts):
            continue
        texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(texts)


def _source_issues(project):
    text = _project_sources(project)
    issues = []
    for name in HALLUCINATED_APIS:
        if re.search(r"\." + re.escape(name) + r"\s*\(", text):
            issues.append("hallucinated_api:" + name)
    required = {
        "sdk_default_import_missing": r"\bmodule\s*\.\s*default\b",
        "setApiInfo_call_missing": r"\.setApiInfo\s*\(",
        "setGlobalParams_call_missing": r"\.setGlobalParams\s*\(",
        "sdk_start_call_missing": r"\.start\s*\(",
        "connected_listener_missing": r"SDKEvents\s*\.\s*connected",
        "stream_start_listener_missing": r"SDKEvents\s*\.\s*stream_start",
        "avatar_stream_missing": r"avatar\s*:\s*\{[\s\S]{0,2000}?stream\s*:",
    }
    for issue, pattern in required.items():
        if not re.search(pattern, text):
            issues.append(issue)
    return issues


def _server_issues(project, node_check):
    server = project / "server.js"
    if not server.is_file():
        return ["server_js_missing"]
    issues = websocket_auth.server_usage_issues(project)
    ok, reason = node_check(server)
    if not ok:
        issues.append("server_syntax_failed" + ((":" + reason) if reason else ""))
    return issues


def _default_node_check(server):
    try:
        result = subprocess.run(
            ["node", "--check", str(server)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, exc.__class__.__name__
    return result.returncode == 0, None if result.returncode == 0 else "invalid_js"


def _default_server_smoke(project):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = os.environ.copy()
    env["PORT"] = str(port)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            ["node", "server.js"],
            cwd=str(project),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            creationflags=creationflags,
        )
    except OSError as exc:
        return False, ["server_start_failed:" + exc.__class__.__name__]

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = "http://127.0.0.1:{}".format(port)
    try:
        deadline = time.time() + 8
        while time.time() < deadline:
            if process.poll() is not None:
                return False, ["server_start_failed"]
            try:
                with opener.open(base + "/api/config", timeout=1) as response:
                    config = json.loads(response.read().decode("utf-8"))
                break
            except Exception:
                time.sleep(0.1)
        else:
            return False, ["server_start_timeout"]

        required_config = ("appId", "sceneId", "avatarId", "vcn", "wsUrl")
        if not all(config.get(name) for name in required_config):
            return False, ["config_endpoint_failed"]
        try:
            with opener.open(base + "/api/avatar-auth", timeout=2) as response:
                auth = json.loads(response.read().decode("utf-8"))
        except Exception:
            return False, ["auth_endpoint_failed"]
        if not auth.get("signedUrl"):
            return False, ["auth_endpoint_failed"]
        return True, []
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def _runtime_issues(project, required_interaction, latest_static_mtime):
    evidence_path = project / ".runtime" / "web-runtime-evidence.json"
    evidence = _read_json(evidence_path)
    if not evidence:
        return ["connected", "stream_start", "first_frame", required_interaction]
    issues = []
    # Authentication rejection takes precedence over later-looking success flags.
    if _has_authentication_failure(evidence):
        issues.append("authentication_failed")
    state = _read_json(project / ".runtime" / "web-delivery.json") or {}
    if _has_authentication_failure(evidence):
        issues.append("authentication_failed")
    if evidence.get("source") != "playwright":
        issues.append("runtime_evidence_source")
    if state.get("prepared_at_epoch") and evidence.get("prepared_at_epoch") != state.get("prepared_at_epoch"):
        issues.append("runtime_evidence_prepared_at_mismatch")
    if state.get("url") and evidence.get("url") != state.get("url"):
        issues.append("runtime_evidence_url_mismatch")
    expected_fingerprint = state.get("credential_fingerprint")
    if expected_fingerprint and evidence.get("credential_fingerprint") != expected_fingerprint:
        issues.append("runtime_evidence_credential_mismatch")
    try:
        if evidence_path.stat().st_mtime < latest_static_mtime:
            issues.append("runtime_evidence_stale")
    except OSError:
        issues.append("runtime_evidence_missing")
    for name in ("connected", "stream_start", "first_frame"):
        if evidence.get(name) is not True:
            issues.append(name)
    if (evidence.get("target_interaction") != required_interaction
            or evidence.get("target_interaction_passed") is not True):
        issues.append(required_interaction)
    errors = evidence.get("errors") or []
    if not isinstance(errors, list):
        errors = [errors]
    core_succeeded = (
        evidence.get("connected") is True
        and evidence.get("stream_start") is True
        and evidence.get("first_frame") is True
        and evidence.get("target_interaction") == required_interaction
        and evidence.get("target_interaction_passed") is True
    )
    blocking_errors = [
        error for error in errors
        if not (core_succeeded and _is_generic_resource_404(error))
    ]
    if blocking_errors:
        issues.append("runtime_errors")
    return issues


def _is_generic_resource_404(error):
    if not isinstance(error, str):
        return False
    value = error.lower()
    return "failed to load resource" in value and "404" in value


def run_checks(project, required_interaction="text", node_check=None,
               server_smoke=None):
    project = Path(project).resolve()
    node_check = node_check or _default_node_check
    server_smoke = server_smoke or _default_server_smoke
    static_issues = []
    sdk_issues, _entry = _sdk_issues(project)
    static_issues.extend(sdk_issues)
    static_issues.extend(_credential_issues(project))
    static_issues.extend(_source_issues(project))
    static_issues.extend(_server_issues(project, node_check))
    smoke_ok, smoke_issues = server_smoke(project)
    if not smoke_ok:
        static_issues.extend(smoke_issues)
    static_issues = list(dict.fromkeys(static_issues))

    static_files = [
        path
        for path in (project / ".runtime" / "sdk-artifact.json",
                     project / ".env", project / ".env.local",
                     project / "server.js", project / "public" / "app.js")
        if path.is_file()
    ]
    latest_static_mtime = max((path.stat().st_mtime for path in static_files), default=0)
    runtime_issues = _runtime_issues(
        project, required_interaction, latest_static_mtime
    )

    if static_issues:
        status = "failed"
    elif runtime_issues:
        status = "needs_runtime_verification"
    else:
        status = "ready_to_deliver"
    remaining = static_issues + runtime_issues
    result = {
        "status": status,
        "ready_to_deliver": status == "ready_to_deliver",
        "static_issues": static_issues,
        "runtime_issues": runtime_issues,
        "remaining_issues": remaining,
    }
    marker = {
        "status": status,
        "ready_to_deliver": result["ready_to_deliver"],
        "issues_found": len(remaining),
        "issues_fixed": 0,
        "remaining_issues": remaining,
        "gate": "web_sdk_gate",
    }
    _write_json_atomic(project / ".runtime" / "verification-result.json", marker)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check")
    check.add_argument("--project", required=True)
    check.add_argument("--interaction", default="text")
    args = parser.parse_args(argv)
    if args.command != "check":
        parser.error("command required")
    result = run_checks(args.project, args.interaction)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "ready_to_deliver":
        return 0
    return 3 if result["status"] == "needs_runtime_verification" else 2


if __name__ == "__main__":
    sys.exit(main())
