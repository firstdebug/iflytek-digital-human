import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = PLUGIN_ROOT / "hooks"


def load_hook_module(name):
    path = HOOKS_DIR / (name + ".py")
    spec = importlib.util.spec_from_file_location("codex_hook_" + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class CodexHookPackageTests(unittest.TestCase):
    def test_manifest_registers_codex_hooks(self):
        manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["hooks"], "./hooks.json")

    def test_hook_config_uses_stable_codex_command_fields(self):
        config = json.loads((PLUGIN_ROOT / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(config), {"hooks"})
        events = config["hooks"]
        self.assertEqual(
            set(events),
            {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SessionEnd"},
        )
        for groups in events.values():
            for group in groups:
                self.assertNotIn("id", group)
                self.assertNotIn("description", group)
                for handler in group["hooks"]:
                    self.assertEqual(handler["type"], "command")
                    self.assertIn("commandWindows", handler)
                    self.assertIn("timeout", handler)
                    self.assertIs(handler["async"], False)
                    self.assertNotIn("timeoutSec", handler)

    def test_route_hint_matches_strong_avatar_intent_only(self):
        route = load_hook_module("route_hint")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                unrelated = route.build_hook_output(
                    {"session_id": "s1", "prompt": "帮我修一下普通网页"},
                    status_provider=lambda: "undecided",
                )
                avatar = route.build_hook_output(
                    {"session_id": "s2", "prompt": "创建一个讯飞虚拟人项目"},
                    status_provider=lambda: "undecided",
                )
        self.assertIsNone(unrelated)
        context = avatar["hookSpecificOutput"]["additionalContext"]
        self.assertIn("avatar-workflow-entry", context)
        self.assertIn("助手对话正文", context)
        self.assertIn("完整能力清单", context)
        self.assertIn("同意使用统计", context)

    def test_route_hint_ignores_backend_nlp_debug_with_quoted_avatar_text(self):
        route = load_hook_module("route_hint")
        prompt = (
            "D:\\codeRep\\avatar-interaction-svc\\avatar-common\\src\\main\\java\\"
            "cn\\xfyun\\avatar\\common\\data\\message\\NlpMessage.java，"
            "nlp-svc 与 OpenAI 第三方模型做 SSE 连接，如何启动服务完成一次经过 svc 的测试？\n\n"
            "上一轮粘贴内容：按当前虚拟人插件规范，需要明确选择隐私同意。"
        )
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                output = route.build_hook_output(
                    {"session_id": "backend-nlp", "prompt": prompt},
                    status_provider=lambda: "undecided",
                )
        self.assertIsNone(output)

    def test_route_hint_matches_explicit_codex_skill_invocation(self):
        route = load_hook_module("route_hint")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                output = route.build_hook_output(
                    {
                        "session_id": "s1",
                        "prompt": "$iflytek-digital-human:avatar-workflow-entry",
                    },
                    status_provider=lambda: "undecided",
                )
        self.assertIsNotNone(output)

    def test_explicit_skill_invocation_wins_over_backend_markers(self):
        intent = load_hook_module("avatar_intent")
        prompt = (
            "$iflytek-digital-human:avatar-workflow-entry，"
            "检查 nlp-svc 的 OpenAI SSE 返回"
        )
        self.assertTrue(intent.is_avatar_related(prompt))

    def test_route_hint_recognizes_consent_followup_in_active_session(self):
        route = load_hook_module("route_hint")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                route.build_hook_output(
                    {"session_id": "s1", "cwd": tmp, "prompt": "创建虚拟人项目"},
                    status_provider=lambda: "undecided",
                )
                output = route.build_hook_output(
                    {"session_id": "s1", "cwd": tmp, "prompt": "同意"},
                    status_provider=lambda: "undecided",
                )
                state = route.session_state.current("s1")
        self.assertEqual(state["phase"], "consent_accept")
        self.assertIn("consent --accept", output["systemMessage"])

    def test_pre_tool_guard_blocks_work_before_consent(self):
        guard = load_hook_module("pre_tool_guard")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                guard.session_state.mark_avatar_session(
                    {"session_id": "s1", "cwd": tmp}, "initial_avatar"
                )
                blocked = guard.build_hook_output(
                    {
                        "session_id": "s1",
                        "tool_name": "exec_command",
                        "tool_input": {"cmd": "npm create vite"},
                    },
                    status_provider=lambda: "undecided",
                )
                allowed_notice = guard.build_hook_output(
                    {
                        "session_id": "s1",
                        "tool_name": "exec_command",
                        "tool_input": {"cmd": "python tools/telemetry.py notice"},
                    },
                    status_provider=lambda: "undecided",
                )
                allowed_capabilities = guard.build_hook_output(
                    {
                        "session_id": "s1",
                        "tool_name": "exec_command",
                        "tool_input": {"cmd": "Get-Content docs/capabilities.md"},
                    },
                    status_provider=lambda: "undecided",
                )
        self.assertEqual(
            blocked["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIsNone(allowed_notice)
        self.assertIsNone(allowed_capabilities)

    def test_pre_tool_guard_requires_explicit_acceptance_for_consent_write(self):
        guard = load_hook_module("pre_tool_guard")
        payload = {
            "session_id": "s1",
            "tool_name": "exec_command",
            "tool_input": {"cmd": "python tools/telemetry.py consent --accept"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                guard.session_state.mark_avatar_session(
                    {"session_id": "s1", "cwd": tmp}, "initial_avatar"
                )
                denied = guard.build_hook_output(
                    payload, status_provider=lambda: "undecided"
                )
                guard.session_state.mark_avatar_session(
                    {"session_id": "s1", "cwd": tmp}, "consent_accept"
                )
                allowed = guard.build_hook_output(
                    payload, status_provider=lambda: "undecided"
                )
        self.assertEqual(
            denied["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIsNone(allowed)

    def test_pre_tool_guard_allows_only_the_selected_consent_mutation(self):
        guard = load_hook_module("pre_tool_guard")
        base = {"session_id": "s1", "tool_name": "exec_command"}
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                guard.session_state.mark_avatar_session(base, "consent_decline")
                decline = dict(base, tool_input={"cmd": "python telemetry.py consent --decline"})
                accept = dict(base, tool_input={"cmd": "python telemetry.py consent --accept"})
                allowed = guard.build_hook_output(
                    decline, status_provider=lambda: "undecided"
                )
                denied = guard.build_hook_output(
                    accept, status_provider=lambda: "undecided"
                )
        self.assertIsNone(allowed)
        self.assertEqual(
            denied["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_session_state_is_isolated_by_codex_session(self):
        state = load_hook_module("session_state")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                state.mark_avatar_session({"session_id": "one", "cwd": "a"}, "one")
                state.mark_avatar_session({"session_id": "two", "cwd": "b"}, "two")
                one = state.current("one")
                two = state.current("two")
        self.assertEqual(one["phase"], "one")
        self.assertEqual(two["phase"], "two")
        self.assertNotIn("cwd", one)

    def test_stop_guard_requires_full_visible_notice(self):
        response_guard = load_hook_module("response_guard")
        capabilities = (PLUGIN_ROOT / "docs" / "capabilities.md").read_text(
            encoding="utf-8"
        ).strip()
        notice = response_guard.render_privacy_notice().strip()
        payload = {
            "session_id": "s1",
            "prompt": "创建讯飞虚拟人项目",
            "last_assistant_message": "请问是否同意？",
        }
        missing = response_guard.build_stop_output(
            payload,
            status_provider=lambda: "undecided",
            session_active_provider=lambda _sid: True,
        )
        payload["last_assistant_message"] = (
            capabilities
            + "\n\n"
            + notice
            + "\n\n请选择：同意使用统计 / 不同意使用统计"
        )
        complete = response_guard.build_stop_output(
            payload,
            status_provider=lambda: "undecided",
            session_active_provider=lambda _sid: True,
        )
        self.assertEqual(missing["decision"], "block")
        self.assertIn("完整能力清单", missing["reason"])
        self.assertIsNone(complete)

    def test_stop_guard_requires_recording_an_explicit_consent_followup(self):
        response_guard = load_hook_module("response_guard")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                response_guard.session_state.mark_avatar_session(
                    {"session_id": "s1", "cwd": tmp}, "consent_accept"
                )
                output = response_guard.build_stop_output(
                    {
                        "session_id": "s1",
                        "prompt": "同意",
                        "last_assistant_message": "好的，继续。",
                    },
                    status_provider=lambda: "undecided",
                )
        self.assertEqual(output["decision"], "block")
        self.assertIn("consent --accept", output["reason"])

    def test_stop_guard_ignores_unrelated_backend_prompt_in_old_avatar_session(self):
        response_guard = load_hook_module("response_guard")
        prompt = (
            "D:\\codeRep\\avatar-interaction-svc\\avatar-common\\src\\main\\java\\"
            "cn\\xfyun\\avatar\\common\\data\\message\\NlpMessage.java，"
            "nlp-svc 与 OpenAI 第三方模型做 SSE 连接，如何启动服务完成一次测试？"
        )
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                response_guard.session_state.mark_avatar_session(
                    {"session_id": "s1", "cwd": tmp}, "initial_avatar"
                )
                output = response_guard.build_stop_output(
                    {
                        "session_id": "s1",
                        "prompt": prompt,
                        "last_assistant_message": "服务启动命令如下。",
                    },
                    status_provider=lambda: "undecided",
                )
        self.assertIsNone(output)

    def test_codex_transcript_parser_reads_latest_exchange(self):
        response_guard = load_hook_module("response_guard")
        rows = [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "虚拟人问题"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "虚拟人回答"}],
                },
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s1.jsonl"
            path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
                encoding="utf-8",
            )
            self.assertEqual(
                response_guard.latest_exchange(path),
                ("虚拟人问题", "虚拟人回答"),
            )

    def test_route_hook_accepts_utf8_pipe_on_windows(self):
        payload = json.dumps(
            {
                "session_id": "utf8-pipe",
                "prompt": "创建一个讯飞虚拟人项目",
                "cwd": str(PLUGIN_ROOT),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CODEX_HOME=tmp, PYTHONUTF8="0")
            result = subprocess.run(
                [sys.executable, str(HOOKS_DIR / "route_hint.py")],
                input=payload,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=True,
            )
        output = json.loads(result.stdout.decode("ascii"))
        self.assertEqual(
            output["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit"
        )

    def test_stop_tracker_never_self_reports_completion(self):
        tracker = load_hook_module("codex_tracker")
        telemetry = mock.Mock()
        common = mock.Mock()
        common.consent_status.return_value = "accepted"
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                tracker.session_state.mark_avatar_session(
                    {"session_id": "s1"}, "initial_avatar"
                )
                with mock.patch.object(
                    tracker, "_load_telemetry", return_value=(telemetry, common)
                ):
                    tracker.handle_event(
                        {"hook_event_name": "Stop", "session_id": "s1", "cwd": tmp}
                    )
        telemetry.report_complete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
