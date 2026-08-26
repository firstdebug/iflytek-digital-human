"""Privacy consent must gate every telemetry side effect."""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PLUGIN_ROOT / "tools"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(HOOKS_DIR))

import route_hint
import telemetry
import telemetry_common
import tracker
import uploader


def complete_notice():
    return {
        "notice_version": "2.1",
        "controller_name": "Example Controller",
        "recipient_name": "Example Recipient",
        "upload_endpoint": "https://telemetry.example.test/report",
        "storage_region": "China",
        "retention_days": 7,
        "contact": "privacy@example.test",
        "server_deletion_method": "Contact privacy@example.test",
        "additional_purposes": [],
    }


class ConsentSandbox(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.notice_path = self.root / "privacy_notice.json"
        self.telemetry_dir = self.root / "telemetry"
        self.path_patch = mock.patch.multiple(
            telemetry_common,
            PRIVACY_NOTICE_PATH=self.notice_path,
            TELEMETRY_DIR=self.telemetry_dir,
            STATE_PATH=self.telemetry_dir / "state.json",
            STATE_LOCK_PATH=self.telemetry_dir / "state.lock",
            ANON_ID_PATH=self.telemetry_dir / "anonymous_id.json",
            CONSENT_PATH=self.telemetry_dir / "consent.json",
            CURRENT_SESSION_PATH=self.telemetry_dir / "current_session",
        )
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def write_notice(self, notice):
        self.notice_path.write_text(json.dumps(notice), encoding="utf-8")


class ConsentStateTests(ConsentSandbox):
    def test_placeholder_notice_is_undecided_and_can_be_accepted(self):
        notice = complete_notice()
        notice["controller_name"] = "[待补充]"
        self.write_notice(notice)

        self.assertEqual(telemetry_common.consent_status(), "undecided")
        accepted, reason = telemetry_common.set_consent(True)

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")
        self.assertEqual(telemetry_common.consent_status(), "accepted")
        self.assertTrue(telemetry_common.is_enabled())
        self.assertFalse(telemetry_common.ANON_ID_PATH.exists())
        self.assertFalse(telemetry_common.STATE_PATH.exists())

    def test_old_notice_acceptance_is_stale_and_disabled(self):
        self.write_notice(complete_notice())
        self.telemetry_dir.mkdir(parents=True)
        telemetry_common.CONSENT_PATH.write_text(
            json.dumps({
                "accepted": True,
                "notice_version": "1.0",
                "decided_at": "2026-08-04T00:00:00.000Z",
            }),
            encoding="utf-8",
        )

        self.assertEqual(telemetry_common.consent_status(), "stale")
        self.assertFalse(telemetry_common.is_enabled())
        self.assertIsNone(telemetry_common.consent_metadata())

    def test_acceptance_is_bound_to_notice_and_endpoint(self):
        self.write_notice(complete_notice())

        accepted, reason = telemetry_common.set_consent(True)

        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")
        self.assertEqual(telemetry_common.consent_status(), "accepted")
        self.assertTrue(telemetry_common.is_enabled())
        self.assertTrue(telemetry_common.is_enabled(
            "https://telemetry.example.test/report"
        ))
        self.assertFalse(telemetry_common.is_enabled(
            "https://other.example.test/report"
        ))
        metadata = telemetry_common.consent_metadata()
        self.assertEqual(metadata["privacyNoticeVersion"], "2.1")
        self.assertIn("consentedAt", metadata)

    def test_decline_clears_telemetry_and_keeps_only_decision(self):
        self.write_notice(complete_notice())
        self.telemetry_dir.mkdir(parents=True)
        for name in ("state.json", "state.lock", "anonymous_id.json",
                     "current_session", "uploader.lock", "debug", "debug.log"):
            (self.telemetry_dir / name).write_text("private", encoding="utf-8")

        accepted, reason = telemetry_common.set_consent(False)

        self.assertFalse(accepted)
        self.assertEqual(reason, "declined")
        self.assertEqual(telemetry_common.consent_status(), "declined")
        remaining = {path.name for path in self.telemetry_dir.iterdir()}
        self.assertEqual(remaining, {"consent.json", "state.lock", "uploader.lock"})


class ConsentNoticeTests(ConsentSandbox):
    def test_notice_renders_explicit_opt_in_and_placeholders(self):
        notice = complete_notice()
        notice["controller_name"] = "[待补充：数据处理方名称]"
        self.write_notice(notice)

        rendered = telemetry.render_privacy_notice()

        self.assertIn("声明版本：2.1", rendered)
        self.assertIn("[待补充：数据处理方名称]", rendered)
        self.assertIn("不同意不会影响 avatar-grill 的正常功能", rendered)
        self.assertIn("沉默、继续使用插件或关闭本提示均不视为同意", rendered)
        self.assertIn("项目目录仅在本地用于工作流接续和产物验证", rendered)
        self.assertIn("对话全文和后续 Prompt 原文不会落盘或上传", rendered)
        self.assertNotIn("讯飞账号哈希", rendered)
        self.assertNotIn("进入虚拟人工作流时的首条用户请求", rendered)
        self.assertNotIn("对话和 Prompt 原文不会落盘或上传", rendered)
        self.assertIn("[同意]", rendered)
        self.assertIn("[不同意]", rendered)

    def test_entry_skill_requires_consent_before_business_routing(self):
        content = (PLUGIN_ROOT / "skills" / "avatar-grill" /
                   "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("隐私授权", content)
        self.assertIn("consent --status", content)
        self.assertIn("`undecided` 或 `stale`", content)
        notice_config = json.loads(
            (PLUGIN_ROOT / "config" / "privacy_notice.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("ready", notice_config)
        self.assertLess(content.index("隐私授权"), content.index("阶段 1"))

    def test_entry_skill_prefers_hook_status_and_only_uses_shell_as_fallback(self):
        content = (PLUGIN_ROOT / "skills" / "avatar-grill" /
                   "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("avatar-grill consent", content)
        self.assertIn("没有注入状态", content)
        self.assertIn("consent --status", content)

    def test_entry_skill_re_reads_after_accept_and_flushes_upload(self):
        content = (PLUGIN_ROOT / "skills" / "avatar-grill" /
                   "SKILL.md").read_text(encoding="utf-8")

        accept = content.index("consent --accept")
        reread = content.index("必须重新读取本入口", accept)
        flush = content.index("uploader.py\" --force", reread)
        self.assertLess(accept, reread)
        self.assertLess(reread, flush)
        self.assertIn("真实 `read` invocation", content)
        self.assertIn("不得追溯写入授权前的 prompt 或 slash", content)


class ConsentRouteHintTests(unittest.TestCase):
    def test_generic_words_do_not_trigger_avatar_route(self):
        for prompt in ("直播", "场景", "知识库", "讯飞"):
            self.assertIsNone(route_hint.build_hook_output(
                {"prompt": prompt}, status_provider=lambda: "accepted"
            ))

    def test_avatar_live_request_triggers_route(self):
        output = route_hint.build_hook_output(
            {"prompt": "创建虚拟人直播项目"}, status_provider=lambda: "accepted"
        )
        self.assertIsNotNone(output)

    def test_generic_avatar_image_request_does_not_trigger_route(self):
        output = route_hint.build_hook_output(
            {"prompt": "update my avatar image"},
            status_provider=lambda: "accepted",
        )
        self.assertIsNone(output)

    def test_avatar_context_injects_fail_closed_platform_invariants(self):
        output = route_hint.build_hook_output(
            {"prompt": "我要做 Web 虚拟人，但没有 appId 和 sceneId"},
            status_provider=lambda: "accepted",
        )

        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(output["systemMessage"], context)
        self.assertIn(
            "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact", context
        )
        self.assertIn("signedUrl", context)
        self.assertIn("authorization/date/host", context)
        self.assertNotIn("其他 host/path/query", context)
        self.assertIn("只读取当前 ${CLAUDE_PLUGIN_ROOT}", context)
        self.assertIn("禁止读取旧备份", context)
        self.assertIn("xfyun_common.py projects", context)
        self.assertIn("禁止输出或打开其他控制台地址", context)
        self.assertIn("blocked_missing_credentials", context)
        self.assertIn("退出码 2/3", context)
        self.assertIn("保持 workflow 为 in_progress", context)
        self.assertIn("只有退出码 0", context)

    def test_accepted_status_is_injected_without_repeating_consent_prompt(self):
        status = mock.Mock(return_value="accepted")

        output = route_hint.build_hook_output(
            {"prompt": "帮我构建一个虚拟人项目"}, status_provider=status
        )

        status.assert_called_once_with()
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[avatar-grill consent] status=accepted", context)
        self.assertIn("不要运行 telemetry.py consent --status", context)
        self.assertIn("不要向用户重复提示", context)

    def test_undecided_status_instructs_full_notice_and_explicit_choice(self):
        output = route_hint.build_hook_output(
            {"prompt": "创建数字人直播间"},
            status_provider=lambda: "undecided",
        )

        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[avatar-grill consent] status=undecided", context)
        self.assertIn("telemetry.py notice", context)
        self.assertIn("明确选择", context)

    def test_unrelated_prompt_does_not_read_or_inject_consent(self):
        status = mock.Mock(return_value="accepted")

        output = route_hint.build_hook_output(
            {"prompt": "帮我整理这个普通文本文件"}, status_provider=status
        )

        self.assertIsNone(output)
        status.assert_not_called()


class HookPrivacyGateTests(unittest.TestCase):
    def test_disabled_hook_does_not_inspect_or_debug_payload(self):
        payload = json.dumps({
            "session_id": "secret-session",
            "cwd": "C:/private/project",
            "prompt": "private prompt",
        }).encode("utf-8")
        stdin = io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8")

        with mock.patch.object(sys, "argv", ["tracker.py", "prompt"]):
            with mock.patch.object(sys, "stdin", stdin):
                with mock.patch.object(
                    telemetry_common, "is_enabled", return_value=False
                ):
                    with mock.patch.object(tracker, "_is_relevant") as relevant:
                        with mock.patch.object(tracker, "_debug") as debug:
                            tracker.main()

        relevant.assert_not_called()
        debug.assert_not_called()


class UploadConsentTests(unittest.TestCase):
    def test_payload_contains_consent_receipt(self):
        payload = uploader._payload(
            {"schema_version": "1.2"},
            [{"workflowId": "wf-1", "anonymousId": "anon-test"}],
            [],
            {
                "privacyNoticeVersion": "2.0",
                "consentedAt": "2026-08-06T00:00:00.000Z",
            },
        )

        self.assertEqual(payload["schemaVersion"], "1.2")
        self.assertEqual(payload["privacyNoticeVersion"], "2.0")
        self.assertEqual(payload["consentedAt"], "2026-08-06T00:00:00.000Z")

    def test_upload_stops_when_consent_is_withdrawn(self):
        post = mock.Mock()

        with mock.patch.object(uploader, "consent_metadata", return_value=None):
            uploaded = uploader.upload_all(
                {"batch_size": 50, "schema_version": "1.2"},
                {"retry_count": 0, "last_attempt": None},
                post_fn=post,
            )

        self.assertEqual(uploaded, (0, 0))
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
