#!/usr/bin/env python3
"""Codex PreToolUse gate for avatar work before consent and visible notice."""

import json
import re
import sys
from pathlib import Path

import session_state


def _command(payload):
    value = (payload.get("tool_input") or {}).get("cmd")
    return value if isinstance(value, str) else ""


def _is_notice_command(command):
    return "telemetry.py" in command and re.search(r"\bnotice\b", command)


def _is_capabilities_read(payload):
    tool_input = payload.get("tool_input") or {}
    path = str(tool_input.get("file_path") or tool_input.get("path") or "")
    command = _command(payload).lower().replace("\\", "/")
    return (path.replace("\\", "/").lower().endswith("docs/capabilities.md")
            or "docs/capabilities.md" in command)


def build_hook_output(payload, status_provider=None):
    session_id = payload.get("session_id") or payload.get("sessionId")
    state = session_state.current(session_id)
    if not state:
        return None
    if status_provider is None:
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / "tools"))
        from telemetry_common import consent_status
        status_provider = consent_status
    try:
        status = status_provider()
    except Exception:
        status = "unavailable"
    command = _command(payload)
    if status in ("accepted", "declined"):
        return None
    selected = {"consent_accept": "--accept", "consent_decline": "--decline"}.get(state.get("phase"))
    if selected and "telemetry.py" in command and "consent" in command and selected in command:
        return None
    if _is_notice_command(command) or _is_capabilities_read(payload):
        return None
    reason = (
        "iflytek-digital-human 授权硬门禁：当前统计授权尚未明确。"
        "先在助手正文展示完整 docs/capabilities.md 和 telemetry.py notice，"
        "再等待用户明确选择同意或不同意；未完成前不得扫描工程、实施业务或调用下游 Skill。"
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
        "reason": reason,
    }


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        output = build_hook_output(json.loads(raw or "{}"))
        if output:
            print(json.dumps(output))
    except Exception:
        return


if __name__ == "__main__":
    main()
