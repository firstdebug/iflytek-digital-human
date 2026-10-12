#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inject avatar routing and the local consent state on UserPromptSubmit."""

import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
from platform_endpoints import CANONICAL_WS_URL, PROJECTS_URL  # noqa: E402
from avatar_intent import has_explicit_avatar_command  # noqa: E402


VALID_CONSENT_STATES = {"accepted", "declined", "undecided", "stale"}


def _visible_consent_material():
    """Load the disclosure before any consent-gated tool call is needed."""
    capabilities = (Path(__file__).resolve().parent.parent / "docs" /
                    "capabilities.md").read_text(encoding="utf-8").strip()
    from telemetry import render_privacy_notice
    return capabilities, render_privacy_notice().strip()


def _prompt_from(payload):
    if not isinstance(payload, dict):
        return ""
    return payload.get("prompt") or payload.get("user_prompt") or ""


def _consent_instruction(status):
    marker = "[iflytek-digital-human consent] status={}. ".format(status)
    if status == "accepted":
        return (marker + "Hook 已完成本地授权检查；不要运行 telemetry.py consent "
                "--status，不要向用户重复提示或询问数据授权，直接继续业务路由。")
    if status == "declined":
        return (marker + "Hook 已完成本地授权检查；不要运行 telemetry.py consent "
                "--status，不要向用户重复提示数据授权，保持统计关闭并继续业务路由。")
    if status in ("undecided", "stale"):
        try:
            capabilities, notice = _visible_consent_material()
        except Exception:
            return (marker + "无法从当前插件读取授权材料；请先修复插件文件读取，"
                    "不要扫描工程或调用下游 skill。")
        return (
            marker + "不要运行授权前的文件读取工具。必须在当前助手对话正文中原样展示以下两段内容，"
            "然后用 AskUserQuestion 只询问‘同意使用统计’或‘不同意使用统计’；"
            "未选择前不得业务路由、扫描工程、询问 quick/strict 或调用下游 skill。"
            "沉默或继续业务请求不算同意。\n\n"
            "===== docs/capabilities.md =====\n" + capabilities +
            "\n===== telemetry.py notice =====\n" + notice
        )
    return ("[iflytek-digital-human consent] status=unavailable. Hook 未能确定授权状态；"
            "在业务路由前回退运行 telemetry.py consent --status。")


def build_hook_output(payload, status_provider=None):
    """Build hook JSON; unrelated prompts never read the consent state."""
    prompt = _prompt_from(payload)
    if not has_explicit_avatar_command(prompt):
        return None

    if status_provider is None:
        tools_dir = Path(__file__).resolve().parent.parent / "tools"
        sys.path.insert(0, str(tools_dir))
        from telemetry_common import consent_status
        status_provider = consent_status

    try:
        status = status_provider()
    except Exception:
        status = "unavailable"
    if status not in VALID_CONSENT_STATES:
        status = "unavailable"

    routing = (
        "[iflytek-digital-human 路由提示] 本次请求涉及讯飞虚拟人/数字人。"
        "请先使用 avatar-workflow-entry 进行意图识别与路由，再分发到对应子技能；"
        "不要跳过入口直接用通用知识抛技术选型问题。"
    )
    invariants = (
        "[iflytek-digital-human 硬约束] 即使 Skill 工具不可用，也必须遵守以下已验证事实，"
        "禁止用通用知识、联网搜索或域名规律替代：\n"
        "0. Skill、Playbook 和工具只读取当前 ${{CLAUDE_PLUGIN_ROOT}}；禁止读取旧备份、"
        "旧 marketplace/cache 或工作目录中的同名 iflytek-digital-human 副本。\n"
        "1. WS_URL 基址是平台常量，只能是 {}；scheme、host、path 必须固定。"
        "运行时 signedUrl 允许在同一基址后追加 authorization/date/host 三个鉴权 query；"
        "Web SDK 前端使用服务端生成的 signedUrl，不再通过 WebSocket 消息体传递鉴权；"
        "不得添加其他 query、不得输出真实 authorization 或 apiKey，示例必须脱敏。\n"
        "2. 控制台唯一入口命令为 xfyun_common.py projects，实际执行 python "
        "\"${{CLAUDE_PLUGIN_ROOT}}/tools/xfyun_common.py\" projects；目标固定为 {}；"
        "禁止输出或打开其他控制台地址。\n"
        "3. 缺少 appId/sceneId 时保持 blocked_missing_credentials，执行 web_delivery.py "
        "返回 JSON 的 next_action，进入 avatar-credentials；不得猜值或转成自由文本建议。\n"
        "4. 退出码 2/3 都保持 workflow 为 in_progress 并只做非终态门禁上报；"
        "只有退出码 0 且 ready_to_deliver=true 才能完成上报或宣称交付。\n"
        "5. 文本驱动调用 writeText(text, {{ nlp: false }}) 只做 TTS；文本问答/文本交互调用 "
        "writeText(text, {{ nlp: true }}) 走 NLP；不得引用其他厂商或编造 interactionMode。"
    ).format(CANONICAL_WS_URL, PROJECTS_URL)
    context = routing + "\n" + invariants + "\n" + _consent_instruction(status)
    return {
        "systemMessage": context,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw.strip() else {}
        output = build_hook_output(payload)
        if output is not None:
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
            print(json.dumps(output, ensure_ascii=False))
    except Exception:
        # Routing hints must never block the user's prompt.
        return


if __name__ == "__main__":
    main()
