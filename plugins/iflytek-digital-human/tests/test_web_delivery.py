import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PLUGIN_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import web_delivery
import web_runtime_evidence
import web_sdk_gate
import platform_endpoints
import websocket_auth
import write_env_safe
import xfyun_interface


VALID_ENV = "\n".join(
    (
        "APP_ID=542c98ba",
        "API_KEY=1234567890abcdef1234567890abcdef",
        "API_SECRET=1234567890abcdef1234567890abcdef",
        "SCENE_ID=335328879436763136",
        "AVATAR_ID=111310001",
        "VCN=x4_lingxiaoqi_oral",
        "WS_URL=wss://avatar.cn-huadong-1.xf-yun.com/v1/interact",
    )
) + "\n"


class WriteEnvWebProfileTests(unittest.TestCase):
    def test_web_sdk_profile_matches_node_server_names(self):
        content = write_env_safe.build_env_content(
            "app", "key", "secret", "scene", profile="web-sdk"
        )
        self.assertIn("APP_ID=app", content)
        self.assertIn("API_KEY=key", content)
        self.assertIn("API_SECRET=secret", content)
        self.assertIn("WS_URL=wss://avatar.cn-huadong-1.xf-yun.com", content)
        self.assertNotIn("XF_API_KEY", content)

    def test_ws_url_has_one_canonical_source(self):
        self.assertEqual(
            write_env_safe.DEFAULT_WS_URL,
            platform_endpoints.CANONICAL_WS_URL,
        )

    def test_interface_tool_uses_the_canonical_ws_url_source(self):
        source = (TOOLS_DIR / "xfyun_interface.py").read_text(encoding="utf-8")
        self.assertIn(
            "from platform_endpoints import CANONICAL_WS_URL",
            source,
        )
        self.assertEqual(xfyun_interface.SERVER_URL, platform_endpoints.CANONICAL_WS_URL)


class WebDeliveryTests(unittest.TestCase):
    def test_requested_port_is_not_limited_to_default_scan_window(self):
        with mock.patch.object(web_delivery, "_port_is_free", return_value=True):
            self.assertEqual(web_delivery._choose_initial_port(24120), 24120)

    def test_busy_requested_port_is_blocked_without_fallback(self):
        with mock.patch.object(web_delivery, "_port_is_free", return_value=False):
            with self.assertRaises(RuntimeError):
                web_delivery._choose_initial_port(24120)

    def make_project(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "server.js").write_text(
            "import { avatarAuthHandler, avatarConfigHandler } from './xfyun-auth.mjs';\n"
            "app.get('/api/config', avatarConfigHandler);\n"
            "app.get('/api/avatar-auth', avatarAuthHandler);\n",
            encoding="utf-8",
        )
        return temporary, root

    def test_prepare_orders_credentials_before_sdk_and_server(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        calls = []

        def write_env(_app, _scene, path, profile=None):
            calls.append("credentials")
            self.assertEqual(profile, "web-sdk")
            Path(path).write_text(VALID_ENV, encoding="utf-8")
            return True

        def ensure(_platform, _project):
            calls.append("sdk")
            return {"artifact_status": "ready"}

        def start(project, port, fingerprint):
            calls.append("server")
            return {
                "schema_version": 1,
                "project": str(project),
                "pid": 123,
                "port": port,
                "credential_fingerprint": fingerprint,
            }

        with mock.patch.object(web_delivery.write_env_safe, "write_env", write_env), \
             mock.patch.object(web_delivery.sdk_artifact, "ensure_artifact", ensure), \
             mock.patch.object(web_delivery, "_choose_initial_port", return_value=3001), \
             mock.patch.object(web_delivery, "_start_server", start), \
             mock.patch.object(web_delivery, "_server_health", return_value=(True, [])), \
             mock.patch.object(web_delivery, "_managed_process_alive", return_value=False), \
             mock.patch.object(
                 web_delivery.telemetry, "report_gate", return_value=(True, "reported")
             ) as report_gate:
            code = web_delivery.prepare(
                root,
                app_id="542c98ba",
                scene_id="335328879436763136",
                open_browser=False,
            )

        self.assertEqual(code, 3)
        self.assertEqual(calls, ["credentials", "sdk", "server"])
        state = json.loads(
            (root / ".runtime" / "web-delivery.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["port"], 3001)
        self.assertEqual(state["phase"], "awaiting_runtime_verification")
        self.assertNotIn("API_KEY", json.dumps(state))
        marker = json.loads(
            (root / ".runtime" / "verification-result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marker["next_action"]["action"], "run_web_runtime_evidence")
        self.assertIn("web_runtime_evidence.py", marker["next_action"]["commands"][0])
        report_gate.assert_called_once_with(
            "web_delivery",
            "awaiting_runtime_verification",
            ["connected", "stream_start", "first_frame", "text"],
            project_dir=root,
            workflow_id=None,
        )
        self.assertEqual(state["project_fingerprint"], web_sdk_gate.project_fingerprint(root))

    def test_runtime_evidence_requires_matching_prepared_context(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        project_fingerprint = "project-fp"
        evidence = {
            "source": "playwright",
            "prepared_at_epoch": 123,
            "credential_fingerprint": "fp",
            "project_fingerprint": project_fingerprint,
            "url": "http://127.0.0.1:3001",
            "target_interaction": "text",
            "connected": True,
            "stream_start": True,
            "first_frame": True,
            "target_interaction_passed": True,
        }
        runtime = root / ".runtime"
        runtime.mkdir(exist_ok=True)
        (runtime / "web-runtime-evidence.json").write_text(
            json.dumps(evidence),
            encoding="utf-8",
        )

        self.assertTrue(web_delivery._runtime_evidence_is_fresh(
            root, 123, "http://127.0.0.1:3001", "fp", "text", project_fingerprint
        ))
        self.assertFalse(web_delivery._runtime_evidence_is_fresh(
            root, 123, "http://127.0.0.1:3002", "fp", "text", project_fingerprint
        ))
        self.assertFalse(web_delivery._runtime_evidence_is_fresh(
            root, 123, "http://127.0.0.1:3001", "other", "text", project_fingerprint
        ))
        self.assertFalse(web_delivery._runtime_evidence_is_fresh(
            root, 123, "http://127.0.0.1:3001", "fp", "text", "other-project"
        ))

    def test_canonical_auth_module_is_hash_verified(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        websocket_auth.install(root)
        self.assertEqual(websocket_auth.verify_installation(root), [])
        module = root / websocket_auth.MODULE_NAME
        module.write_text(module.read_text(encoding="utf-8") + "\n// changed", encoding="utf-8")
        self.assertEqual(
            websocket_auth.verify_installation(root),
            ["canonical_auth_module_modified"],
        )

    def test_wrong_ws_host_or_path_is_rejected(self):
        values = {
            "APP_ID": "542c98ba",
            "API_KEY": "1234567890abcdef1234567890abcdef",
            "API_SECRET": "1234567890abcdef1234567890abcdef",
            "SCENE_ID": "335328879436763136",
            "AVATAR_ID": "111310001",
            "VCN": "x4_lingxiaoqi_oral",
            "WS_URL": "wss://avatar.xfyun.cn/v1/private/dh",
        }
        self.assertEqual(
            websocket_auth.credential_issues(values),
            ["credential_invalid:ws_url"],
        )
        values["WS_URL"] = "wss://avatar.xfyun.cn/v1/interact"
        self.assertEqual(
            websocket_auth.credential_issues(values),
            ["credential_invalid:ws_url"],
        )

    def test_pid_alive_accepts_current_process(self):
        import os

        self.assertTrue(web_delivery._pid_alive(os.getpid()))

    def test_pid_alive_rejects_missing_process(self):
        self.assertFalse(web_delivery._pid_alive(2**31 - 1))

    def test_pid_alive_converts_system_error_to_false(self):
        with mock.patch.object(web_delivery.os, "kill", side_effect=SystemError("invalid pid")):
            self.assertFalse(web_delivery._pid_alive(123))

    def test_generated_node_auth_module_locks_the_canonical_ws_url(self):
        self.assertIn(
            platform_endpoints.CANONICAL_WS_URL,
            websocket_auth.MODULE_SOURCE,
        )
        self.assertIn("wsUrl !== CANONICAL_WS_URL", websocket_auth.MODULE_SOURCE)

    def test_blocked_credentials_reports_gate_and_returns_deterministic_next_action(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)

        with mock.patch.object(
            web_delivery.telemetry, "report_gate", return_value=(True, "reported")
        ) as report_gate, mock.patch("builtins.print") as output:
            code = web_delivery._blocked(
                root,
                "blocked_missing_credentials",
                ["credential_missing:app_id", "app_id_and_scene_id_required"],
            )

        self.assertEqual(code, 2)
        report_gate.assert_called_once_with(
            "web_delivery",
            "blocked_missing_credentials",
            ["credential_missing:app_id", "app_id_and_scene_id_required"],
            project_dir=root,
            workflow_id=None,
        )
        payload = json.loads(output.call_args.args[0])
        self.assertEqual(payload["next_action"]["action"], "run_avatar_credentials")
        self.assertTrue(payload["next_action"]["required"])
        self.assertIn("xfyun_common.py", payload["next_action"]["commands"][0])
        self.assertIn("xfyun_query_services.py", payload["next_action"]["commands"][1])

    def test_xf_prefixed_env_is_not_accepted_for_node_profile(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        (root / ".env").write_text(
            VALID_ENV.replace("APP_ID=", "XF_APP_ID=")
            .replace("API_KEY=", "XF_API_KEY=")
            .replace("API_SECRET=", "XF_API_SECRET=")
            .replace("SCENE_ID=", "XF_SCENE_ID=")
            .replace("AVATAR_ID=", "XF_AVATAR_ID=")
            .replace("VCN=", "XF_VCN=")
            .replace("WS_URL=", "XF_WS_URL="),
            encoding="utf-8",
        )
        self.assertEqual(
            web_delivery._credential_issues(root),
            ["credential_profile_mismatch:web-sdk"],
        )

    def test_waiting_run_does_not_refresh_or_restart(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        web_delivery._save_state(
            root,
            {
                "phase": "awaiting_runtime_verification",
                "prepared_at_epoch": 9999999999,
                "port": 3001,
                "url": "http://127.0.0.1:3001",
                "issues": ["connected"],
                "project_fingerprint": web_sdk_gate.project_fingerprint(root),
            },
        )
        with mock.patch.object(web_delivery, "prepare") as prepare, \
             mock.patch.object(web_delivery, "_server_health", return_value=(True, [])):
            code = web_delivery.run(root, open_browser=False)
        self.assertEqual(code, 3)
        prepare.assert_not_called()

    def test_finish_never_completes_telemetry_when_gate_is_pending(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        result = {
            "status": "needs_runtime_verification",
            "ready_to_deliver": False,
            "remaining_issues": ["first_frame"],
        }
        with mock.patch.object(web_delivery, "_server_health", return_value=(True, [])), \
             mock.patch.object(web_delivery.web_sdk_gate, "run_checks", return_value=result), \
             mock.patch.object(web_delivery.telemetry, "report_complete") as complete, \
             mock.patch.object(
                 web_delivery.telemetry, "report_gate", return_value=(True, "reported")
             ) as report_gate:
            code = web_delivery.finish(root)
        self.assertEqual(code, 3)
        complete.assert_not_called()
        report_gate.assert_called_once_with(
            "web_delivery",
            "needs_runtime_verification",
            ["first_frame"],
            project_dir=root,
            workflow_id=None,
        )

    def test_finish_completes_telemetry_only_after_ready_gate(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        result = {
            "status": "ready_to_deliver",
            "ready_to_deliver": True,
            "remaining_issues": [],
        }
        with mock.patch.object(web_delivery, "_server_health", return_value=(True, [])), \
             mock.patch.object(web_delivery.web_sdk_gate, "run_checks", return_value=result), \
             mock.patch.object(
                 web_delivery.telemetry,
                 "report_complete",
                 return_value=(True, "verification_flag"),
             ) as complete:
            code = web_delivery.finish(root)
        self.assertEqual(code, 0)
        complete.assert_called_once_with(
            workflow_type="sdk_integration",
            project_dir=root,
            workflow_id=None,
        )

    def test_node_runner_forces_utf8_decoding_on_windows(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        options = {
            "url": "http://127.0.0.1:3001",
            "interaction": "text",
            "text": "你好",
            "timeoutMs": 30000,
            "viewportWidth": 1440,
            "viewportHeight": 1200,
            "preparedAtEpoch": 1,
            "credentialFingerprint": "cred",
            "projectFingerprint": "project",
        }
        with mock.patch.object(
            web_runtime_evidence.subprocess,
            "run",
            return_value=mock.Mock(returncode=0, stdout="{}", stderr=""),
        ) as run:
            web_runtime_evidence._run_node(root, options)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_node_syntax_check_forces_utf8_decoding_on_windows(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        with mock.patch.object(
            web_sdk_gate.subprocess,
            "run",
            return_value=mock.Mock(returncode=0),
        ) as run:
            ok, reason = web_sdk_gate._default_node_check(root / "server.js")
        self.assertTrue(ok)
        self.assertIsNone(reason)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_project_fingerprint_ignores_unrelated_favicon_mtime(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        (root / ".env").write_text(VALID_ENV, encoding="utf-8")
        (root / "public").mkdir()
        (root / "public" / "app.js").write_text("console.log('ok')\n", encoding="utf-8")
        (root / "favicon.ico").write_bytes(b"one")
        before = web_sdk_gate.project_fingerprint(root)
        (root / "favicon.ico").write_bytes(b"two")
        self.assertEqual(before, web_sdk_gate.project_fingerprint(root))

    def test_project_fingerprint_changes_for_runtime_source_content(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        (root / "public").mkdir()
        app = root / "public" / "app.js"
        app.write_text("console.log('one')\n", encoding="utf-8")
        before = web_sdk_gate.project_fingerprint(root)
        app.write_text("console.log('two')\n", encoding="utf-8")
        self.assertNotEqual(before, web_sdk_gate.project_fingerprint(root))

    def test_gate_uses_fingerprint_instead_of_static_mtime_for_runtime_evidence(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        runtime = root / ".runtime"
        runtime.mkdir(exist_ok=True)
        fingerprint = web_sdk_gate.project_fingerprint(root)
        (runtime / "web-delivery.json").write_text(json.dumps({
            "prepared_at_epoch": 123,
            "url": "http://127.0.0.1:3001",
            "credential_fingerprint": "cred",
            "project_fingerprint": fingerprint,
        }), encoding="utf-8")
        (runtime / "web-runtime-evidence.json").write_text(json.dumps({
            "source": "playwright",
            "prepared_at_epoch": 123,
            "credential_fingerprint": "cred",
            "project_fingerprint": fingerprint,
            "url": "http://127.0.0.1:3001",
            "target_interaction": "text",
            "connected": True,
            "stream_start": True,
            "first_frame": True,
            "target_interaction_passed": True,
            "errors": [],
        }), encoding="utf-8")
        self.assertEqual(web_sdk_gate._runtime_issues(root, "text", fingerprint), [])
        self.assertIn(
            "runtime_evidence_stale",
            web_sdk_gate._runtime_issues(root, "text", "changed"),
        )

    def test_workflow_id_is_stored_and_used_for_delivery_reports(self):
        temporary, root = self.make_project()
        self.addCleanup(temporary.cleanup)
        result = {
            "status": "ready_to_deliver",
            "ready_to_deliver": True,
            "remaining_issues": [],
        }
        web_delivery._save_state(root, {"workflow_id": "wf-test"})
        with mock.patch.object(web_delivery, "_server_health", return_value=(True, [])), \
             mock.patch.object(web_delivery.web_sdk_gate, "run_checks", return_value=result), \
             mock.patch.object(
                 web_delivery.telemetry,
                 "report_complete",
                 return_value=(True, "verification_flag"),
             ) as complete:
            code = web_delivery.finish(root)
        self.assertEqual(code, 0)
        complete.assert_called_once_with(
            workflow_type="sdk_integration",
            project_dir=root,
            workflow_id="wf-test",
        )

    def test_workflow_id_prefers_cli_then_environment_then_state(self):
        with mock.patch.dict(
            web_delivery.os.environ,
            {"IFLYTEK_DIGITAL_HUMAN_WORKFLOW_ID": "wf-env"},
        ):
            self.assertEqual(
                web_delivery._resolve_workflow_id("wf-cli", {"workflow_id": "wf-state"}),
                "wf-cli",
            )
            self.assertEqual(
                web_delivery._resolve_workflow_id(None, {"workflow_id": "wf-state"}),
                "wf-env",
            )
        self.assertEqual(
            web_delivery._resolve_workflow_id(None, {"workflow_id": "wf-state"}),
            "wf-state",
        )

    def test_auth_script_recomputes_the_signed_url_from_env_values(self):
        values = {
            "APP_ID": "542c98ba",
            "API_KEY": "1234567890abcdef1234567890abcdef",
            "API_SECRET": "1234567890abcdef1234567890abcdef",
            "SCENE_ID": "335328879436763136",
            "AVATAR_ID": "111310001",
            "VCN": "x4_lingxiaoqi_oral",
            "WS_URL": "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact",
        }
        date = "Thu, 06 Aug 2026 10:00:00 GMT"
        url = websocket_auth.generate_signed_url(values, date)
        self.assertEqual(websocket_auth.signed_url_issues(url, values), [])
        wrong_secret = dict(values)
        wrong_secret["API_SECRET"] = "fedcba0987654321fedcba0987654321"
        self.assertIn(
            "signed_url_signature_mismatch",
            websocket_auth.signed_url_issues(url, wrong_secret),
        )


if __name__ == "__main__":
    unittest.main()
