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
from avatar_intent import is_avatar_related  # noqa: E402


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
KNOWLEDGE_MARKERS = ("知识库", "docqa", "xfyun_knowledge.py")
RAG_WORD_RE = re.compile(r"(?<![a-z0-9_])rag(?![a-z0-9_])", re.I)
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
    if not is_avatar_related(prompt):
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
    asks_knowledge = (
        _contains_any(prompt, KNOWLEDGE_MARKERS)
        or bool(RAG_WORD_RE.search(prompt))
    )
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
    if (record.get("isMeta") or record.get("isCompactSummary") or
            record.get("isVisibleInTranscriptOnly")):
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
    issue_set = set(issues)
    facts = []

    if issue_set & {
            "noncanonical_ws_url", "sensitive_signed_url",
            "invalid_signed_url_transport", "missing_canonical_ws_url",
            "endpoint_not_constant"}:
        facts.append(
            "WS_URL 固定为 {}；signedUrl 只追加脱敏的 "
            "authorization/date/host。".format(CANONICAL_WS_URL)
        )
    if issue_set & {
            "wrong_console_url", "missing_projects_console",
            "missing_projects_command"}:
        facts.append(
            "控制台只使用 xfyun_common.py projects，目标为 {}。".format(
                PROJECTS_URL)
        )
    if issue_set & {"missing_blocked_status", "missing_next_action"}:
        facts.append(
            "缺 appId/sceneId 时返回 blocked_missing_credentials，并按 "
            "web_delivery.py JSON 的 next_action 进入 avatar-credentials。"
        )
    if issue_set & {"unsafe_web_set_api_info", "missing_signed_url_api_info"}:
        facts.append(
            "Web 前端只调用 setApiInfo({signedUrl, appId, sceneId})；"
            "apiKey/apiSecret 只保存在 Node 服务端。"
        )
    if issue_set & {
            "invented_web_delivery_generation", "missing_server_first_contract",
            "missing_web_delivery_run_command", "missing_web_delivery_status_command"}:
        facts.append(
            "server.js 必须先存在；web_delivery.py 不生成工程骨架，"
            "只使用 run/status 编排已有工程。"
        )
    if issue_set & {
            "wrong_vendor_text_mode", "invented_text_interaction_mode",
            "missing_text_driver_nlp_false", "missing_text_interact_nlp_true"}:
        facts.append(
            "文本驱动使用 writeText(text, {nlp: false})，文本问答使用 "
            "writeText(text, {nlp: true})。"
        )
    if issue_set & {
            "invalid_knowledge_model_alias", "invalid_knowledge_document_status",
            "wrong_enable_publish_semantics"}:
        facts.append(
            "知识库使用 xfyun_knowledge.py；默认 emb_v1_1024/xhdmx1，"
            "文档 1=就绪、0/-2/-4=处理中、-3=采编异常，enable 默认 publish。"
        )
    if "invented_web_transparency_api" in issue_set:
        facts.append(
            "Web 透明背景只配置 xrtc 与 avatar.stream.alpha=1；"
            "不存在 transparentBackground 或 player.alpha API。"
        )
    if issue_set & {
            "invented_platform_command", "missing_external_model_tool",
            "missing_knowledge_tool", "missing_external_knowledge_chain"}:
        facts.append(
            "外部模型加知识库使用 xfyun_model_manage.py 与 "
            "xfyun_knowledge.py，链路为 docqa,openai。"
        )

    return (
        "iflytek-digital-human 最终回答门禁未通过（{}）。只修正以下命中项，"
        "不要扩展到无关能力：\n- {}"
    ).format(",".join(issues), "\n- ".join(facts))


def _session_scope_matches(payload, transcript_path, uses_transcript):
    """Block only when Claude proves the transcript belongs to this session."""
    session_id = payload.get("session_id") or payload.get("sessionId")
    if not session_id:
        return False
    if not uses_transcript or not transcript_path:
        return True
    return Path(transcript_path).stem.lower() == str(session_id).lower()


def build_stop_output(payload):
    """Return a Stop block decision, or None when the response is valid."""
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return None
    prompt = payload.get("prompt") or ""
    response = payload.get("last_assistant_message") or ""
    transcript_path = payload.get("transcript_path")
    uses_transcript = not prompt or not response
    if not _session_scope_matches(payload, transcript_path, uses_transcript):
        return None
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
