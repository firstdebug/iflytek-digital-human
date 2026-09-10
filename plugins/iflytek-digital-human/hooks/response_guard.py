#!/usr/bin/env python3
"""Codex Stop hook: enforce visible consent disclosure and safe responses."""

import json
import re
import sys
from pathlib import Path

from avatar_intent import is_avatar_related
import session_state

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _consent_phase(prompt):
    normalized = re.sub(r"[\s，。！？,.!?]+", "", prompt or "").lower()
    if re.fullmatch(r"(?:我)?不同意(?:使用)?统计(?:授权)?|拒绝", normalized):
        return "consent_decline"
    if re.fullmatch(r"(?:我)?同意(?:使用)?统计(?:授权)?|同意|接受|ok|okay|好的?", normalized):
        return "consent_accept"
    return "initial_avatar"


def render_privacy_notice():
    sys.path.insert(0, str(PLUGIN_ROOT / "tools"))
    from telemetry import render_privacy_notice as render
    return render()


def _content_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        item.get("text", "") for item in content
        if isinstance(item, dict) and item.get("text")
    )


def latest_exchange(transcript_path):
    prompt = response = ""
    if not transcript_path:
        return prompt, response
    try:
        rows = Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return prompt, response
    for raw in rows:
        try:
            record = json.loads(raw)
        except Exception:
            continue
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict) or payload.get("type") != "message":
            continue
        text = _content_text(payload.get("content"))
        if payload.get("role") == "user" and text:
            prompt, response = text, ""
        elif payload.get("role") == "assistant" and prompt and text:
            response = text
    return prompt, response


def _needs_visible_consent(status, response):
    if status not in ("undecided", "stale", "unavailable"):
        return False
    capabilities = (PLUGIN_ROOT / "docs" / "capabilities.md").read_text(encoding="utf-8").strip()
    notice = render_privacy_notice().strip()
    choices = ("同意使用统计" in response and "不同意使用统计" in response)
    return not (capabilities in response and notice in response and choices)


def build_stop_output(payload, status_provider=None, session_active_provider=None):
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return None
    prompt = payload.get("prompt") or ""
    response = payload.get("last_assistant_message") or ""
    if (not prompt or not response) and payload.get("transcript_path"):
        prompt, response = latest_exchange(payload.get("transcript_path"))
    session_id = payload.get("session_id") or payload.get("sessionId")
    if session_active_provider is None:
        session_active_provider = lambda sid: bool(session_state.current(sid))
    active = session_active_provider(session_id)
    related = is_avatar_related(prompt)
    consent_followup = bool(active) and _consent_phase(prompt) in (
        "consent_accept", "consent_decline"
    )
    # A prior avatar request in the same Codex session must not make an
    # unrelated backend/NLP response subject to the avatar consent gate.
    if not prompt or not response or (not related and not consent_followup):
        return None
    if status_provider is None:
        sys.path.insert(0, str(PLUGIN_ROOT / "tools"))
        from telemetry_common import consent_status
        status_provider = consent_status
    try:
        status = status_provider()
    except Exception:
        status = "unavailable"
    if status not in ("undecided", "stale", "unavailable"):
        return None
    phase = session_state.current(session_id).get("phase") if active else ""
    if phase in ("consent_accept", "consent_decline"):
        flag = "--accept" if phase == "consent_accept" else "--decline"
        reason = (
            "iflytek-digital-human 授权选择尚未落盘：用户已经明确选择，"
            "请先运行 telemetry.py consent {}，再继续原虚拟人请求。"
        ).format(flag)
        return {"decision": "block", "reason": reason, "systemMessage": reason}
    if not _needs_visible_consent(status, response):
        return None
    reason = (
        "iflytek-digital-human 最终回答门禁未通过：必须在助手对话正文完整展示"
        "完整能力清单 docs/capabilities.md 和 telemetry.py notice，并同时给出‘同意使用统计’与"
        "‘不同意使用统计’两个明确选项；工具 stdout、隐藏上下文或文件路径不算展示。"
    )
    return {"decision": "block", "reason": reason, "systemMessage": reason}


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        output = build_stop_output(json.loads(raw or "{}"))
        if output:
            print(json.dumps(output))
    except Exception:
        return


if __name__ == "__main__":
    main()
