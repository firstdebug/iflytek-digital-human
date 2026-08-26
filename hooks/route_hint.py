#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inject avatar routing and the local consent state on UserPromptSubmit."""

import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
from platform_endpoints import CANONICAL_WS_URL, PROJECTS_URL  # noqa: E402


STRONG_AVATAR_KEYWORDS = (
    "虚拟人", "数字人", "avatar sdk", "xfyun avatar", "virtual-man",
    "virtual human", "digital human", "h5通话", "透明背景", "全双工",
)
AVATAR_CONTEXT = (
    "虚拟人", "数字人", "avatar sdk", "xfyun avatar", "virtual-man",
    "virtual human", "digital human",
)
CONTEXTUAL_KEYWORDS = (
    "讯飞", "xfyun", "直播", "智能客服", "语音交互", "文本驱动",
    "音频驱动", "动作控制", "形象", "发音人", "场景", "模型配置",
    "知识库", "appid", "appsecret", "anchorid", "vcn", "web对话",
    "大屏交互", "字幕", "web template", "live streaming",
    "voice interact", "text driver", "audio driver",
)

VALID_CONSENT_STATES = {"accepted", "declined", "undecided", "stale"}


def _prompt_from(payload):
    if not isinstance(payload, dict):
        return ""
    return payload.get("prompt") or payload.get("user_prompt") or ""


def _is_avatar_related(prompt):
    low = prompt.lower()
    if any(keyword in low for keyword in STRONG_AVATAR_KEYWORDS):
        return True
    has_context = any(keyword in low for keyword in AVATAR_CONTEXT)
    return has_context and any(keyword in low for keyword in CONTEXTUAL_KEYWORDS)


def _consent_instruction(status):
    marker = "[avatar-grill consent] status={}. ".format(status)
    if status == "accepted":
        return (marker + "Hook 已完成本地授权检查；不要运行 telemetry.py consent "
                "--status，不要向用户重复提示或询问数据授权，直接继续业务路由。")
    if status == "declined":
        return (marker + "Hook 已完成本地授权检查；不要运行 telemetry.py consent "
                "--status，不要向用户重复提示数据授权，保持统计关闭并继续业务路由。")
    if status in ("undecided", "stale"):
        return (marker + "不要重复运行 telemetry.py consent --status。在业务路由前运行 "
                "telemetry.py notice，原样展示完整声明，并等待用户明确选择同意或不同意；"
                "沉默或继续业务请求不算同意。")
    return ("[avatar-grill consent] status=unavailable. Hook 未能确定授权状态；"
            "在业务路由前回退运行 telemetry.py consent --status。")


def build_hook_output(payload, status_provider=None):
    """Build hook JSON; unrelated prompts never read the consent state."""
    prompt = _prompt_from(payload)
    if not _is_avatar_related(prompt):
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
        "[avatar-grill 路由提示] 本次请求涉及讯飞虚拟人/数字人。"
        "请使用 avatar-grill 先查询事实、计算问题前沿并生成执行契约；"
        "不要路由到其他 Skill，也不要直接用通用知识抛技术选型问题。"
    )
    invariants = (
        "[avatar-grill 硬约束] 即使 Skill 工具不可用，也必须遵守以下已验证事实，"
        "禁止用通用知识、联网搜索或域名规律替代：\n"
        "0. Skill、Playbook 和工具只读取当前 ${{CLAUDE_PLUGIN_ROOT}}；禁止读取旧备份、"
        "旧 marketplace/cache 或工作目录中的同名 avatar-grill/avatar-platform 副本。\n"
        "1. WS_URL 基址是平台常量，只能是 {}；scheme、host、path 必须固定。"
        "运行时 signedUrl 允许在同一基址后追加 authorization/date/host 三个鉴权 query；"
        "Web SDK 前端使用服务端生成的 signedUrl，不再通过 WebSocket 消息体传递鉴权；"
        "不得添加其他 query、不得输出真实 authorization 或 apiKey，示例必须脱敏。\n"
        "2. 控制台唯一入口命令为 xfyun_common.py projects，实际执行 python "
        "\"${{CLAUDE_PLUGIN_ROOT}}/tools/xfyun_common.py\" projects；目标固定为 {}；"
        "禁止输出或打开其他控制台地址。\n"
        "3. 缺少 appId/sceneId 时保持 blocked_missing_credentials，执行 web_delivery.py "
        "返回 JSON 的 next_action，由 avatar-grill 执行凭据和资源恢复；不得猜值或转成自由文本建议。\n"
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
