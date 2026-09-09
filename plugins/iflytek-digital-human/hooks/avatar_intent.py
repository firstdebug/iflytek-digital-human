import re


STRONG_AVATAR_PHRASES = (
    "虚拟人", "数字人", "avatar sdk", "xfyun avatar", "virtual-man",
    "virtual human", "digital human", "讯飞知识库", "xfyun knowledge",
    "h5通话", "透明背景", "全双工",
)
AVATAR_SLASH_RE = re.compile(r"/iflytek-digital-human(?::[a-z0-9][a-z0-9-]*)?\b", re.I)
AVATAR_SKILL_RE = re.compile(
    r"\$(?:iflytek-digital-human|avatar-platform):avatar-[a-z0-9-]+\b", re.I
)


def is_avatar_related(text):
    if not isinstance(text, str) or not text:
        return False
    if AVATAR_SLASH_RE.search(text) or AVATAR_SKILL_RE.search(text):
        return True
    low = text.lower()
    return any(phrase.lower() in low for phrase in STRONG_AVATAR_PHRASES)
