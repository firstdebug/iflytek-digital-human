#!/usr/bin/env python3
"""Codex UserPromptSubmit hook for high-confidence avatar routing."""

import json
import re
import sys
from pathlib import Path

from avatar_intent import is_avatar_related
import session_state

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _prompt(payload):
    return payload.get("prompt") or payload.get("user_prompt") or ""


def _consent_phase(prompt):
    normalized = re.sub(r"[\s，。！？,.!?]+", "", prompt).lower()
    if re.fullmatch(r"(?:我)?不同意(?:使用)?统计(?:授权)?|拒绝", normalized):
        return "consent_decline"
    if re.fullmatch(r"(?:我)?同意(?:使用)?统计(?:授权)?|同意|接受|ok|okay|好的?", normalized):
        return "consent_accept"
    return "initial_avatar"


def build_hook_output(payload, status_provider=None):
    prompt = _prompt(payload)
    if not is_avatar_related(prompt):
        return None
    phase = _consent_phase(prompt)
    session_state.mark_avatar_session(payload, phase)
    if status_provider is None:
        sys.path.insert(0, str(PLUGIN_ROOT / "tools"))
        from telemetry_common import consent_status
        status_provider = consent_status
    try:
        status = status_provider()
    except Exception:
        status = "unavailable"
    if status == "accepted":
        try:
            sys.path.insert(0, str(PLUGIN_ROOT / "tools"))
            from telemetry import start_workflow
            start_workflow(project_dir=payload.get("cwd"),
                           session_id=payload.get("session_id"))
        except Exception:
            pass
    routing = (
        "[iflytek-digital-human 路由提示] 本次请求涉及讯飞虚拟人/数字人。"
        "必须先使用 avatar-workflow-entry，再分发到对应子技能。"
    )
    if phase in ("consent_accept", "consent_decline"):
        consent = (
            "请只运行 telemetry.py consent --accept 或 --decline 对应的明确选择，"
            "然后重新读取 avatar-workflow-entry 继续原请求。"
        )
    elif status in ("undecided", "stale", "unavailable") and phase == "initial_avatar":
        consent = (
            "在业务路由前，必须完整读取并把完整能力清单（docs/capabilities.md）与"
            " telemetry.py notice 的完整内容"
            "放入助手对话正文；工具输出、隐藏上下文、日志或仅给文件路径都不算展示。"
            "随后只询问‘同意使用统计’或‘不同意使用统计’，等待明确选择。"
        )
    elif status == "accepted":
        consent = "统计已获明确同意；不要重复展示授权声明或询问授权。"
    elif status == "declined":
        consent = "统计已被拒绝；保持统计关闭，不要重复询问授权。"
    else:
        consent = "授权状态不可用；先回退到 telemetry.py consent --status。"
    context = routing + "\n" + consent
    return {
        "systemMessage": context,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        },
    }


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(raw or "{}")
        output = build_hook_output(payload)
        if output:
            print(json.dumps(output))
    except Exception:
        return


if __name__ == "__main__":
    main()
