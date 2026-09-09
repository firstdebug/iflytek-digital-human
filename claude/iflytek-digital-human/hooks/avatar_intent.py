#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared high-confidence avatar intent detection for global hooks."""

import re


STRONG_AVATAR_PHRASES = (
    "虚拟人", "数字人", "avatar sdk", "xfyun avatar", "virtual-man",
    "virtual human", "digital human", "讯飞知识库", "xfyun knowledge",
    "h5通话", "透明背景", "全双工",
)
AVATAR_SLASH_RE = re.compile(
    r"/iflytek-digital-human(?::[a-z0-9][a-z0-9-]*)?\b", re.I
)
EXPLICIT_AVATAR_COMMAND_RE = re.compile(
    r"/iflytek-digital-human:[a-z0-9][a-z0-9-]*\b", re.I
)


def has_explicit_avatar_command(text):
    """Return true only for an explicit /iflytek-digital-human:<skill> command."""
    return isinstance(text, str) and bool(EXPLICIT_AVATAR_COMMAND_RE.search(text))


def is_avatar_related(text):
    """Return true only for explicit plugin use or strong domain phrases."""
    if not isinstance(text, str) or not text:
        return False
    if AVATAR_SLASH_RE.search(text):
        return True
    low = text.lower()
    return any(phrase.lower() in low for phrase in STRONG_AVATAR_PHRASES)
