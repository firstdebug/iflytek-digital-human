#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared high-confidence avatar intent detection for global hooks."""

import re


AVATAR_SLASH_RE = re.compile(
    r"/(?:iflytek-digital-human|avatar-platform)(?::[a-z0-9][a-z0-9-]*)?\b",
    re.I,
)
AVATAR_COMMAND_RE = re.compile(
    r"(?:[/$](?:(?:iflytek-digital-human|avatar-platform):)?)"
    r"(avatar-[a-z0-9-]+)\b",
    re.I,
)


def _strip_non_invocation_context(text):
    text = re.sub(r"```.*?```", "\n", text, flags=re.S)
    kept = []
    quoted_prefix = re.compile(
        r"^\s*(?:>|上一轮|上轮|引用|历史|quoted|previous|earlier)(?:\b|[:：\s])",
        re.I,
    )
    for line in text.splitlines():
        if quoted_prefix.search(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def explicit_avatar_commands(text):
    if not isinstance(text, str) or not text:
        return []
    visible = _strip_non_invocation_context(text)
    return [match.group(1).lower() for match in AVATAR_COMMAND_RE.finditer(visible)]


def has_explicit_avatar_command(text):
    """Return true only for an explicit current-message skill command."""
    return bool(explicit_avatar_commands(text))


def is_avatar_related(text):
    """Return true only for explicit plugin/skill use."""
    if not isinstance(text, str) or not text:
        return False
    return has_explicit_avatar_command(text)
