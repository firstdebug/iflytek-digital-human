"""JSON-state telemetry lifecycle and reliability tests."""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "claude" / "iflytek-digital-human"
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
        "xfyun_user_id": "xf-test",
        "agent": "claude",
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
        "skill_name": "avatar-workflow-entry",
        "xfyun_user_id": "xf-test",
        "agent": "claude",
        "source": "read",
        "first_at": STAMP,
        "last_at": STAMP,
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
        self.state_backup = self.telemetry_dir / "state.backup.json"
        self.state_lock = self.telemetry_dir / "state.lock"
        self.uploader_lock = self.telemetry_dir / "uploader.lock"
        self.patches = [
            mock.patch.multiple(
                telemetry_common,
                TELEMETRY_DIR=self.telemetry_dir,
                STATE_PATH=self.state_path,
                STATE_BACKUP_PATH=self.state_backup,
                STATE_LOCK_PATH=self.state_lock,
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
    def test_legacy_anonymous_identity_is_removed_without_creating_id_file(self):
        legacy = {
            "anonymous_id": "anon_root",
            "workflows": [workflow(anonymous_id="anon_workflow")],
            "invocations": [invocation(anonymous_id="anon_invocation")],
        }

        state = telemetry_common._normalize_state(legacy)

        self.assertNotIn("anonymous_id", state)
        self.assertNotIn("anonymous_id", state["workflows"][0])
        self.assertNotIn("anonymous_id", state["invocations"][0])
        self.assertFalse((self.telemetry_dir / "anonymous_id.json").exists())

    def test_session_request_stats_keep_only_twenty_most_recent_sessions(self):
        state = telemetry_common._empty_state()
        state["session_request_stats"] = {
            "session-{:02d}".format(index): {
                "platform_ok": index,
                "telemetry_post": 0,
                "telemetry_post_fail": 0,
                "updated_at": "2026-08-27T00:{:02d}:00.000Z".format(index),
            }
            for index in range(25)
        }

        normalized = telemetry_common._normalize_state(state)

        self.assertEqual(len(normalized["session_request_stats"]), 20)
        self.assertNotIn("session-00", normalized["session_request_stats"])
        self.assertIn("session-24", normalized["session_request_stats"])

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
        self.assertNotIn("revision", loaded["invocations"][0])
        self.assertEqual(loaded["workflows"][0]["xfyun_user_id"], "xf_old")

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

    def test_skill_tool_is_ignored(self):
        payload = {
            "tool_name": "Skill",
            "tool_input": {"skill": "avatar-executing"},
            "cwd": "C:/project",
        }
        tracker.handle_pre(self.state, payload, "wf-session", "session")
        self.assertEqual(self.state["workflows"], [])
        self.assertEqual(self.state["invocations"], [])

    def test_invocation_is_deduplicated_per_workflow_and_skill(self):
        tracker.record_invocation(
            self.state, "wf-1", "avatar-executing", "read")
        tracker.record_invocation(
            self.state, "wf-1", "avatar-executing", "slash")
        self.assertEqual(len(self.state["invocations"]), 1)
        item = self.state["invocations"][0]
        self.assertNotIn("hit_count", item)
        self.assertEqual(item["source"], "read")

    def test_natural_avatar_prompt_does_not_create_workflow(self):
        payload = {
            "session_id": "session",
            "cwd": "C:/project",
            "prompt": "做虚拟人 apiKey=secret C:\\Users\\name\\private",
        }
        tracker.handle_prompt(self.state, payload, "wf-session", "session")
        self.assertEqual(self.state["workflows"], [])

    def test_weak_avatar_word_does_not_create_workflow(self):
        payload = {
            "session_id": "session",
            "cwd": "C:/project",
            "prompt": "update my avatar image",
        }
        tracker.handle_prompt(self.state, payload, "wf-session", "session")
        self.assertEqual(self.state["workflows"], [])

    def test_recent_interrupted_workflow_is_resumed_across_sessions(self):
        recent = telemetry_common.now_iso()
        self.state["workflows"].append(workflow(
            "wf-old", status="interrupted", updated_at=recent,
            ended_at=recent, cwd="C:/same",
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-new-session", signal=True, cwd="C:/same",
            session_id="new-session",
        )
        self.assertEqual(result, "wf-old")
        self.assertEqual(self.state["workflows"][0]["status"], "in_progress")
        self.assertEqual(self.state["workflows"][0]["revision"], 2)

    def test_in_progress_workflow_is_not_resumed_by_a_new_session(self):
        recent = telemetry_common.now_iso()
        self.state["workflows"].append(workflow(
            "wf-old", status="in_progress", updated_at=recent,
            cwd="C:/same",
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-new-session", signal=True, cwd="C:/same",
            session_id="new-session",
        )
        self.assertEqual(result, "wf-new-session")
        self.assertEqual(len(self.state["workflows"]), 2)

    def test_home_directory_workflow_is_not_resumed_across_sessions(self):
        recent = telemetry_common.now_iso()
        home = str(Path.home())
        self.state["workflows"].append(workflow(
            "wf-old", status="interrupted", updated_at=recent,
            ended_at=recent, cwd=home,
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-new-session", signal=True, cwd=home,
            session_id="new-session",
        )
        self.assertEqual(result, "wf-new-session")
        self.assertEqual(len(self.state["workflows"]), 2)

    def test_same_session_refines_home_cwd_to_project_directory(self):
        home = str(Path.home())
        project = str(Path.home() / "avatar-voice-web")
        self.state["workflows"].append(workflow("wf-session", cwd=home))
        telemetry_common.set_active_workflow(
            self.state, "session", "wf-session")

        result = tracker.ensure_workflow(
            self.state, "wf-session", signal=True, cwd=project,
            session_id="session",
        )

        self.assertEqual(result, "wf-session")
        self.assertEqual(self.state["workflows"][0]["cwd"], project)

    def test_old_interrupted_workflow_is_not_resumed(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=6)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z")
        self.state["workflows"].append(workflow(
            "wf-old", status="interrupted", updated_at=old,
            ended_at=old, cwd="C:/same",
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-new-session", signal=True, cwd="C:/same",
            session_id="new-session",
        )
        self.assertEqual(result, "wf-new-session")
        self.assertEqual(len(self.state["workflows"]), 2)

    def test_completed_workflow_forks_instead_of_regressing(self):
        self.state["workflows"].append(workflow(
            "wf-session", status="completed",
            completion_method="verification_flag",
        ))
        result = tracker.ensure_workflow(
            self.state, "wf-session", signal=True, cwd="C:/project",
            session_id="session",
        )
        self.assertNotEqual(result, "wf-session")
        self.assertEqual(self.state["workflows"][0]["status"], "completed")
        self.assertEqual(len(self.state["workflows"]), 2)

    def test_primary_intent_switch_cancels_old_and_starts_new(self):
        self.state["workflows"].append(workflow(
            "wf-1", workflow_type="web_template"))
        result = tracker.route_workflow_for_skill(
            self.state, "wf-1", "session", "avatar-executing", "C:/project",
        )
        self.assertNotEqual(result, "wf-1")
        self.assertEqual(self.state["workflows"][0]["status"], "cancelled")
        self.assertEqual(self.state["workflows"][1]["workflow_type"],
                         "sdk_integration")

    def test_primary_skill_reuses_workflow_started_by_auxiliary_skill(self):
        self.state["workflows"].append(workflow(
            "wf-1", workflow_type="credentials_setup"))
        result = tracker.route_workflow_for_skill(
            self.state, "wf-1", "session", "avatar-executing", "C:/project",
        )
        self.assertEqual(result, "wf-1")
        self.assertEqual(self.state["workflows"][0]["status"], "in_progress")
        self.assertEqual(self.state["workflows"][0]["workflow_type"],
                         "sdk_integration")

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

    def test_payload_hides_private_revision_and_omits_protocol_fields(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(revision=3))
        state["session_request_stats"] = {
            "session": {"platform_ok": 3, "telemetry_post": 2,
                        "telemetry_post_fail": 1}
        }
        workflows, invocations = uploader.collect(state, 50)
        payload = uploader._payload(
            {}, workflows, invocations,
        )
        self.assertNotIn("schemaVersion", payload)
        self.assertNotIn("privacyNoticeVersion", payload)
        self.assertNotIn("consentedAt", payload)
        self.assertEqual(payload["workflows"][0]["revision"], 3)
        self.assertNotIn("_revision", payload["workflows"][0])
        self.assertNotIn("firstPrompt", payload["workflows"][0])
        self.assertNotIn("hasAvatarSignal", payload["workflows"][0])
        self.assertNotIn("session_request_stats", payload)

    def test_telemetry_rows_and_payload_identify_claude_agent(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(agent="claude"))
        state["invocations"].append(invocation(agent="claude"))

        workflows, invocations = uploader.collect(state, 50)
        payload = uploader._payload({}, workflows, invocations)

        self.assertEqual(payload["agent"], "claude")
        self.assertEqual(payload["workflows"][0]["agent"], "claude")
        self.assertEqual(payload["invocations"][0]["agent"], "claude")

    def test_invocation_payload_does_not_send_hit_count(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(
            workflow_id="wf-1",
            workflow_type="live_streaming",
        ))
        state["invocations"].append(invocation(workflow_id="wf-1"))
        invocations = uploader.collect(state, 50)[1]
        payload = uploader._payload(
            {}, uploader.collect(state, 50)[0], invocations,
        )
        self.assertNotIn("hitCount", payload["invocations"][0])
        self.assertNotIn("revision", payload["invocations"][0])

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

        with mock.patch.object(uploader, "can_upload", return_value=True):
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
        with mock.patch.object(uploader, "can_upload", return_value=False):
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
        with mock.patch.object(uploader, "can_upload", return_value=True):
            with self.assertRaises(OSError):
                uploader.upload_all(
                    {"batch_size": 50, "schema_version": "1.4"},
                    {"retry_count": 0, "last_attempt": None},
                    post_fn=mock.Mock(side_effect=OSError("offline")),
                )
        self.assertEqual(self.load()["workflows"][0]["upload_status"], "pending")

    def test_server_rejection_is_retryable(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow()]
        self.save(state)
        with mock.patch.object(uploader, "can_upload", return_value=True):
            with self.assertRaises(uploader.RetryableUploadError):
                uploader.upload_all(
                    {"batch_size": 50},
                    {"retry_count": 0, "last_attempt": None},
                    post_fn=lambda _config, _payload: {
                        "flag": False, "code": 90003, "data": None,
                    },
                )
        self.assertEqual(self.load()["workflows"][0]["upload_status"], "pending")


class ReporterTests(JsonStateSandbox):
    def test_web_template_without_fresh_artifact_stays_in_progress(self):
        unrelated = self.root / "unrelated"
        artifact = unrelated / ".runtime" / "artifacts.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text(json.dumps({
            "template_url": "https://example.test/wrong-project",
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-template", workflow_type="web_template",
            cwd=str(self.root / "template-project"))]
        telemetry_common.set_active_workflow(
            state, "session-template", "wf-template")
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(
                    telemetry, "read_current_session",
                    return_value=("other-session", str(unrelated))):
            changed, reason = telemetry.report_complete(
                session_id="session-template", workflow_type="web_template")

        item = self.load()["workflows"][0]
        self.assertFalse(changed)
        self.assertEqual(reason, "needs_template_artifact")
        self.assertEqual(item["status"], "in_progress")
        self.assertIsNone(item["completion_method"])

    def test_web_template_with_scene_id_but_no_url_stays_in_progress(self):
        project = self.root / "template-project"
        artifact = project / ".runtime" / "artifacts.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text(json.dumps({"scene_id": "scene-only"}),
                            encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-template", workflow_type="web_template", cwd=str(project))]
        telemetry_common.set_active_workflow(
            state, "session-template", "wf-template")
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                session_id="session-template", workflow_type="web_template")

        item = self.load()["workflows"][0]
        self.assertFalse(changed)
        self.assertEqual(reason, "needs_template_artifact")
        self.assertEqual(item["status"], "in_progress")

    def test_non_product_workflow_types_allow_explicit_completion(self):
        relaxed_types = (
            "credentials_setup", "live_streaming", "webapi_protocol",
            "knowledge_base", "troubleshoot", "model_config",
            "config_authoring",
        )
        for index, workflow_type in enumerate(relaxed_types):
            with self.subTest(workflow_type=workflow_type):
                workflow_id = "wf-relaxed-{}".format(index)
                session_id = "session-relaxed-{}".format(index)
                state = telemetry_common._empty_state()
                state["workflows"] = [workflow(
                    workflow_id, workflow_type=workflow_type,
                    cwd=str(self.root))]
                telemetry_common.set_active_workflow(
                    state, session_id, workflow_id)
                self.save(state)

                with mock.patch.object(
                        telemetry, "is_enabled", return_value=True):
                    changed, reason = telemetry.report_complete(
                        session_id=session_id, workflow_type=workflow_type)

                item = self.load()["workflows"][0]
                self.assertTrue(changed)
                self.assertEqual(reason, "reported")
                self.assertEqual(item["status"], "completed")

    def test_completed_workflow_change_triggers_async_upload(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-complete-flush", workflow_type="webapi_protocol",
            cwd=str(self.root))]
        telemetry_common.set_active_workflow(
            state, "session-complete-flush", "wf-complete-flush")
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(telemetry, "spawn_uploader") as spawn:
            changed, reason = telemetry.report_complete(
                session_id="session-complete-flush",
                workflow_type="webapi_protocol")

        self.assertTrue(changed)
        self.assertEqual(reason, "reported")
        spawn.assert_called_once_with(force=True)

    def test_skipped_completion_does_not_trigger_async_upload(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow("wf-complete", status="completed")]
        telemetry_common.set_active_workflow(state, "session-complete", "wf-complete")
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(telemetry, "spawn_uploader") as spawn:
            changed, reason = telemetry.report_complete(
                session_id="session-complete",
                workflow_type="sdk_integration")

        self.assertFalse(changed)
        self.assertEqual(reason, "workflow_not_in_progress")
        spawn.assert_not_called()

    def test_gate_report_change_triggers_async_upload(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow("wf-gate-flush", cwd="C:/project")]
        telemetry_common.set_active_workflow(state, "session-gate-flush",
                                             "wf-gate-flush")
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(telemetry, "spawn_uploader") as spawn:
            changed, reason = telemetry.report_gate(
                "first_frame", "failed", ["issue"],
                session_id="session-gate-flush")

        self.assertTrue(changed)
        self.assertEqual(reason, "reported")
        spawn.assert_called_once_with(force=True)

    def test_failed_workflow_change_triggers_async_upload(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-fail-flush", workflow_type="web_template", cwd=str(self.root))]
        telemetry_common.set_active_workflow(
            state, "session-fail-flush", "wf-fail-flush")
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(telemetry, "spawn_uploader") as spawn:
            changed, reason = telemetry.report_fail(
                session_id="session-fail-flush", reason="unit-test")

        self.assertTrue(changed)
        self.assertEqual(reason, "reported")
        spawn.assert_called_once_with(force=True)

    def test_complete_without_current_session_uses_unique_active_workflow(self):
        artifacts = self.root / ".runtime" / "artifacts.json"
        artifacts.parent.mkdir(parents=True)
        artifacts.write_text(json.dumps({
            "template_url": "https://example.test/avatar",
            "scene_id": "scene-1",
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-template", workflow_type=None, cwd="C:/original")]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(telemetry.os, "getcwd",
                                  return_value=str(self.root)):
            changed, reason = telemetry.report_complete(
                workflow_type="web_template")

        item = self.load()["workflows"][0]
        self.assertTrue(changed)
        self.assertEqual(reason, "artifacts_file")
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["workflow_type"], "web_template")

    def test_complete_without_explicit_session_reads_current_session(self):
        artifacts = self.root / ".runtime" / "artifacts.json"
        artifacts.parent.mkdir(parents=True)
        artifacts.write_text(json.dumps({
            "template_url": "https://example.test/avatar",
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-current", workflow_type="web_template")]
        telemetry_common.set_active_workflow(
            state, "session-current", "wf-current")
        self.save(state)
        telemetry_common.write_current_session(
            "session-current", str(self.root))

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="web_template")

        self.assertTrue(changed)
        self.assertEqual(reason, "artifacts_file")
        self.assertEqual(self.load()["workflows"][0]["status"], "completed")

    def test_complete_without_current_session_rejects_ambiguous_workflows(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [
            workflow("wf-one", workflow_type=None),
            workflow("wf-two", workflow_type="web_template"),
        ]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="web_template")

        self.assertFalse(changed)
        self.assertEqual(reason, "ambiguous_workflow")
        self.assertTrue(all(item["status"] == "in_progress"
                            for item in self.load()["workflows"]))

    def test_exact_project_report_completes_bound_workflow(self):
        project = self.root / "avatar-web-app"
        marker = project / ".runtime" / "verification-result.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({
            "ready_to_deliver": True,
            "remaining_issues": [],
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-project", cwd=str(project), workflow_type="sdk_integration")]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="sdk_integration", project_dir=project)

        item = self.load()["workflows"][0]
        self.assertTrue(changed)
        self.assertEqual(reason, "verification_flag")
        self.assertEqual(item["status"], "completed")

    def test_project_report_does_not_fall_back_to_unrelated_sdk_workflow(self):
        project = self.root / "avatar-web-app"
        marker = project / ".runtime" / "verification-result.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({
            "ready_to_deliver": True,
            "remaining_issues": [],
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-parent", cwd=str(self.root), workflow_type="sdk_integration")]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="sdk_integration", project_dir=project)

        item = self.load()["workflows"][0]
        self.assertFalse(changed)
        self.assertEqual(reason, "ambiguous_workflow")
        self.assertEqual(item["status"], "in_progress")
        self.assertEqual(item["revision"], 1)

    def test_project_report_matches_workflow_recorded_in_project_subdirectory(self):
        project = self.root / "avatar-web-app"
        marker = project / ".runtime" / "verification-result.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({
            "ready_to_deliver": True,
            "remaining_issues": [],
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-subdir", cwd=str(project / "sdk" / "esm"),
            workflow_type="webapi_protocol")]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="sdk_integration", project_dir=project)

        item = self.load()["workflows"][0]
        self.assertTrue(changed)
        self.assertEqual(reason, "verification_flag")
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["workflow_type"], "webapi_protocol")

    def test_cancelled_workflow_with_fresh_success_evidence_can_complete(self):
        project = self.root / "avatar-web-app"
        marker = project / ".runtime" / "verification-result.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({
            "ready_to_deliver": True,
            "remaining_issues": [],
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-cancelled", status="cancelled", cwd=str(project),
            workflow_type="sdk_integration")]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="sdk_integration", project_dir=project)

        item = self.load()["workflows"][0]
        self.assertTrue(changed)
        self.assertEqual(reason, "verification_flag")
        self.assertEqual(item["status"], "completed")

    def test_cancelled_workflow_without_success_evidence_stays_terminal(self):
        project = self.root / "avatar-web-app"
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow(
            "wf-cancelled", status="cancelled", cwd=str(project),
            workflow_type="sdk_integration")]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="sdk_integration", project_dir=project)

        item = self.load()["workflows"][0]
        self.assertFalse(changed)
        self.assertEqual(reason, "workflow_not_in_progress")
        self.assertEqual(item["status"], "cancelled")

    def test_project_report_stays_ambiguous_with_multiple_sdk_workflows(self):
        project = self.root / "avatar-web-app"
        marker = project / ".runtime" / "verification-result.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({
            "ready_to_deliver": True,
            "remaining_issues": [],
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [
            workflow("wf-one", cwd=str(self.root), workflow_type="sdk_integration"),
            workflow("wf-two", cwd=str(self.root / "other"), workflow_type="sdk_integration"),
        ]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="sdk_integration", project_dir=project)

        self.assertFalse(changed)
        self.assertEqual(reason, "ambiguous_workflow")
        self.assertTrue(all(item["status"] == "in_progress"
                            for item in self.load()["workflows"]))

    def test_explicit_workflow_id_completes_even_when_project_is_ambiguous(self):
        project = self.root / "avatar-web-app"
        marker = project / ".runtime" / "verification-result.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps({
            "ready_to_deliver": True,
            "remaining_issues": [],
        }), encoding="utf-8")
        state = telemetry_common._empty_state()
        state["workflows"] = [
            workflow("wf-one", cwd=str(self.root), workflow_type="sdk_integration"),
            workflow("wf-two", cwd=str(self.root / "other"),
                     workflow_type="sdk_integration"),
        ]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_complete(
                workflow_type="sdk_integration",
                project_dir=project,
                workflow_id="wf-two",
            )

        workflows = {item["workflow_id"]: item for item in self.load()["workflows"]}
        self.assertTrue(changed)
        self.assertEqual(reason, "verification_flag")
        self.assertEqual(workflows["wf-two"]["status"], "completed")
        self.assertEqual(workflows["wf-one"]["status"], "in_progress")

    def test_explicit_workflow_id_reports_gate_without_project_lookup(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [
            workflow("wf-one", cwd="C:/project"),
            workflow("wf-two", cwd="C:/other"),
        ]
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_gate(
                "web_delivery",
                "awaiting_runtime_verification",
                ["first_frame"],
                workflow_id="wf-two",
            )

        workflows = {item["workflow_id"]: item for item in self.load()["workflows"]}
        self.assertTrue(changed)
        self.assertEqual(reason, "reported")
        self.assertEqual(
            workflows["wf-two"]["completion_detail"]["gate"],
            "web_delivery",
        )
        self.assertIsNone(workflows["wf-one"]["completion_detail"])

    def test_project_scoped_report_does_not_use_global_current_session(self):
        state = telemetry_common._empty_state()
        state["workflows"] = [workflow("wf-project", cwd="C:/project")]
        self.save(state)
        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_gate(
                "first_frame", "failed", ["issue"], project_dir="C:/project")
        self.assertTrue(changed)
        self.assertEqual(reason, "reported")
        self.assertEqual(self.load()["workflows"][0]["workflow_id"], "wf-project")

    def test_gate_report_keeps_workflow_open_and_sanitizes_detail(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow())
        telemetry_common.set_active_workflow(state, "session", "wf-1")
        self.save(state)
        with mock.patch.object(telemetry, "is_enabled", return_value=True), \
                mock.patch.object(telemetry, "_resolve_session",
                                  return_value=("session", "C:/project")):
            changed, reason = telemetry.report_gate(
                "first_frame", "failed", ["C:/private/screenshot.png"],
                session_id="session")
        item = self.load()["workflows"][0]
        self.assertTrue(changed)
        self.assertEqual(reason, "reported")
        self.assertEqual(item["status"], "in_progress")
        self.assertNotIn("C:/private", json.dumps(item["completion_detail"]))

    def test_later_gate_cannot_regress_completed_workflow(self):
        state = telemetry_common._empty_state()
        state["workflows"].append(workflow(
            status="completed", completion_method="verification_flag",
            cwd="C:/project"))
        self.save(state)

        with mock.patch.object(telemetry, "is_enabled", return_value=True):
            changed, reason = telemetry.report_gate(
                "web_delivery", "authentication_failed", ["11203"],
                project_dir="C:/project")

        item = self.load()["workflows"][0]
        self.assertFalse(changed)
        self.assertEqual(reason, "workflow_not_in_progress")
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["revision"], 1)

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
