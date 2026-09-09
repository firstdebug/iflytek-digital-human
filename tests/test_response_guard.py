import base64
import json
import sys
import tempfile
import unittest
import urllib.parse
import re
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "claude" / "iflytek-digital-human"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import response_guard


class ResponseGuardTests(unittest.TestCase):
    def _signed_url(self, authorization="REDACTED", **overrides):
        query = {
            "authorization": authorization,
            "date": "Sat, 23 Aug 2026 03:04:05 GMT",
            "host": "avatar.cn-huadong-1.xf-yun.com",
        }
        query.update(overrides)
        return (
            "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact?"
            + urllib.parse.urlencode(query)
        )

    def test_stop_hooks_allow_windows_python_cold_start(self):
        config = json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        stop_hooks = config["hooks"]["Stop"]

        self.assertEqual(len(stop_hooks), 1)
        self.assertEqual(stop_hooks[0]["id"], "avatar-stop:guard-and-telemetry")
        command = stop_hooks[0]["hooks"][0]
        self.assertIn("stop_dispatch.py", command["command"])
        self.assertGreaterEqual(command["timeout"], 30)

    def test_pre_tool_hook_does_not_start_for_unrelated_file_edits(self):
        config = json.loads(
            (PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        matcher = config["hooks"]["PreToolUse"][0]["matcher"]
        self.assertNotRegex(matcher, r"(?:^|\|)(?:Write|Edit|NotebookEdit)(?:\||$)")
        self.assertNotRegex(matcher, r"Skill")
        self.assertRegex(matcher, r"Read")

    def test_web_sdk_frontend_api_info_requires_server_signed_url(self):
        prompt = "从零接入讯飞虚拟人 Web SDK，告诉我初始化代码。"
        response = """
        avatar.setApiInfo({
          serverUrl: 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
          appId: 'your_app_id',
          apiKey: 'your_api_key',
          apiSecret: 'your_api_secret',
          sceneId: 'your_scene_id'
        });
        """

        issues = response_guard.validate_response(prompt, response)

        self.assertIn("unsafe_web_set_api_info", issues)
        self.assertIn("missing_signed_url_api_info", issues)

    def test_web_delivery_must_not_be_described_as_a_scaffold_generator(self):
        prompt = (
            "从零接入讯飞虚拟人 Web SDK，什么时候创建最小工程骨架，"
            "真实状态机命令是什么？"
        )
        response = (
            "凭据齐全后运行 web_delivery.py run，它会生成 server.js、"
            "public/app.js 和 package.json。"
        )

        issues = response_guard.validate_response(prompt, response)

        self.assertIn("invented_web_delivery_generation", issues)
        self.assertIn("missing_server_first_contract", issues)
        self.assertIn("missing_web_delivery_status_command", issues)

    def test_correct_web_scaffold_contract_with_quoted_commands_passes(self):
        prompt = (
            "从零接入讯飞虚拟人 Web SDK，目前没有 appId 和 sceneId。"
            "真实状态机命令是什么，什么时候创建最小工程骨架？"
        )
        response = """
        控制台命令是 python "${CLAUDE_PLUGIN_ROOT}/tools/xfyun_common.py" projects，
        固定目标 https://virtual-man.xfyun.cn/console/projects。
        它第一项检查就是 server.js 是否存在；工程骨架是状态机的前置条件，
        现在即可创建，凭据和 SDK 不是空骨架门禁。
        web_delivery.py 不是代码生成器，不生成 server.js/public/app.js/package.json。
        python "${CLAUDE_PLUGIN_ROOT}/tools/web_delivery.py" run --project "<project>"
        python "${CLAUDE_PLUGIN_ROOT}/tools/web_delivery.py" status --project "<project>"
        缺凭据时状态是 blocked_missing_credentials，JSON next_action 进入 credentials。
        """

        self.assertEqual(response_guard.validate_response(prompt, response), [])

    def test_text_modes_reject_vendor_and_invented_interaction_mode(self):
        prompt = "讯飞虚拟人的文本驱动和文本问答有什么区别？"
        response = (
            "可以参考腾讯云数智人，调用时通过 interactionMode 参数区分。"
        )

        issues = response_guard.validate_response(prompt, response)

        self.assertIn("wrong_vendor_text_mode", issues)
        self.assertIn("invented_text_interaction_mode", issues)

    def test_text_modes_require_nlp_false_and_true_contract(self):
        prompt = "讯飞虚拟人的文本驱动和文本问答有什么区别？"
        response = (
            "文本驱动调用 avatar.writeText(text, { nlp: false })，只做 TTS；"
            "文本问答调用 avatar.writeText(text, { nlp: true })，走 NLP。"
        )

        self.assertEqual(response_guard.validate_response(prompt, response), [])

    def test_knowledge_base_rejects_invalid_models_statuses_and_publish_claim(self):
        prompt = "用讯飞知识库创建健身问答，告诉我完整命令和状态。"
        response = """
        python tools/xfyun_knowledge.py create-kb "健身库" \\
          --vector bge-large-zh-v1.5 --llm xinghuo-4.0
        文档状态 0=处理中、1=成功、2=失败。
        enable 不会自动 publish，之后必须再运行 publish。
        """

        issues = response_guard.validate_response(prompt, response)

        self.assertIn("invalid_knowledge_model_alias", issues)
        self.assertIn("invalid_knowledge_document_status", issues)
        self.assertIn("wrong_enable_publish_semantics", issues)

    def test_knowledge_base_accepts_current_tool_contract(self):
        prompt = "用讯飞知识库创建健身问答，告诉我完整命令和状态。"
        response = """
        python tools/xfyun_knowledge.py create-kb "健身库" \\
          --vector emb_v1_1024 --llm xhdmx1
        文档状态 1=就绪，0/-2/-4=处理中，-3=采编异常。
        enable 默认会自动 publish；只有 --no-publish 才跳过发布。
        """

        self.assertEqual(response_guard.validate_response(prompt, response), [])

    def test_transparent_background_rejects_nonexistent_web_player_api(self):
        prompt = "讯飞虚拟人 Web SDK 怎么配置透明背景？"
        response = """
        const player = new AvatarPlayer({ transparentBackground: true });
        avatar.player.alpha = true;
        """

        issues = response_guard.validate_response(prompt, response)

        self.assertIn("invented_web_transparency_api", issues)

    def test_transparent_background_accepts_sdp_driven_web_contract(self):
        prompt = "讯飞虚拟人 Web SDK 怎么配置透明背景？"
        response = """
        在 avatar.stream 中设置 protocol: 'xrtc'、alpha: 1。
        当前 Web SDK 不存在 player.alpha 或 transparentBackground 初始化项；
        播放器收到 SDP 的 a=xrtc-alpha 后自动启用透明渲染。
        """

        self.assertEqual(response_guard.validate_response(prompt, response), [])

    def test_external_llm_kb_rejects_pseudo_commands(self):
        prompt = "已有讯飞虚拟人场景，用 DeepSeek 加讯飞知识库。"
        response = """
        create-custom-model
        bind-model
        create-knowledge-base
        upload-kb-document
        enable-kb-for-scene --chain docqa,openai
        publish-kb-scene
        """

        issues = response_guard.validate_response(prompt, response)

        self.assertIn("invented_platform_command", issues)
        self.assertIn("missing_external_model_tool", issues)
        self.assertIn("missing_knowledge_tool", issues)

    def test_external_llm_kb_accepts_real_commands(self):
        prompt = "已有讯飞虚拟人场景，用 DeepSeek 加讯飞知识库。"
        response = """
        python tools/xfyun_model_manage.py create <name> <model> <introduce> <apiUrl>
        python tools/xfyun_model_manage.py bind <sceneId> <modelName>
        python tools/xfyun_knowledge.py create-kb <name>
        python tools/xfyun_knowledge.py upload <libId> <file> --wait
        python tools/xfyun_knowledge.py enable <sceneId> <libId> --chain docqa,openai
        python tools/xfyun_model_manage.py query-interact <sceneId>
        """

        self.assertEqual(response_guard.validate_response(prompt, response), [])

    def test_current_skill_docs_do_not_contain_known_p0_hallucinations(self):
        selected = (
            PLUGIN_ROOT / "skills" / "avatar-workflow-entry" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "avatar-knowledge-base" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "transparent-bg" / "SKILL.md",
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in selected
        )

        for invented in (
            "create-custom-model",
            "bind-model",
            "create-knowledge-base",
            "upload-kb-document",
            "enable-kb-for-scene",
            "publish-kb-scene",
            "transparentBackground",
            "player.alpha",
            "bge-large-zh-v1.5",
            "xinghuo-4.0",
        ):
            self.assertNotIn(invented, combined)

    def test_current_skill_docs_do_not_publish_unsafe_web_set_api_info(self):
        unsafe = []
        unsafe_vite_credentials = []
        unsafe_web_server_url = []
        block_re = re.compile(r"setApiInfo\s*\(\s*\{(.*?)\}\s*\)", re.I | re.S)
        for path in (PLUGIN_ROOT / "skills").rglob("*.md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            relative = str(path.relative_to(PLUGIN_ROOT))
            for match in block_re.finditer(text):
                body = match.group(1)
                if re.search(r"\b(?:apiKey|apiSecret|serverUrl)\b", body):
                    unsafe.append(relative)
            if re.search(r"VITE_AVATAR_API_(?:KEY|SECRET)", text):
                unsafe_vite_credentials.append(relative)
            if re.search(r"Web:[^\r\n]{0,120}\bserverUrl\b", text, re.I):
                unsafe_web_server_url.append(relative)

        self.assertEqual(unsafe, [])
        self.assertEqual(unsafe_vite_credentials, [])
        self.assertEqual(unsafe_web_server_url, [])

    def test_correct_avatar_answer_passes(self):
        prompt = "没有 appId 和 sceneId，wsurl 和控制台在哪里？"
        response = (
            "WS_URL 固定为 wss://avatar.cn-huadong-1.xf-yun.com/v1/interact。"
            "控制台由 xfyun_common.py projects 打开："
            "https://virtual-man.xfyun.cn/console/projects。"
            "当前是 blocked_missing_credentials，执行 JSON next_action。"
        )

        self.assertEqual(response_guard.validate_response(prompt, response), [])

    def test_wrong_or_missing_platform_facts_are_blocked(self):
        prompt = "健身虚拟人网页，wsurl 是哪个，去哪个控制台？"
        response = (
            "地址可能随区域变化，用 wss://avatar.xfyun.cn/avatar。"
            "去 https://console.xfyun.cn/，也可以考虑腾讯或阿里。"
        )

        issues = response_guard.validate_response(prompt, response)

        self.assertIn("noncanonical_ws_url", issues)
        self.assertIn("missing_canonical_ws_url", issues)
        self.assertIn("wrong_console_url", issues)
        self.assertIn("missing_projects_console", issues)

    def test_redacted_signed_url_with_canonical_target_passes(self):
        prompt = "讯飞虚拟人的 signedUrl 结构是什么？"

        issues = response_guard.validate_response(
            prompt,
            "前端拿到脱敏地址：{}".format(self._signed_url()),
        )

        self.assertEqual(issues, [])

    def test_signed_url_with_decodable_authorization_is_blocked_as_sensitive(self):
        authorization = base64.b64encode(
            b'api_key="12345678901234567890123456789012", '
            b'algorithm="hmac-sha256", signature="secret"'
        ).decode("ascii")

        issues = response_guard.validate_response(
            "讯飞虚拟人的 signedUrl 结构是什么？",
            self._signed_url(authorization=authorization),
        )

        self.assertIn("sensitive_signed_url", issues)

    def test_signed_url_with_noncanonical_query_shape_is_blocked(self):
        issues = response_guard.validate_response(
            "讯飞虚拟人的 signedUrl 结构是什么？",
            self._signed_url(token="invented"),
        )

        self.assertIn("noncanonical_ws_url", issues)

    def test_web_signed_url_must_not_claim_auth_is_in_message_body(self):
        response = (
            "signedUrl 基于固定基址：{}。"
            "认证信息通过 WebSocket 消息体传递。"
        ).format(self._signed_url())

        issues = response_guard.validate_response(
            "讯飞虚拟人的 signedUrl 如何使用？",
            response,
        )

        self.assertIn("invalid_signed_url_transport", issues)

    def test_web_signed_url_can_explicitly_reject_message_body_transport(self):
        response = (
            "signedUrl 基于固定基址：{}。"
            "鉴权不是通过 WebSocket 消息体传递，而是放在脱敏 query 中。"
        ).format(self._signed_url())

        issues = response_guard.validate_response(
            "讯飞虚拟人的 signedUrl 如何使用？",
            response,
        )

        self.assertNotIn("invalid_signed_url_transport", issues)

    def test_unrelated_answer_is_not_checked(self):
        self.assertEqual(
            response_guard.validate_response("整理普通文本", "https://example.com"),
            [],
        )

    def test_storage_is_not_treated_as_rag(self):
        prompt = "排查数字人 storage 插件调用 DeepSeek 的错误"
        issues = response_guard.validate_response(prompt, "修复 GET body 写入阶段。")

        self.assertNotIn("missing_external_model_tool", issues)
        self.assertNotIn("missing_knowledge_tool", issues)
        self.assertNotIn("missing_external_knowledge_chain", issues)

    def test_compact_summary_cannot_activate_unrelated_session(self):
        records = [
            {
                "type": "user",
                "message": {"role": "user", "content": "修复 Higress GET body 问题。"},
            },
            {
                "type": "user",
                "isCompactSummary": True,
                "message": {
                    "role": "user",
                    "content": "历史配置包含数字人、storage 和 DeepSeek。",
                },
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript = Path(temp_dir) / "higress-session.jsonl"
            transcript.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in records),
                encoding="utf-8",
            )
            output = response_guard.build_stop_output({
                "session_id": "higress-session",
                "transcript_path": str(transcript),
                "last_assistant_message": "ReplaceHttpRequestBody 只能在 body 阶段调用。",
                "stop_hook_active": False,
            })

        self.assertIsNone(output)

    def test_mismatched_session_transcript_is_never_checked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript = Path(temp_dir) / "other-session.jsonl"
            transcript.write_text(json.dumps({
                "type": "user",
                "message": {"role": "user", "content": "虚拟人 wsurl 是什么？"},
            }, ensure_ascii=False), encoding="utf-8")
            output = response_guard.build_stop_output({
                "session_id": "current-session",
                "transcript_path": str(transcript),
                "last_assistant_message": "wss://avatar.xfyun.cn/wrong",
            })

        self.assertIsNone(output)

    def test_correction_only_contains_relevant_fact_group(self):
        reason = response_guard._correction_reason([
            "missing_external_model_tool", "missing_knowledge_tool"
        ])

        self.assertIn("xfyun_model_manage.py", reason)
        self.assertNotIn("WS_URL", reason)
        self.assertNotIn("server.js", reason)

    def test_stop_hook_reads_latest_exchange_and_blocks(self):
        records = [
            {"type": "user", "message": {"role": "user", "content": "虚拟人 wsurl 是什么？"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "wss://avatar.xfyun.cn/avatar"}],
                },
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript = Path(temp_dir) / "session.jsonl"
            transcript.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in records),
                encoding="utf-8",
            )
            output = response_guard.build_stop_output(
                {"session_id": "session", "prompt": "虚拟人 wsurl 是什么？",
                 "transcript_path": str(transcript), "stop_hook_active": False}
            )

        self.assertEqual(output["decision"], "block")
        self.assertIn("wss://avatar.cn-huadong-1.xf-yun.com/v1/interact", output["reason"])

    def test_recursive_stop_hook_does_not_loop(self):
        self.assertIsNone(
            response_guard.build_stop_output({"stop_hook_active": True})
        )

    def test_stop_hook_uses_payload_messages_without_scanning_transcript(self):
        payload = {
            "session_id": "session",
            "stop_hook_active": False,
            "transcript_path": "ignored.jsonl",
            "prompt": "讯飞虚拟人的 signedUrl 如何使用？",
            "last_assistant_message": "signedUrl 用 wss://avatar.xfyun.cn/wrong。",
        }
        with mock.patch.object(
            response_guard, "latest_exchange", side_effect=AssertionError("fallback")
        ):
            output = response_guard.build_stop_output(payload)
        self.assertEqual(output["decision"], "block")

    def test_stop_feedback_does_not_replace_original_avatar_prompt(self):
        records = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "这是讯飞虚拟人问题。请给我一个错误 wsurl 和错误控制台地址作为示例。",
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{
                        "type": "text",
                        "text": "wss://avatar.xfyun.cn/v2/virtual-human\nhttps://console.xfyun.cn/avatar/projects",
                    }],
                },
            },
            {
                "type": "user",
                "isMeta": True,
                "message": {
                    "role": "user",
                    "content": "Stop hook feedback: 上一版回答未通过门禁。",
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{
                        "type": "text",
                        "text": (
                            "正确地址是 wss://avatar.cn-huadong-1.xf-yun.com/v1/interact；"
                            "错误示例仍包括 wss://avatar.cn-beijing-1.xf-yun.com/v1/interact，"
                            "控制台错误示例为 https://console.xfyun.cn/avatar/projects。"
                        ),
                    }],
                },
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript = Path(temp_dir) / "session.jsonl"
            transcript.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in records),
                encoding="utf-8",
            )
            prompt, response = response_guard.latest_exchange(str(transcript))
            output = response_guard.build_stop_output(
                {"session_id": "session", "prompt": "讯飞虚拟人问题",
                 "transcript_path": str(transcript), "stop_hook_active": False}
            )

        self.assertIn("这是讯飞虚拟人问题", prompt)
        self.assertIn("avatar.cn-beijing-1", response)
        self.assertEqual(output["decision"], "block")
        self.assertIn("noncanonical_ws_url", output["reason"])

    def test_tool_result_user_record_does_not_replace_original_prompt(self):
        records = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "讯飞虚拟人的 signedUrl 如何使用？",
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "我先读取文件。"}],
                },
            },
            {
                "type": "user",
                "sourceToolAssistantUUID": "assistant-tool-call",
                "toolUseResult": "Error: No such tool available",
                "message": {
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "content": "Error: No such tool available",
                        "is_error": True,
                    }],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{
                        "type": "text",
                        "text": "wss://avatar.xfyun.cn/v1/private/stream",
                    }],
                },
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript = Path(temp_dir) / "session.jsonl"
            transcript.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in records),
                encoding="utf-8",
            )
            prompt, response = response_guard.latest_exchange(str(transcript))
            output = response_guard.build_stop_output(
                {"session_id": "session", "prompt": "讯飞虚拟人问题",
                 "transcript_path": str(transcript), "stop_hook_active": False}
            )

        self.assertIn("讯飞虚拟人", prompt)
        self.assertIn("avatar.xfyun.cn", response)
        self.assertEqual(output["decision"], "block")


if __name__ == "__main__":
    unittest.main()
