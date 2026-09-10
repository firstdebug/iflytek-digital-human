import re


STRONG_AVATAR_PHRASES = (
    "虚拟人", "数字人", "avatar sdk", "xfyun avatar", "virtual-man",
    "virtual human", "digital human", "讯飞知识库", "xfyun knowledge",
    "h5通话", "透明背景", "全双工",
)
BACKEND_NLP_DEBUG_MARKERS = (
    "nlpmessage", "nlp-svc", "nlp svc", "openai sse", "sse连接",
    "经过svc", "higress", "spring boot",
)
EXPLICIT_AVATAR_TASK_MARKERS = (
    "创建虚拟人", "搭建虚拟人", "接入虚拟人", "集成虚拟人",
    "创建数字人", "搭建数字人", "接入数字人", "集成数字人",
    "虚拟人项目", "数字人项目", "虚拟人对话", "数字人对话",
    "虚拟人 sdk", "数字人 sdk", "avatar sdk", "digital human",
    "virtual human", "讯飞虚拟人",
)
AVATAR_SLASH_RE = re.compile(r"/iflytek-digital-human(?::[a-z0-9][a-z0-9-]*)?\b", re.I)
AVATAR_SKILL_RE = re.compile(
    r"\$(?:iflytek-digital-human|avatar-platform):avatar-[a-z0-9-]+\b", re.I
)


def is_avatar_related(text):
    if not isinstance(text, str) or not text:
        return False
    # An explicit plugin/skill invocation is authoritative, even if the
    # surrounding prompt quotes backend NLP terms from an earlier message.
    if AVATAR_SLASH_RE.search(text) or AVATAR_SKILL_RE.search(text):
        return True
    low = text.lower()
    if (any(marker in low for marker in BACKEND_NLP_DEBUG_MARKERS)
            and not any(marker in low for marker in EXPLICIT_AVATAR_TASK_MARKERS)):
        return False
    return any(phrase.lower() in low for phrase in STRONG_AVATAR_PHRASES)
