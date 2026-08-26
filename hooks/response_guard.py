#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Block avatar answers that contradict deterministic platform invariants."""

import json
import base64
import re
import sys
import urllib.parse
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
from platform_endpoints import CANONICAL_WS_URL, PROJECTS_URL  # noqa: E402


AVATAR_KEYWORDS = (
    "虚拟人", "数字人", "讯飞", "xfyun", "avatar", "virtual human",
    "digital human", "appid", "sceneid",
)
WS_QUESTION_MARKERS = ("wsurl", "websocket", "ws url", "ws地址", "ws 地址", "wss://")
CONSOLE_QUESTION_MARKERS = ("控制台", "appid", "sceneid", "凭据")
MISSING_MARKERS = ("没有", "缺少", "还没", "未有", "啥凭据都没有")
WSS_RE = re.compile(r"wss://[^\s`'\"<>，。；、)]+", re.I)
SIGNED_URL_QUERY_KEYS = frozenset(("authorization", "date", "host"))
API_KEY_IN_AUTH_RE = re.compile(r'api_key\s*=\s*"([^\"]+)"', re.I)
AUTH_IN_MESSAGE_RE = re.compile(
    r"(?:认证|鉴权)(?:信息|材料|参数)?.{0,16}"
    r"(?<!不)(?<!不是)(?:通过|放入|放在|写入|携带).{0,20}"
    r"(?:WebSocket\s*)?(?:消息体|消息正文|业务消息)",
    re.I | re.S,
)
TEXT_MODE_VENDOR_RE = re.compile(r"(?:腾讯云|阿里云|百度智能云|字节云|数智人)", re.I)
KNOWLEDGE_MARKERS = ("知识库", "docqa", "rag", "xfyun_knowledge.py")
EXTERNAL_MODEL_MARKERS = (
    "deepseek", "gpt", "chatgpt", "外部模型", "第三方模型", "自有模型",
)
PSEUDO_PLATFORM_COMMAND_RE = re.compile(
    r"\b(?:create-custom-model|bind-model|create-knowledge-base|"
    r"upload-kb-document|enable-kb-for-scene|publish-kb-scene)\b",
    re.I,
)
INVENTED_WEB_TRANSPARENCY_RE = re.compile(
    r"\btransparentBackground\b|\b(?:avatar\.)?player\.alpha\b",
    re.I,
)
SET_API_INFO_RE = re.compile(
    r"setApiInfo\s*\(\s*\{(?P<body>.*?)\}\s*\)", re.I | re.S
)
UNSAFE_WEB_API_INFO_RE = re.compile(
    r"\b(?:apiKey|apiSecret|serverUrl)\b", re.I
)
WEB_DELIVERY_GENERATES_RE = re.compile(
    r"web_delivery\.py[^\r\n]{0,180}\brun\b.{0,400}"
    r"(?:这个命令会|该命令会|运行后会).{0,300}(?:生成|创建|搭建).{0,160}"
    r"(?:server\.js|app\.js|package\.json|工程骨架)",
    re.I | re.S,
)
WEB_DELIVERY_DIRECT_GENERATES_RE = re.compile(
    r"web_delivery\.py[^\r\n。]{0,100}(?:会|将|负责|用于)\s*"
    r"(?:自动)?(?:生成|创建|搭建)[^\r\n。]{0,120}"
    r"(?:server\.js|app\.js|package\.json|工程骨架)",
    re.I,
)
SERVER_FIRST_RE = re.compile(
    r"(?:"
    r"server\.js.{0,80}(?:必须|需要).{0,30}(?:先|预先|已经)?.{0,20}(?:存在|创建|建好)"
    r"|(?:第一项|首先).{0,80}检查.{0,80}server\.js.{0,80}(?:存在|是否存在|存在与否)"
    r"|(?:工程)?骨架.{0,80}(?:状态机|web_delivery\.py).{0,40}前置条件"
    r")",
    re.I | re.S,
)


def _contains_any(text, markers):
    low = text.lower()
    return any(marker.lower() in low for marker in markers)


def _is_avatar_related(prompt):
    return _contains_any(prompt, AVATAR_KEYWORDS)


def _signed_url_issues(url):
    """Validate a base endpoint or its three-field signed URL envelope.

    The platform endpoint is immutable, while the auth module appends
    authorization/date/host query fields. Keep this distinction in the
    response guard so valid runtime URLs are not mistaken for hallucinated
    endpoints.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return ["noncanonical_ws_url"]

    base = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, "", "")
    )
    if base != CANONICAL_WS_URL or parsed.fragment:
        return ["noncanonical_ws_url"]
    if not parsed.query:
        return []

    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != SIGNED_URL_QUERY_KEYS:
        return ["noncanonical_ws_url"]
    if any(len(values) != 1 or not values[0] for values in query.values()):
        return ["noncanonical_ws_url"]
    if query["host"][0] != urllib.parse.urlsplit(CANONICAL_WS_URL).netloc:
        return ["noncanonical_ws_url"]

    # A real signed authorization decodes to api_key="<32 chars>" plus the
    # algorithm/signature fields. Do not allow credentials to enter a model
    # answer or transcript, even though the URL target itself is valid.
    try:
        encoded = query["authorization"][0]
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(encoded + padding, validate=True).decode(
            "utf-8", errors="replace"
        )
    except (ValueError, UnicodeError):
        decoded = ""
    match = API_KEY_IN_AUTH_RE.search(decoded)
    if match and len(match.group(1)) == 32:
        return ["sensitive_signed_url"]
    return []


def validate_response(prompt, response):
    """Return deterministic violation codes for the latest avatar answer."""
    if not _is_avatar_related(prompt):
        return []

    issues = []
    asks_ws = _contains_any(prompt, WS_QUESTION_MARKERS)
    asks_console = _contains_any(prompt, CONSOLE_QUESTION_MARKERS)
    missing_credentials = (
        asks_console
        and _contains_any(prompt, MISSING_MARKERS)
    )
    asks_web_sdk = "web" in prompt.lower() and "sdk" in prompt.lower()
    asks_scaffold = asks_web_sdk and _contains_any(
        prompt, ("骨架", "scaffold", "最小工程")
    )
    asks_state_commands = _contains_any(
        prompt, ("状态机命令", "真实状态机", "状态命令")
    )
    asks_text_modes = (
        _contains_any(prompt, ("文本驱动",))
        and _contains_any(prompt, ("文本问答", "文本交互"))
    )
    asks_knowledge = _contains_any(prompt, KNOWLEDGE_MARKERS)
    asks_external_knowledge = asks_knowledge and _contains_any(
        prompt, EXTERNAL_MODEL_MARKERS
    )
    asks_web_transparency = (
        "web" in prompt.lower()
        and _contains_any(prompt, ("透明", "alpha", "transparent"))
    )

    urls = [url.rstrip(".,;:") for url in WSS_RE.findall(response)]
    for url in urls:
        for issue in _signed_url_issues(url):
            if issue not in issues:
                issues.append(issue)
    if "signedurl" in response.lower() and AUTH_IN_MESSAGE_RE.search(response):
        issues.append("invalid_signed_url_transport")
    if asks_ws and CANONICAL_WS_URL not in response:
        issues.append("missing_canonical_ws_url")
    if re.search(
        r"(?:WS_URL|WebSocket|wsurl|域名|host|地址).{0,24}"
        r"(?:随|可能|根据).{0,24}(?:变化|改变|不同)",
        response,
        re.I | re.S,
    ):
        issues.append("endpoint_not_constant")

    if "console.xfyun.cn" in response.lower():
        issues.append("wrong_console_url")
    if asks_console and PROJECTS_URL not in response:
        issues.append("missing_projects_console")
    if asks_console and not re.search(
        r"xfyun_common\.py[\"']?\s+projects\b", response, re.I
    ):
        issues.append("missing_projects_command")

    if missing_credentials:
        if "blocked_missing_credentials" not in response:
            issues.append("missing_blocked_status")
        if "next_action" not in response:
            issues.append("missing_next_action")

    if asks_web_sdk:
        for match in SET_API_INFO_RE.finditer(response):
            body = match.group("body")
            if UNSAFE_WEB_API_INFO_RE.search(body):
                issues.append("unsafe_web_set_api_info")
            if not re.search(r"\bsignedUrl\b", body, re.I):
                issues.append("missing_signed_url_api_info")
        if (WEB_DELIVERY_GENERATES_RE.search(response)
                or WEB_DELIVERY_DIRECT_GENERATES_RE.search(response)):
            issues.append("invented_web_delivery_generation")

    if asks_scaffold and not SERVER_FIRST_RE.search(response):
        issues.append("missing_server_first_contract")

    if asks_state_commands:
        if not re.search(r"web_delivery\.py[\"']?\s+run\b", response, re.I):
            issues.append("missing_web_delivery_run_command")
        if not re.search(r"web_delivery\.py[\"']?\s+status\b", response, re.I):
            issues.append("missing_web_delivery_status_command")

    if asks_text_modes:
        if TEXT_MODE_VENDOR_RE.search(response):
            issues.append("wrong_vendor_text_mode")
        if re.search(r"\binteractionMode\b", response, re.I):
            issues.append("invented_text_interaction_mode")
        if not re.search(r"nlp\s*:\s*false", response, re.I):
            issues.append("missing_text_driver_nlp_false")
        if not re.search(r"nlp\s*:\s*true", response, re.I):
            issues.append("missing_text_interact_nlp_true")

    if asks_knowledge:
        if re.search(
            r"--vector\s+bge-large-zh-v1\.5|--llm\s+xinghuo-4\.0",
            response,
            re.I,
        ):
            issues.append("invalid_knowledge_model_alias")
        if re.search(
            r"0\s*[=—:-]\s*处理中.{0,40}1\s*[=—:-]\s*成功.{0,40}"
            r"2\s*[=—:-]\s*失败",
            response,
            re.I | re.S,
        ):
            issues.append("invalid_knowledge_document_status")
        if re.search(
            r"enable.{0,30}(?:不会|不自动|不会自动).{0,20}publish",
            response,
            re.I | re.S,
        ):
            issues.append("wrong_enable_publish_semantics")

    if asks_web_transparency:
        for match in INVENTED_WEB_TRANSPARENCY_RE.finditer(response):
            line_start = response.rfind("\n", 0, match.start()) + 1
            prefix = response[line_start:match.start()]
            if not re.search(r"(?:不存在|不支持|没有|不要|不可|无此)", prefix):
                issues.append("invented_web_transparency_api")
                break

    if asks_external_knowledge:
        if PSEUDO_PLATFORM_COMMAND_RE.search(response):
            issues.append("invented_platform_command")
        if "xfyun_model_manage.py" not in response:
            issues.append("missing_external_model_tool")
        if "xfyun_knowledge.py" not in response:
            issues.append("missing_knowledge_tool")
        if "docqa,openai" not in response.lower():
            issues.append("missing_external_knowledge_chain")

    return list(dict.fromkeys(issues))


def _content_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )


def _is_internal_user_record(record, content):
    """Identify Claude-generated user-shaped records, not user prompts."""
    if record.get("isMeta"):
        return True
    if record.get("toolUseResult") is not None:
        return True
    if record.get("sourceToolAssistantUUID"):
        return True
    return any(
        isinstance(item, dict) and item.get("type") == "tool_result"
        for item in content
    ) if isinstance(content, list) else False


def latest_exchange(transcript_path):
    """Extract the latest user prompt and assistant text from a JSONL transcript."""
    prompt = ""
    response = ""
    with Path(transcript_path).open("r", encoding="utf-8", errors="replace") as stream:
        for raw in stream:
            try:
                record = json.loads(raw)
            except Exception:
                continue
            message = record.get("message") if isinstance(record, dict) else None
            if not isinstance(message, dict):
                continue
            role = message.get("role") or record.get("type")
            text = _content_text(message.get("content"))
            # Claude writes Stop-hook feedback as a synthetic user record. It is
            # marked isMeta=true and must not replace the user's original prompt;
            # otherwise a correction turn loses the avatar-specific checks.
            is_internal_user = _is_internal_user_record(
                record, message.get("content")
            )
            if role == "user" and not is_internal_user:
                prompt = text
                response = ""
            elif role == "assistant" and prompt and text:
                response = text
    return prompt, response


def latest_user_prompt(transcript_path):
    """Read only user-shaped JSONL records from the end of a transcript."""
    data = Path(transcript_path).read_bytes()
    for raw in reversed(data.splitlines()):
        if b'"role":"user"' not in raw and b'"role": "user"' not in raw:
            continue
        try:
            record = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        message = record.get("message") if isinstance(record, dict) else None
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if _is_internal_user_record(record, content):
            continue
        text = _content_text(content)
        if text:
            return text
    return ""


def _correction_reason(issues):
    return (
        "avatar-grill 最终回答门禁未通过（{}）。丢弃上一版回答并重新回答，"
        "不得解释或引用上一版错误内容。必须使用以下已验证事实：\n"
        "- WS_URL 是固定平台常量：{}。不得说区域、租户或版本会改变它。\n"
        "- 控制台唯一入口命令：xfyun_common.py projects；固定目标：{}。"
        "不得输出 console.xfyun.cn 或第三方控制台。即使原问题要求‘错误示例’，也只能用抽象占位符（如 <wrong-url>），"
        "不得输出任何非规范的真实 URL，也不得引用上一版错误 URL。\n"
        "- 如果需要说明 signedUrl，只能说明固定基址后追加 authorization/date/host 三个 query，"
        "authorization 必须脱敏；不得把真实签名或 apiKey 放进回答，也不得说 Web SDK 还通过"
        " WebSocket 消息体传递鉴权。\n"
        "- Web SDK 前端固定先取 GET /api/avatar-auth -> {{signedUrl,timestamp}} 和 "
        "GET /api/config -> {{appId,sceneId,avatarId,vcn,wsUrl}}，然后只调用 "
        "setApiInfo({{signedUrl, appId, sceneId}})；apiKey/apiSecret 只保存在 Node 服务端。\n"
        "- 最小 server.js 工程骨架可以在凭据和 SDK 之前创建，且 server.js 必须先存在。"
        "web_delivery.py 不生成 server.js/public/app.js/package.json；它编排已有骨架的凭据、"
        "canonical auth、SDK、服务和门禁。真实命令是 web_delivery.py run 与 "
        "web_delivery.py status；缺 server.js 时先返回 blocked_server_lifecycle/server_js_missing。\n"
        "- 缺 appId/sceneId 时明确写 blocked_missing_credentials，并说明执行 "
        "web_delivery.py JSON 的 next_action，由 avatar-grill 执行凭据和资源恢复。\n"
        "- 退出码 2/3 保持 workflow 为 in_progress；只有退出码 0 且 "
        "ready_to_deliver=true 才完成。\n"
        "- 文本驱动与文本问答只能按当前 Skill 的 API 解释：前者 `writeText(text, {{nlp: false}})` "
        "只做 TTS，后者 `writeText(text, {{nlp: true}})` 走 NLP；不得引用腾讯云或编造 interactionMode。"
        "\n- 知识库只使用 xfyun_knowledge.py 的真实命令；默认模型 ID 是 emb_v1_1024/xhdmx1，"
        "文档状态为 1=就绪、0/-2/-4=处理中、-3=采编异常；enable 默认自动 publish，"
        "只有 --no-publish 才跳过。"
        "\n- Web 透明背景只配置 xrtc 与 avatar.stream.alpha=1；当前 SDK 没有 "
        "transparentBackground 或 player.alpha API，播放器由 SDP a=xrtc-alpha 自动启用。"
        "\n- 外部模型加知识库必须使用 xfyun_model_manage.py 与 xfyun_knowledge.py 的真实命令，"
        "自有模型链路为 docqa,openai；不得输出 create-custom-model 等伪命令。"
    ).format(",".join(issues), CANONICAL_WS_URL, PROJECTS_URL)


def build_stop_output(payload):
    """Return a Stop block decision, or None when the response is valid."""
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return None
    prompt = payload.get("prompt") or ""
    response = payload.get("last_assistant_message") or ""
    transcript_path = payload.get("transcript_path")
    try:
        if response:
            if not prompt and transcript_path:
                prompt = latest_user_prompt(transcript_path)
        elif transcript_path:
            prompt, response = latest_exchange(transcript_path)
        else:
            return None
    except Exception:
        return None
    if not prompt or not response:
        return None
    issues = validate_response(prompt, response)
    if not issues:
        return None
    reason = _correction_reason(issues)
    return {
        "decision": "block",
        "reason": reason,
        "systemMessage": reason,
    }


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw.strip() else {}
        output = build_stop_output(payload)
        if output:
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
            print(json.dumps(output, ensure_ascii=False))
    except Exception:
        return


if __name__ == "__main__":
    main()
