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
    consent_command = "telemetry.py" in command and "consent" in command
    if status in ("accepted", "declined"):
        root = Path(payload.get("cwd") or Path.cwd())
        try:
            from telemetry_common import validate_gate_consent
            gate_ok, gate_reason = validate_gate_consent(
                root / ".runtime" / "gate-consent.json"
            )
        except Exception:
            gate_ok, gate_reason = False, "unavailable"
        if not gate_ok:
            if consent_command and (
                    (status == "accepted" and "--accept" in command)
                    or (status == "declined" and "--decline" in command)):
                return None
            reason = (
                "iflytek-digital-human 准入凭证无效（{}）：必须先运行与当前授权一致的 "
                "telemetry.py consent --accept/--decline，使项目 .runtime/gate-consent.json "
                "由工具原子生成；凭证有效前不得实施。"
            ).format(gate_reason)
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
                "reason": reason,
            }
        return None
    selected = {"consent_accept": "--accept", "consent_decline": "--decline"}.get(state.get("phase"))
    if consent_command and state.get("phase") == "initial_avatar":
        if "--accept" in command or "--decline" in command:
            return None
    if selected and consent_command and selected in command:
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
