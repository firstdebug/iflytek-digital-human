"""JSON-state telemetry lifecycle and reliability tests."""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PLUGIN_ROOT / "tools"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(HOOKS_DIR))

import telemetry
import telemetry_common
import tracker
import uploader


STAMP = "2026-08-25T01:00:00.000Z"


def workflow(workflow_id="wf-1", status="in_progress", revision=1, **values):
    item = {
        "workflow_id": workflow_id,
        "workflow_type": "sdk_integration",
        "anonymous_id": "anon-test",
        "started_at": STAMP,
        "ended_at": None,
        "status": status,
        "has_avatar_signal": 1,
        "completion_method": None,
        "completion_detail": None,
        "os": "win32",
        "plugin_version": "1.0.0",
        "revision": revision,
        "cwd": "C:/project",
        "upload_status": "pending",
        "updated_at": STAMP,
    }
    item.update(values)
    return item


def invocation(invocation_id="inv-1", workflow_id="wf-1", **values):
    item = {
        "invocation_id": invocation_id,
        "workflow_id": workflow_id,
        "skill_name": "avatar-grill",
        "anonymous_id": "anon-test",
        "source": "skill_tool",
        "first_at": STAMP,
        "last_at": STAMP,
        "revision": 1,
        "upload_status": "pending",
        "updated_at": STAMP,
    }
    item.update(values)
    return item


class JsonStateSandbox(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.telemetry_dir = self.root / "telemetry"
        self.state_path = self.telemetry_dir / "state.json"
        self.state_lock = self.telemetry_dir / "state.lock"
        self.uploader_lock = self.telemetry_dir / "uploader.lock"
        self.patches = [
            mock.patch.multiple(
                telemetry_common,
                TELEMETRY_DIR=self.telemetry_dir,
                STATE_PATH=self.state_path,
                STATE_LOCK_PATH=self.state_lock,
                ANON_ID_PATH=self.telemetry_dir / "anonymous_id.json",
                CONSENT_PATH=self.telemetry_dir / "consent.json",
                CURRENT_SESSION_PATH=self.telemetry_dir / "current_session",
            ),
            mock.patch.multiple(
                uploader,
                STATE_LOCK_PATH=self.state_lock,
                UPLOADER_LOCK_PATH=self.uploader_lock,
            ),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def save(self, state):
        telemetry_common.save_state(state)

    def load(self):
        return telemetry_common.load_state()


class StateFileTests(JsonStateSandbox):
    def test_locked_state_creates_one_json_state_file(self):
        with telemetry_common.locked_state() as state:
            state["workflows"].append(workflow())

        loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema_version"], "2.0-json")
        self.assertEqual(loaded["workflows"][0]["workflow_id"], "wf-1")
        self.assertFalse((self.telemetry_dir / "usage.db").exists())

    def test_atomic_write_leaves_no_temporary_file(self):
        self.save(telemetry_common._empty_state())
        self.assertTrue(self.state_path.exists())
        self.assertEqual(list(self.telemetry_dir.glob("*.tmp")), [])

    def test_corrupt_state_is_quarantined_and_recreated(self):
        self.telemetry_dir.mkdir(parents=True)
        self.state_path.write_text("{broken", encoding="utf-8")
        state = self.load()
        self.assertEqual(state["workflows"], [])
        self.assertFalse(self.state_path.exists())
        self.assertEqual(len(list(self.telemetry_dir.glob("state.corrupt-*.json"))), 1)
        self.save(state)
        self.assertTrue(self.state_path.exists())

    def test_structurally_invalid_collections_are_normalized(self):
        self.telemetry_dir.mkdir(parents=True)
        self.state_path.write_text(json.dumps({
            "workflows": "not-a-list",
            "invocations": {"bad": True},
            "session_workflows": [],
        }), encoding="utf-8")
        state = self.load()
        self.assertEqual(state["workflows"], [])
        self.assertEqual(state["invocations"], [])
        self.assertEqual(state["session_workflows"], {})

    def test_removed_prompt_and_hit_fields_are_scrubbed_from_legacy_state(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(
            first_prompt="legacy prompt", xfyun_user_id="xf_old"))
        state["invocations"].append(invocation(hit_count=9))

        self.save(state)
        loaded = self.load()

        self.assertNotIn("first_prompt", loaded["workflows"][0])
        self.assertNotIn("hit_count", loaded["invocations"][0])
        self.assertNotIn("xfyun_user_id", loaded["workflows"][0])

    def test_upload_backoff_state_lives_inside_state_json(self):
        uploader.save_upload_state({
            "retry_count": 2,
            "last_attempt": STAMP,
            "last_ack_at": STAMP,
        })
        state = self.load()
        self.assertEqual(state["upload"]["retry_count"], 2)
        self.assertEqual(uploader.load_upload_state()["last_attempt"], STAMP)
        self.assertFalse((self.telemetry_dir / "upload_state.json").exists())

    def test_file_lock_blocks_another_process_then_releases(self):
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, {!r}); "
            "from telemetry_common import file_lock; "
            "p=Path({!r}); ctx=file_lock(p, timeout=0.1); "
            "ok=ctx.__enter__(); print('locked' if ok else 'busy'); "
            "ctx.__exit__(None,None,None)"
        ).format(str(TOOLS_DIR), str(self.state_lock))
        with telemetry_common.file_lock(self.state_lock, timeout=1.0) as acquired:
            self.assertTrue(acquired)
            result = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True,
                timeout=5, check=True,
            )
            self.assertEqual(result.stdout.strip(), "busy")
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            timeout=5, check=True,
        )
        self.assertEqual(result.stdout.strip(), "locked")


class TrackerStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.state = telemetry_common._empty_state()

    def test_foreign_skill_tool_is_ignored(self):
        payload = {
            "tool_name": "Skill",
            "tool_input": {"skill": "some-other-plugin"},
            "cwd": "C:/project",
        }
        tracker.handle_pre(
            self.state, payload, "wf-session", "anon-test", "session")
        self.assertEqual(self.state["workflows"], [])
        self.assertEqual(self.state["invocations"], [])

    def test_plugin_skill_tool_is_recorded(self):
        payload = {
            "tool_name": "Skill",
            "tool_input": {"skill": "avatar-grill"},
            "cwd": "C:/project",
        }
        tracker.handle_pre(
            self.state, payload, "wf-session", "anon-test", "session")
        self.assertEqual(len(self.state["invocations"]), 1)
        self.assertEqual(self.state["invocations"][0]["skill_name"],
                         "avatar-grill")
        self.assertEqual(self.state["invocations"][0]["source"], "skill_tool")

    def test_invocation_is_deduplicated_per_workflow_and_skill(self):
        tracker.record_invocation(
            self.state, "wf-1", "avatar-grill", "anon-test", "read")
        tracker.record_invocation(
            self.state, "wf-1", "avatar-grill", "anon-test", "skill_tool")
        self.assertEqual(len(self.state["invocations"]), 1)
        item = self.state["invocations"][0]
        self.assertNotIn("hit_count", item)
        self.assertEqual(item["source"], "read")

    def test_prompt_text_is_not_stored_in_workflow(self):
        payload = {
            "session_id": "session",
            "cwd": "C:/project",
            "prompt": "做虚拟人 apiKey=secret C:\\Users\\name\\private",
        }
        tracker.handle_prompt(
            self.state, payload, "wf-session", "anon-test", "session")
        item = self.state["workflows"][0]
        self.assertNotIn("first_prompt", item)

    def test_contract_task_kind_sets_backend_workflow_type(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".avatar").mkdir()
            (root / ".avatar" / "avatar-run-contract.json").write_text(
                json.dumps({"task": {"kind": "knowledge_base"}}),
                encoding="utf-8",
            )
            self.state["workflows"].append(workflow(
                "wf-1", workflow_type=None, cwd=str(root)
            ))
            tracker.maybe_set_type_from_contract(self.state, "wf-1")
            self.assertEqual(
                self.state["workflows"][0]["workflow_type"], "knowledge_base"
            )

    def test_recent_interrupted_workflow_is_resumed_across_sessions(self):
        recent = telemetry_common.now_iso()
        self.state["workflows"].append(workflow(
            "wf-old", status="interrupted", updated_at=recent,
            ended_at=recent, cwd="C:/same",
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-new-session", "anon-test", True, "C:/same",
            "new-session",
        )
        self.assertEqual(result, "wf-old")
        self.assertEqual(self.state["workflows"][0]["status"], "in_progress")
        self.assertEqual(self.state["workflows"][0]["revision"], 2)

    def test_old_interrupted_workflow_is_not_resumed(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=6)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z")
        self.state["workflows"].append(workflow(
            "wf-old", status="interrupted", updated_at=old,
            ended_at=old, cwd="C:/same",
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-new-session", "anon-test", True, "C:/same",
            "new-session",
        )
        self.assertEqual(result, "wf-new-session")
        self.assertEqual(len(self.state["workflows"]), 2)

    def test_completed_workflow_forks_instead_of_regressing(self):
        self.state["workflows"].append(workflow(
            "wf-session", status="completed",
            completion_method="verification_flag",
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-session", "anon-test", True, "C:/project",
            "session",
        )
        self.assertNotEqual(result, "wf-session")
        self.assertEqual(self.state["workflows"][0]["status"], "completed")
        self.assertEqual(len(self.state["workflows"]), 2)

    def test_single_grill_entry_does_not_switch_primary_workflow(self):
        self.state["workflows"].append(workflow(
            "wf-1", workflow_type="web_template"))
        result = tracker.route_workflow_for_skill(
            self.state, "wf-1", "session", "avatar-grill",
            "anon-test", "C:/project",
        )
        self.assertEqual(result, "wf-1")
        self.assertEqual(self.state["workflows"][0]["status"], "in_progress")
        self.assertEqual(len(self.state["workflows"]), 1)

    def test_failed_completion_evidence_is_terminal_failure(self):
        self.state["workflows"].append(workflow("wf-1"))
        with mock.patch.object(
            tracker, "resolve_completion",
            return_value=("verification_flag", {"failed": True}),
        ):
            tracker.handle_end(self.state, {}, "wf-1")
        self.assertEqual(self.state["workflows"][0]["status"], "failed")

    def test_stop_scan_can_finish_same_workflow_after_repair(self):
        self.state["workflows"].append(workflow("wf-1"))
        with mock.patch.object(
            tracker, "resolve_completion",
            return_value=("verification_flag", {"ready_to_deliver": True}),
        ):
            changed = tracker.opportunistic_scan(self.state, "wf-1", {})
        item = self.state["workflows"][0]
        self.assertTrue(changed)
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["revision"], 2)


class UploadReliabilityTests(JsonStateSandbox):
    def test_ack_marks_only_the_sent_revision_uploaded(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(revision=2))
        sent = uploader.collect(state, 50)[0]
        uploader.apply_response(state, sent, [], {
            "acceptedWorkflowIds": ["wf-1"],
        })
        self.assertEqual(state["workflows"][0]["upload_status"], "uploaded")
        self.assertEqual(state["workflows"][0]["revision"], 2)

    def test_late_ack_cannot_confirm_a_new_revision(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(revision=1))
        sent = uploader.collect(state, 50)[0]
        tracker._touch_workflow(state["workflows"][0], status="completed")
        changed = uploader.apply_response(state, sent, [], {
            "acceptedWorkflowIds": ["wf-1"],
        })
        self.assertFalse(changed)
        self.assertEqual(state["workflows"][0]["revision"], 2)
        self.assertEqual(state["workflows"][0]["upload_status"], "pending")

    def test_permanent_rejection_dead_letters_matching_revision(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(revision=1))
        sent = uploader.collect(state, 50)[0]
        uploader.apply_response(state, sent, [], {
            "rejected": [{"id": "wf-1", "reason": "status_invalid"}],
        })
        self.assertEqual(state["workflows"][0]["upload_status"], "dead_letter")
        self.assertEqual(uploader.collect(state, 50)[0], [])

    def test_retryable_rejection_remains_pending(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow())
        sent = uploader.collect(state, 50)[0]
        changed = uploader.apply_response(state, sent, [], {
            "rejected": [{"id": "wf-1", "reason": "internal_error"}],
        })
        self.assertFalse(changed)
        self.assertEqual(state["workflows"][0]["upload_status"], "pending")

    def test_payload_uses_wire_v14_and_hides_private_revision(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(revision=3))
        workflows, invocations = uploader.collect(state, 50)
        payload = uploader._payload(
            {"schema_version": "1.4"}, workflows, invocations,
            {"privacyNoticeVersion": "2.1", "consentedAt": STAMP},
        )
        self.assertEqual(payload["schemaVersion"], "1.4")
        self.assertEqual(payload["workflows"][0]["revision"], 3)
        self.assertNotIn("_revision", payload["workflows"][0])
        self.assertNotIn("firstPrompt", payload["workflows"][0])

    def test_invocation_payload_does_not_send_hit_count(self):
        state = telemetry_common._empty_state()
        state["invocations"].append(invocation())
        invocations = uploader.collect(state, 50)[1]
        payload = uploader._payload(
            {"schema_version": "1.4"}, [], invocations,
            {"privacyNoticeVersion": "2.1", "consentedAt": STAMP},
        )
        self.assertNotIn("hitCount", payload["invocations"][0])

    def test_completion_detail_is_sanitized_at_upload_boundary(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(
            completion_detail={
                "source": "C:/private/result.json",
                "message": "failed at C:/private/project/file.txt",
            }))
        collected = uploader.collect(state, 50)[0][0]
        detail = json.loads(collected["completionDetail"])
        self.assertNotIn("source", detail)
        self.assertNotIn("C:/private", detail["message"])

    def test_upload_all_drains_batches_and_persists_ack(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow("wf-{}".format(i)) for i in range(3)]
        self.save(state)

        def accept(_config, payload):
            return {"data": {
                "acceptedWorkflowIds": [x["workflowId"]
                                        for x in payload["workflows"]],
                "acceptedInvocationIds": [],
                "rejected": [],
            }}

        with mock.patch.object(
            uploader, "consent_metadata",
            return_value={"privacyNoticeVersion": "2.1", "consentedAt": STAMP},
        ):
            result = uploader.upload_all(
                {"batch_size": 1, "schema_version": "1.4",
                 "endpoint": "https://example.test/report"},
                {"retry_count": 0, "last_attempt": None},
                post_fn=accept,
            )
        self.assertEqual(result, (3, 0))
        loaded = self.load()
        self.assertTrue(all(x["upload_status"] == "uploaded"
                            for x in loaded["workflows"]))
        self.assertIsNotNone(loaded["upload"]["last_ack_at"])

    def test_consent_withdrawal_prevents_network_call(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow())
        self.save(state)
        post = mock.Mock()
        with mock.patch.object(uploader, "consent_metadata", return_value=None):
            result = uploader.upload_all(
                {"batch_size": 50, "schema_version": "1.4"},
                {"retry_count": 0, "last_attempt": None}, post_fn=post)
        self.assertEqual(result, (0, 0))
        post.assert_not_called()
        self.assertEqual(self.load()["workflows"][0]["upload_status"], "pending")

    def test_network_exception_leaves_snapshot_pending(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow())
        self.save(state)
        with mock.patch.object(
            uploader, "consent_metadata",
            return_value={"privacyNoticeVersion": "2.1", "consentedAt": STAMP},
        ):
            with self.assertRaises(OSError):
                uploader.upload_all(
                    {"batch_size": 50, "schema_version": "1.4"},
                    {"retry_count": 0, "last_attempt": None},
                    post_fn=mock.Mock(side_effect=OSError("offline")),
                )
        self.assertEqual(self.load()["workflows"][0]["upload_status"], "pending")


class ReporterTests(JsonStateSandbox):
    def test_gate_report_keeps_workflow_open_and_sanitizes_detail(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow())
        telemetry_common.set_active_workflow(state, "session", "wf-1")
        self.save(state)
        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(telemetry, "_resolve_session",
                                  return_value=("session", "C:/project")), \
                mock.patch.object(telemetry, "spawn_uploader"):
            changed, reason = telemetry.report_gate(
                "first_frame", "failed", ["C:/private/screenshot.png"],
                session_id="session")
        item = self.load()["workflows"][0]
        self.assertTrue(changed)
        self.assertEqual(reason, "reported")
        self.assertEqual(item["status"], "in_progress")
        self.assertNotIn("C:/private", json.dumps(item["completion_detail"]))

    def test_purge_removes_only_old_acknowledged_workflows(self):
        old = (datetime.now(timezone.utc) - timedelta(days=8)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z")
        state = telemetry_common._empty_state()
        state["workflows"] = [
            workflow("wf-old", started_at=old, upload_status="uploaded"),
            workflow("wf-pending", started_at=old, upload_status="pending"),
        ]
        state["invocations"] = [invocation("inv-old", "wf-old")]
        self.save(state)
        removed = telemetry.purge_old(days=7)
        self.assertEqual(removed, 1)
        loaded = self.load()
        self.assertEqual([x["workflow_id"] for x in loaded["workflows"]],
                         ["wf-pending"])
        self.assertEqual(loaded["invocations"], [])


if __name__ == "__main__":
    unittest.main()
