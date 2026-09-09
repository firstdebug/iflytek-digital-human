"""Small persistent bridge between separate Codex hook processes."""

import json
import os
import hashlib
from pathlib import Path


def _path(session_id):
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    digest = hashlib.sha256(str(session_id).encode("utf-8")).hexdigest()
    return root / "iflytek-digital-human" / "hook-sessions" / (digest + ".json")


def _read(session_id):
    try:
        return json.loads(_path(session_id).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(session_id, data):
    path = _path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def mark_avatar_session(payload, phase):
    session_id = payload.get("session_id") or payload.get("sessionId")
    if not session_id:
        return
    previous = _read(session_id)
    data = {
        "session_id": str(session_id),
        "phase": phase,
    }
    _write(session_id, data)


def current(session_id):
    if not session_id:
        return {}
    data = _read(session_id)
    return data if data.get("session_id") == str(session_id) else {}


def clear(session_id):
    if not session_id:
        return
    try:
        _path(session_id).unlink()
    except OSError:
        pass
