"""交付模式与语音门禁测试。

测试 workflow_mode: quick|strict 和语音确认门禁的完整性。
"""
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"


class DeliveryModesTests(unittest.TestCase):
    def test_delivery_modes_reference_exists(self):
        self.assertTrue((SKILLS_ROOT / "shared" / "delivery-modes.md").is_file())

    def test_modes_define_workflow_mode_not_delivery_mode(self):
        content = (SKILLS_ROOT / "shared" / "delivery-modes.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_mode: quick", content)
        self.assertIn("workflow_mode: strict", content)
        self.assertIn("process_documents: false", content)
        self.assertIn("writer_reviewer_loop: false", content)
        self.assertIn("不创建 `design-spec.md` 或 `implementation-plan.md`", content)

    def test_modes_define_hard_gates(self):
        content = (SKILLS_ROOT / "shared" / "delivery-modes.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("必问门禁", content)
        self.assertIn("首次 SDK 自建或多能力扩展时**必须先问一次**", content)
        self.assertIn("新增语音识别、语音交互、麦克风权限", content)
        self.assertIn("用户未回答时停止", content)

    def test_modes_clarify_both_skip_nothing_safety_critical(self):
        content = (SKILLS_ROOT / "shared" / "delivery-modes.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("两种模式都不能跳过", content)
        self.assertIn("密钥不进入源码", content)
        self.assertIn("android-gradle-stability.md", content)


class WorkflowModeIntegrationTests(unittest.TestCase):
    def test_authentication_failure_routes_to_evidence_driven_recovery(self):
        entry = (SKILLS_ROOT / "avatar-workflow-entry" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        troubleshoot = (SKILLS_ROOT / "avatar-troubleshoot" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        recovery = (
            SKILLS_ROOT
            / "avatar-troubleshoot"
            / "references"
            / "authentication-failed.md"
        ).read_text(encoding="utf-8")

        self.assertIn("avatar authentication failed", entry)
        self.assertIn("avatar-troubleshoot", entry)
        self.assertIn("authentication-failed.md", troubleshoot)
        self.assertIn("通用错误文案不是根因", recovery)
        for command in (
            "xfyun_query_services.py list-apps",
            "xfyun_query_services.py list-scenes",
            "xfyun_model_manage.py check <sceneId>",
            "xfyun_interface.py create <appId>",
            "xfyun_interface.py auth-avatar <appId>",
            "web_delivery.py",
        ):
            self.assertIn(command, recovery)
        self.assertIn("ready_to_deliver=true", recovery)
        self.assertNotIn("api/v1/scene/", recovery)
        self.assertNotIn("cat .env", recovery)
        self.assertNotIn("VITE_AVATAR_", recovery)

    def test_workflow_entry_documents_both_gates(self):
        content = (SKILLS_ROOT / "avatar-workflow-entry" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("用户确认门禁（HARD-GATE：必须先问，不能默认）", content)
        self.assertIn("交付模式门禁（workflow_mode）", content)
        self.assertIn("语音能力门禁", content)
        self.assertIn("AskUserQuestion", content)

    def test_brainstorming_accepts_mode_and_documents_quick_skip(self):
        content = (SKILLS_ROOT / "avatar-brainstorming" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("delivery-modes.md", content)
        self.assertIn("workflow_mode: quick | strict", content)
        self.assertIn("`quick`：不创建 `design-spec.md`", content)
        self.assertIn("不调用 `spec-reviewer`", content)

    def test_planning_skips_entirely_in_quick_mode(self):
        content = (SKILLS_ROOT / "avatar-planning" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("delivery-modes.md", content)
        self.assertIn("workflow_mode=quick", content)
        self.assertIn("直接跳过本阶段", content)
        self.assertIn("不调用 plan-writer/plan-reviewer", content)

    def test_executing_documents_mode_input_and_common_gates(self):
        content = (SKILLS_ROOT / "avatar-executing" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("delivery-modes.md", content)
        self.assertIn("workflow_mode: quick | strict", content)
        self.assertIn("共同前置门禁", content)
        self.assertIn("新增语音、麦克风权限或录音代码前", content)
        self.assertIn("android-gradle-stability.md", content)

    def test_verification_documents_mode_and_coverage_invariant(self):
        content = (SKILLS_ROOT / "avatar-verification" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("delivery-modes.md", content)
        self.assertIn("workflow_mode: quick | strict", content)
        self.assertIn("`quick`：执行完整验证", content)
        self.assertIn("不创建 `verification-report.md`", content)
        self.assertIn("模式只改变报告形态，不降低验证覆盖", content)

    def test_web_flow_documents_endpoint_and_gate_reporting_invariants(self):
        entry = (SKILLS_ROOT / "avatar-workflow-entry" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        credentials = (SKILLS_ROOT / "avatar-credentials" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        executing = (SKILLS_ROOT / "avatar-executing" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        verification = (SKILLS_ROOT / "avatar-verification" / "skill.md").read_text(
            encoding="utf-8"
        )
        for content in (entry, credentials, executing, verification):
            self.assertIn(
                "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact", content
            )
        self.assertIn("WS_URL 是平台常量", credentials)
        self.assertIn("blocked_missing_credentials", executing)
        self.assertIn("next_action", executing)
        self.assertIn("非终态门禁上报", executing)
        self.assertIn("门禁上报由状态机负责", verification)
        self.assertIn("不写 `ended_at` 或 `completion_method`", verification)

    def test_skill_sources_do_not_embed_known_hallucinated_endpoints(self):
        banned = (
            "console.xfyun.cn/avatar",
            "console.xfyun.cn/app/myapp",
            "console.xfyun.cn/services/bm",
            "avatar.xfyun.cn/v1/private/dh",
        )
        for path in SKILLS_ROOT.rglob("*.md"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            for endpoint in banned:
                self.assertNotIn(endpoint, content, str(path))


class VoiceGateTests(unittest.TestCase):
    def test_voice_interact_enforces_confirmation_gate(self):
        content = (SKILLS_ROOT / "voice-interact" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("用户确认门禁（HARD-GATE）", content)
        self.assertIn("AskUserQuestion", content)
        self.assertIn("按住说话", content)
        self.assertIn("点击开始/停止", content)
        self.assertIn("自动 VAD", content)
        self.assertIn("全双工", content)
        self.assertIn("用户未确认前**不得**加入 `RECORD_AUDIO`", content)
        self.assertIn("不得申请麦克风权限", content)

    def test_permissions_setup_enforces_gate_for_new_capabilities(self):
        content = (SKILLS_ROOT / "avatar-permissions-setup" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("权限修改门禁（新增能力时必须先问）", content)
        self.assertIn("AskUserQuestion", content)
        self.assertIn("**不得**添加 `RECORD_AUDIO`", content)

    def test_executing_red_flags_include_voice_gate_violations(self):
        content = (SKILLS_ROOT / "avatar-executing" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("用户未选择语音却加入麦克风权限", content)
        self.assertIn("违反语音门禁", content)

    def test_routing_rules_document_voice_extension_gate(self):
        content = (
            SKILLS_ROOT
            / "avatar-workflow-entry"
            / "references"
            / "routing-rules.md"
        ).read_text(encoding="utf-8")
        self.assertIn("语音能力扩展:", content)
        self.assertIn("gate: HARD-GATE", content)
        self.assertIn("未确认前不得修改 Manifest/Info.plist", content)

    def test_examples_show_voice_gate_enforcement(self):
        content = (
            SKILLS_ROOT / "avatar-workflow-entry" / "references" / "examples.md"
        ).read_text(encoding="utf-8")
        self.assertIn("给现有项目加语音", content)
        self.assertIn("语音门禁仍必须先执行", content)
        self.assertIn("不能直接改 Manifest", content)
        self.assertIn("反例（历史错误行为）", content)


if __name__ == "__main__":
    unittest.main()
