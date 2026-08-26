"""Telemetry completion regression tests.

These tests keep completion evidence scoped to the workflow that produced it:
the evidence must be newer than the workflow and must come from the project
directory captured when the workflow was created.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PLUGIN_ROOT / "tools"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(HOOKS_DIR))

import completion_check
import telemetry_common
import tracker


def iso_utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )


def write_json(path, data, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    os.utime(str(path), (mtime, mtime))


def state_with_workflow(
    workflow_id, cwd, started_at, workflow_type="live_streaming"
):
    state = telemetry_common._empty_state()
    state["workflows"].append({
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "anonymous_id": "anon-test",
        "started_at": started_at,
        "ended_at": None,
        "status": "in_progress",
        "has_avatar_signal": 1,
        "completion_method": None,
        "completion_detail": None,
        "cwd": str(cwd),
        "revision": 1,
        "upload_status": "pending",
        "updated_at": started_at,
    })
    return state


class CompletionEvidenceFreshnessTests(unittest.TestCase):
    def test_z_timestamp_is_interpreted_as_utc(self):
        self.assertEqual(
            completion_check._iso_to_epoch("2026-08-05T13:06:08.000Z"),
            datetime(2026, 8, 5, 13, 6, 8, tzinfo=timezone.utc).timestamp(),
        )

    def test_stale_verification_result_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = time.time()
            write_json(
                root / ".runtime" / "verification-result.json",
                {"ready_to_deliver": True},
                now - 120,
            )

            self.assertEqual(
                completion_check.detect(root, iso_utc(now - 60)),
                ("none", {}),
            )

    def test_incomplete_verification_result_is_not_a_terminal_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = time.time()
            write_json(
                root / ".runtime" / "verification-result.json",
                {
                    "ready_to_deliver": False,
                    "status": "needs_runtime_verification",
                    "remaining_issues": ["first_frame"],
                },
                now,
            )

            self.assertEqual(
                completion_check.detect(
                    root, iso_utc(now - 60), "sdk_integration"
                ),
                ("none", {}),
            )

    def test_stale_artifacts_result_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = time.time()
            write_json(
                root / ".runtime" / "artifacts.json",
                {"live_url": "/view/old"},
                now - 120,
            )

            self.assertEqual(
                completion_check.detect(root, iso_utc(now - 60)),
                ("none", {}),
            )

    def test_fresh_artifacts_result_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = time.time()
            artifact = root / ".runtime" / "artifacts.json"
            write_json(artifact, {"live_url": "/view/current"}, now)

            method, detail = completion_check.detect(root, iso_utc(now - 60))

            self.assertEqual(method, "artifacts_file")
            self.assertEqual(Path(detail["source"]), artifact)

    def test_sdk_workflow_does_not_complete_from_artifacts_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = time.time()
            write_json(
                root / ".runtime" / "artifacts.json",
                {"scene_id": "scene-current"},
                now,
            )

            self.assertEqual(
                completion_check.detect(
                    root, iso_utc(now - 60), "sdk_integration"
                ),
                ("none", {}),
            )


class WorkflowDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.project_dir = root / "project"
        self.drift_dir = root / "plugin"
        self.now = time.time()
        self.started_at = iso_utc(self.now - 60)
        write_json(
            self.project_dir / ".runtime" / "artifacts.json",
            {"live_url": "/view/current"},
            self.now,
        )
        write_json(
            self.drift_dir / ".runtime" / "artifacts.json",
            {"live_url": "/view/old"},
            self.now - 120,
        )

    def test_opportunistic_scan_uses_workflow_directory(self):
        state = state_with_workflow(
            "wf-prompt", self.project_dir, self.started_at)

        tracker.opportunistic_scan(
            state, "wf-prompt", {"cwd": str(self.drift_dir)}
        )

        item = state["workflows"][0]
        status = item["status"]
        method = item["completion_method"]
        detail = item["completion_detail"]
        self.assertEqual((status, method), ("completed", "artifacts_file"))
        self.assertNotIn("source", detail)
        self.assertNotIn(str(self.project_dir), json.dumps(detail))

    def test_session_end_uses_workflow_directory(self):
        state = state_with_workflow(
            "wf-end", self.project_dir, self.started_at)

        tracker.handle_end(
            state, {"cwd": str(self.drift_dir)}, "wf-end"
        )

        item = state["workflows"][0]
        status = item["status"]
        method = item["completion_method"]
        detail = item["completion_detail"]
        self.assertEqual((status, method), ("completed", "artifacts_file"))
        self.assertNotIn("source", detail)
        self.assertNotIn(str(self.project_dir), json.dumps(detail))


class StorageCutoverTests(unittest.TestCase):
    def test_legacy_sqlite_file_is_left_untouched_and_not_migrated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            telemetry_dir = Path(temp_dir)
            db_path = telemetry_dir / "usage.db"
            db_path.write_bytes(b"legacy-sqlite-data")
            state_path = telemetry_dir / "state.json"

            with mock.patch.object(telemetry_common, "STATE_PATH", state_path):
                state = telemetry_common.load_state()

            self.assertEqual(state["workflows"], [])
            self.assertEqual(db_path.read_bytes(), b"legacy-sqlite-data")
            self.assertFalse(state_path.exists())


if __name__ == "__main__":
    unittest.main()
