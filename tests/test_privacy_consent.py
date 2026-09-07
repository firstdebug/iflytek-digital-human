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
        "notice_version": "2.2",
        "controller_name": "Example Controller",
        "recipient_name": "Example Recipient",
        "upload_endpoint": "https://telemetry.example.test/report",
        "storage_region": "China",
        "retention_days": 365,
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
            STATE_BACKUP_PATH=self.telemetry_dir / "state.backup.json",
            STATE_LOCK_PATH=self.telemetry_dir / "state.lock",
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
        self.assertFalse((self.telemetry_dir / "anonymous_id.json").exists())
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
        self.assertEqual(metadata["privacyNoticeVersion"], "2.2")
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
    def test_notice_has_no_anonymous_identity_terms(self):
        notice_text = (PLUGIN_ROOT / "config" / "privacy_notice.json").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("anonymous_id", notice_text)
        self.assertNotIn("anon_", notice_text)
        self.assertIn("account_id", notice_text)
        self.assertIn("xfyun_user_id", notice_text)

    def test_upload_endpoint_matches_runtime_config_and_server_route(self):
        notice = json.loads(
            (PLUGIN_ROOT / "config" / "privacy_notice.json").read_text(
                encoding="utf-8"
            )
        )
        config = json.loads(
            (PLUGIN_ROOT / "config" / "telemetry.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(notice["upload_endpoint"], config["endpoint"])
        self.assertEqual(config["endpoint"], uploader.DEFAULT_CONFIG["endpoint"])
        self.assertTrue(config["endpoint"].endswith(
            "/zs_server/workflow-telemetry/report"
        ))

    def test_production_notice_uses_official_xfyun_policies(self):
        notice = json.loads(
            (PLUGIN_ROOT / "config" / "privacy_notice.json").read_text(
                encoding="utf-8"
            )
        )
        self.write_notice(notice)
        rendered = telemetry.render_privacy_notice()

        self.assertEqual(notice["notice_version"], "2.2")
        self.assertEqual(notice["controller_name"], "科大讯飞股份有限公司")
        self.assertIn("dpo@iflytek.com", notice["contact"])
        self.assertNotIn("待法务", json.dumps(notice, ensure_ascii=False))
        self.assertEqual(
            notice["privacy_policy_url"],
            "https://www.xfyun.cn/doc/policy/privacy.html"
            "#%E4%B8%80%E3%80%81%E5%AE%9A%E4%B9%89%E4%B8%8E%E8%A7%A3%E9%87%8A",
        )
        self.assertEqual(
            notice["user_agreement_url"],
            "https://www.xfyun.cn/doc/policy/agreement.html",
        )
        self.assertIn(notice["privacy_policy_url"], rendered)
        self.assertIn(notice["user_agreement_url"], rendered)
        self.assertIn("讯飞开放平台隐私政策", rendered)
        self.assertIn("讯飞开放平台用户服务协议", rendered)

    def test_notice_renders_explicit_opt_in_and_placeholders(self):
        notice = complete_notice()
        notice["controller_name"] = "[待补充：数据处理方名称]"
        self.write_notice(notice)

        rendered = telemetry.render_privacy_notice()

        self.assertIn("声明版本：2.2", rendered)
        self.assertIn("[待补充：数据处理方名称]", rendered)
        self.assertIn("不同意不会影响 avatar-platform 的正常功能", rendered)
        self.assertIn("沉默、继续使用插件或关闭本提示均不视为同意", rendered)
        self.assertIn("项目目录仅在本地用于工作流接续和产物验证", rendered)
        self.assertIn("对话全文和后续 Prompt 原文不会落盘或上传", rendered)
        self.assertNotIn("讯飞账号哈希", rendered)
        self.assertNotIn("进入虚拟人工作流时的首条用户请求", rendered)
        self.assertNotIn("对话和 Prompt 原文不会落盘或上传", rendered)
        self.assertIn("[同意]", rendered)
        self.assertIn("[不同意]", rendered)
        self.assertIn("365", rendered)

    def test_entry_skill_requires_consent_before_business_routing(self):
        content = (PLUGIN_ROOT / "skills" / "avatar-workflow-entry" /
                   "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("首次调用：能力清单 + 完整声明", content)
        self.assertIn("docs/capabilities.md", content)
        self.assertIn("telemetry.py notice", content)
        self.assertIn("讯飞开放平台隐私政策", content)
        self.assertIn("讯飞开放平台用户服务协议", content)
        self.assertIn("consent --status", content)
        self.assertIn("`undecided` 或 `stale`", content)
        notice_config = json.loads(
            (PLUGIN_ROOT / "config" / "privacy_notice.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("ready", notice_config)
        self.assertLess(content.index("首次调用：能力清单 + 完整声明"), content.index("快速扫描工程"))

        capabilities = content.index("docs/capabilities.md")
        notice = content.index("telemetry.py notice")
        question = content.index("AskUserQuestion", notice)
        self.assertLess(capabilities, notice)
        self.assertLess(notice, question)
        self.assertIn("用户选择前停止", content)
        self.assertIn("不得扫描工程", content)
        self.assertIn("不得调用下游 skill", content)
        self.assertIn("已是 `accepted`", content)
        self.assertIn("已是 `declined`", content)
        self.assertIn("只展示能力清单", content)

    def test_entry_skill_prefers_hook_status_and_only_uses_shell_as_fallback(self):
        content = (PLUGIN_ROOT / "skills" / "avatar-workflow-entry" /
                   "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("avatar-platform consent", content)
        self.assertIn("仅当上下文中没有", content)
        self.assertIn("consent --status", content)

    def test_entry_skill_re_reads_after_accept_and_flushes_upload(self):
        content = (PLUGIN_ROOT / "skills" / "avatar-workflow-entry" /
                   "SKILL.md").read_text(encoding="utf-8")

        accept = content.index("telemetry.py consent --accept")
        reread = content.index("必须立刻重新读取本入口", accept)
        self.assertLess(accept, reread)
        self.assertIn("只写入本地 pending 状态", content[reread:])
        self.assertIn("xfyun_common.py", content[reread:])
        self.assertIn("真实的 `read` invocation", content)
        self.assertIn("不得把授权前的 slash/prompt 追溯写入", content)


class ConsentRouteHintTests(unittest.TestCase):
    def test_avatar_context_injects_fail_closed_platform_invariants(self):
        output = route_hint.build_hook_output(
            {"prompt": "/avatar-platform:avatar-workflow-entry 我要做 Web 虚拟人，但没有 appId 和 sceneId"},
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
            {"prompt": "/avatar-platform:avatar-workflow-entry 帮我构建一个虚拟人项目"}, status_provider=status
        )

        status.assert_called_once_with()
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[avatar-platform consent] status=accepted", context)
        self.assertIn("不要运行 telemetry.py consent --status", context)
        self.assertIn("不要向用户重复提示", context)

    def test_undecided_status_instructs_full_notice_and_explicit_choice(self):
        output = route_hint.build_hook_output(
            {"prompt": "/avatar-platform:avatar-live-streaming 创建数字人直播间"},
            status_provider=lambda: "undecided",
        )

        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[avatar-platform consent] status=undecided", context)
        self.assertIn("telemetry.py notice", context)
        self.assertIn("docs/capabilities.md", context)
        self.assertLess(context.index("docs/capabilities.md"), context.index("telemetry.py notice"))
        self.assertIn("未选择前不得业务路由", context)
        self.assertIn("明确选择", context)

    def test_stale_status_has_same_capability_and_notice_gate(self):
        output = route_hint.build_hook_output(
            {"prompt": "/avatar-platform:avatar-live-streaming 创建虚拟人直播项目"},
            status_provider=lambda: "stale",
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("docs/capabilities.md", context)
        self.assertIn("telemetry.py notice", context)
        self.assertIn("未选择前不得业务路由", context)

    def test_declined_status_continues_without_capability_consent_gate(self):
        output = route_hint.build_hook_output(
            {"prompt": "/avatar-platform:avatar-live-streaming 创建虚拟人直播项目"},
            status_provider=lambda: "declined",
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("status=declined", context)
        self.assertIn("继续业务路由", context)
        self.assertNotIn("docs/capabilities.md", context)
        self.assertNotIn("telemetry.py notice", context)

    def test_unrelated_prompt_does_not_read_or_inject_consent(self):
        status = mock.Mock(return_value="accepted")

        output = route_hint.build_hook_output(
            {"prompt": "帮我整理这个普通文本文件"}, status_provider=status
        )

        self.assertIsNone(output)
        status.assert_not_called()

    def test_weak_avatar_words_do_not_activate_global_hook(self):
        status = mock.Mock(return_value="accepted")

        for prompt in (
                "update my avatar image", "讯飞最近有什么新闻",
                "配置直播、场景和知识库", "这个 appId 字段是什么意思"):
            self.assertIsNone(route_hint.build_hook_output(
                {"prompt": prompt}, status_provider=status))

        status.assert_not_called()

    def test_explicit_avatar_signals_still_activate_hook(self):
        for prompt in ("/avatar-platform:avatar-workflow-entry",
                       "请执行 /avatar-platform:avatar-verification"):
            self.assertIsNotNone(route_hint.build_hook_output(
                {"prompt": prompt}, status_provider=lambda: "accepted"))

    def test_natural_avatar_mentions_do_not_activate_route_hook(self):
        status = mock.Mock(return_value="accepted")
        for prompt in ("创建虚拟人直播项目", "接入 avatar sdk",
                       "build an xfyun avatar demo",
                       "请审查 nlp-svc 的虚拟人协议适配"):
            self.assertIsNone(route_hint.build_hook_output(
                {"prompt": prompt}, status_provider=status))
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
    def test_payload_omits_consent_and_schema_fields(self):
        payload = uploader._payload(
            {},
            [{"workflowId": "wf-1", "xfyunUserId": "xf-test"}],
            [],
        )

        self.assertEqual(payload["xfyunUserId"], "xf-test")
        self.assertNotIn("anonymousId", payload)
        self.assertNotIn("schemaVersion", payload)
        self.assertNotIn("privacyNoticeVersion", payload)
        self.assertNotIn("consentedAt", payload)

    def test_upload_stops_when_consent_is_withdrawn(self):
        post = mock.Mock()

        with mock.patch.object(uploader, "can_upload", return_value=False):
            uploaded = uploader.upload_all(
                {"batch_size": 50, "schema_version": "1.2"},
                {"retry_count": 0, "last_attempt": None},
                post_fn=post,
            )

        self.assertEqual(uploaded, (0, 0))
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
