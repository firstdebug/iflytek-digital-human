import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "avatar-grill"

MODULES = {
    "avatar-action-control",
    "avatar-artifact-download",
    "avatar-audio-driver",
    "avatar-config-authoring",
    "avatar-credentials",
    "avatar-executing",
    "avatar-full-duplex",
    "avatar-integration-guides",
    "avatar-knowledge-base",
    "avatar-live-streaming",
    "avatar-model-config",
    "avatar-network-debug",
    "avatar-permissions-setup",
    "avatar-preflight",
    "avatar-subtitle-setup",
    "avatar-text-driver",
    "avatar-text-interact",
    "avatar-toolchain",
    "avatar-transparent-bg",
    "avatar-troubleshoot",
    "avatar-verification",
    "avatar-voice-interact",
    "avatar-web-template",
    "avatar-webapi-protocol",
    "shared",
}

TOOLS = {
    "completion_check.py",
    "platform_endpoints.py",
    "sdk_artifact.py",
    "telemetry.py",
    "telemetry_common.py",
    "uploader.py",
    "web_delivery.py",
    "web_sdk_gate.py",
    "websocket_auth.py",
    "write_env_safe.py",
    "xfyun_common.py",
    "xfyun_interface.py",
    "xfyun_knowledge.py",
    "xfyun_live.py",
    "xfyun_model_manage.py",
    "xfyun_query_services.py",
    "xfyun_secrets.py",
    "xfyun_template.py",
}


class SkillPackageTests(unittest.TestCase):
    def test_only_one_discoverable_skill_exists(self):
        discovered = list(ROOT.rglob("SKILL.md"))
        self.assertEqual(discovered, [SKILL / "SKILL.md"])

    def test_all_capability_modules_are_vendored_and_indexed(self):
        module_root = SKILL / "references" / "modules"
        self.assertEqual({p.name for p in module_root.iterdir() if p.is_dir()}, MODULES)
        index = (SKILL / "references" / "capability-execution.md").read_text(encoding="utf-8")
        for module in MODULES - {"shared"}:
            self.assertIn(f"modules/{module}/", index, module)

    def test_runtime_tools_are_bundled_and_parse(self):
        existing = {p.name for p in (ROOT / "tools").glob("*.py")}
        self.assertTrue(TOOLS <= existing)
        for path in (ROOT / "tools").glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_custom_markdown_links_resolve(self):
        pattern = re.compile(r"\[[^\]]+\]\(([^)#\s]+\.md)\)")
        paths = [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]
        for source in paths:
            for link in pattern.findall(source.read_text(encoding="utf-8")):
                self.assertTrue((source.parent / link).resolve().is_file(), f"{source}: {link}")

    def test_no_exported_account_data_or_runtime_files(self):
        forbidden_names = {"xfyun_scenes_export.json", "xfyun_cookies.json", ".env"}
        found = {p.name for p in ROOT.rglob("*") if p.is_file()}
        self.assertFalse(forbidden_names & found)

    def test_custom_instructions_have_no_legacy_workflow_dependency(self):
        paths = [SKILL / "SKILL.md", *(SKILL / "references" / "modules").rglob("*.md")]
        content = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths)
        for marker in (
            "avatar-brainstorming", "avatar-planning", "avatar-workflow-entry",
            "workflow_mode", "implementation-plan.md", "design-spec.md",
            "AskUserQuestion", "子 agent", "你是被派发", "delivery-modes.md",
            "返回上游", "路由到其他 Skill", "## 相关技能", "来自路由",
            "调用本技能", "交回父流程",
        ):
            self.assertNotIn(marker, content, marker)

    def test_install_docs_require_whole_repo_and_mutual_exclusion(self):
        install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        combined = install + "\n" + readme
        self.assertIn("整个", combined)
        self.assertIn("互斥", combined)
        self.assertNotIn("把 `skills/avatar-grill/` 复制", combined)
        self.assertIn("tools/xfyun_common.py", combined)

    def test_grill_round_format_is_documented(self):
        content = (SKILL / "references" / "question-tree.md").read_text(encoding="utf-8")
        self.assertIn("❓ **Q1**", content)
        self.assertIn("➡️ 推荐", content)
        self.assertIn("等用户回答整轮", content)
        self.assertIn("❓ **Q1** - **交付类型**", content)

    def test_diagnose_mutation_policy_is_consistent(self):
        sentence = (
            "docs、verify 只允许 [] 或 [none]；diagnose 只允许空操作、"
            "create_project_files 或 update_config，其他平台写操作必须回到 Grill 重新确认契约。"
        )
        paths = (
            SKILL / "scripts" / "validate_contract.py",
            SKILL / "references" / "execution-contract.md",
            SKILL / "references" / "capability-execution.md",
        )
        for path in paths:
            self.assertIn(sentence, path.read_text(encoding="utf-8"), str(path))

    def test_preflight_voice_and_shared_are_contract_subordinate(self):
        preflight = (SKILL / "references" / "modules" / "avatar-preflight" / "source-skill.md").read_text(encoding="utf-8")
        gate = (SKILL / "references" / "modules" / "avatar-preflight" / "references" / "gate-results-and-output.md").read_text(encoding="utf-8")
        voice = (SKILL / "references" / "modules" / "avatar-voice-interact" / "source-skill.md").read_text(encoding="utf-8")
        shared = (SKILL / "references" / "modules" / "shared" / "source-skill.md").read_text(encoding="utf-8")
        resource_auth = (SKILL / "references" / "modules" / "avatar-preflight" / "references" / "resource-authorization.md").read_text(encoding="utf-8")
        self.assertNotIn("用户主动执行", preflight)
        self.assertNotIn("--force-recheck", preflight + gate)
        self.assertNotIn("稍后手动配置", gate)
        self.assertNotIn("~/.avatar-code/dev-env.yaml", gate)
        self.assertIn("开始写代码或改权限前必须先用契约校验器确认", voice)
        self.assertIn("执行阶段不得现场追问", voice)
        self.assertNotIn("dispatching-parallel-agents", shared)
        self.assertIn("test-driven-development/source-skill.md", shared)
        self.assertNotIn("请选择或输入自定义", resource_auth)
        self.assertIn("只验证执行契约已经选择", resource_auth)

    def test_modules_do_not_restart_old_skills_or_execution_interviews(self):
        content = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (SKILL / "references" / "modules").rglob("*.md")
        )
        for marker in (
            "askUser(", "用户主动执行", "用户主动请求", "执行: avatar-",
            "dev-env.yaml", "--force-recheck", "../SKILL.md", "/SKILL.md",
        ):
            self.assertNotIn(marker, content, marker)

    def test_canonical_endpoint_is_owned_by_runtime_constant(self):
        source = (ROOT / "tools" / "platform_endpoints.py").read_text(encoding="utf-8")
        self.assertIn('CANONICAL_WS_URL = "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"', source)
        validator = (SKILL / "scripts" / "validate_contract.py").read_text(encoding="utf-8")
        self.assertIn("from platform_endpoints import CANONICAL_WS_URL", validator)
        self.assertNotIn('WS_URL = "wss://', validator)
        banned = ("console.xfyun.cn/app/myapp", "avatar.xfyun.cn/v1/private/dh")
        for path in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
            text = path.read_text(encoding="utf-8")
            for endpoint in banned:
                self.assertNotIn(endpoint, text, str(path))

    def test_manifests_are_valid_json(self):
        for manifest in ROOT.glob(".*-plugin/plugin.json"):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "avatar-grill")

    def test_claude_hooks_route_only_to_grill(self):
        hook_config = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertIn("UserPromptSubmit", hook_config["hooks"])
        self.assertIn("PreToolUse", hook_config["hooks"])
        self.assertIn("Stop", hook_config["hooks"])
        self.assertIn("SessionEnd", hook_config["hooks"])
        route = (ROOT / "hooks" / "route_hint.py").read_text(encoding="utf-8")
        self.assertIn("请使用 avatar-grill", route)
        self.assertNotIn("avatar-workflow-entry", route)

    def test_tracker_uses_isolated_grill_state_and_entry(self):
        tracker = (ROOT / "hooks" / "tracker.py").read_text(encoding="utf-8")
        self.assertIn("ENTRY_SKILLS = {'avatar-grill'}", tracker)
        self.assertIn("'.claude', 'avatar-grill'", tracker)
        self.assertNotIn("avatar-brainstorming", tracker)
        self.assertIn("maybe_set_type_from_contract", tracker)
        common = (ROOT / "tools" / "telemetry_common.py").read_text(encoding="utf-8")
        self.assertIn("'.claude' / 'avatar-grill' / 'telemetry'", common)


if __name__ == "__main__":
    unittest.main()
