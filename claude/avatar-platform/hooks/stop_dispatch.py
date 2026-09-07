#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the Stop response gate once and flush telemetry out of band."""

import json
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = HOOKS_DIR.parent

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def dispatch(raw):
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    # Keep the blocking response gate in this process so Claude receives its
    # decision. It prefers last_assistant_message and avoids transcript scans.
    try:
        from response_guard import build_stop_output
        decision = build_stop_output(payload)
        if decision:
            print(json.dumps(decision, ensure_ascii=False))
    except Exception:
        pass

    # Telemetry must never delay or block the Stop decision. The tracker has its
    # own JSON state lock and uploader isolation; this child is deliberately
    # detached from Claude's hook lifecycle.
    try:
        tracker = HOOKS_DIR / "tracker.py"
        child = subprocess.Popen(
            [sys.executable, str(tracker), "stop"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            child.stdin.write(raw.encode("utf-8"))
            child.stdin.close()
        except Exception:
            pass
    except Exception:
        pass


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    dispatch(raw)


if __name__ == "__main__":
    main()
