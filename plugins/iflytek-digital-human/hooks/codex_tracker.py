#!/usr/bin/env python3
"""Best-effort Codex hook telemetry without inventing completion."""

import json
import re
import sys
from pathlib import Path

import session_state

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_RE = re.compile(r"(?:^|[/\\])skills[/\\]([a-z0-9][a-z0-9-]*)[/\\]SKILL\.md", re.I)


def _command(payload):
    value = (payload.get("tool_input") or {}).get("cmd")
    return value if isinstance(value, str) else ""


def _tool_succeeded(payload):
    result = payload.get("tool_response")
    if isinstance(result, dict):
        code = result.get("exit_code")
        return code in (None, 0)
    return True


def _load_telemetry():
    sys.path.insert(0, str(PLUGIN_ROOT / "tools"))
    import telemetry
    import telemetry_common
    return telemetry, telemetry_common


def handle_event(payload):
    event = payload.get("hook_event_name", "")
    sid = payload.get("session_id")
    state = session_state.current(sid)
    if not state:
        return
    telemetry, common = _load_telemetry()
    if common.consent_status() != "accepted":
        if event == "SessionEnd":
            session_state.mark_avatar_session(payload, "session_end")
        elif event == "PostToolUse" and common.consent_status() == "declined":
            session_state.clear(sid)
        return
    cwd = payload.get("cwd")
    if event == "PostToolUse" and _tool_succeeded(payload):
        command = _command(payload)
        if "telemetry.py" in command and "consent" in command and "--accept" in command:
            telemetry.start_workflow(project_dir=cwd, session_id=sid)
        for skill in SKILL_RE.findall(command):
            telemetry.record_skill_invocation(skill.lower(), session_id=sid)
    elif event == "SessionEnd":
        with common.locked_state(timeout=0.5) as all_state:
            if all_state is not None:
                workflow_id = common.active_workflow_id(all_state, sid)
                item = next((row for row in all_state.get("workflows", [])
                             if row.get("workflow_id") == workflow_id), None)
                if item and item.get("status") == "in_progress":
                    item.update({
                        "status": "interrupted",
                        "ended_at": common.now_iso(),
                        "revision": int(item.get("revision") or 0) + 1,
                        "upload_status": "pending",
                        "updated_at": common.now_iso(),
                    })
        session_state.mark_avatar_session(payload, "session_end")


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(raw or "{}")
        handle_event(payload)
    except Exception:
        return


if __name__ == "__main__":
    main()
