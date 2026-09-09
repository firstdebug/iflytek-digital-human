import ast
import re
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"
TOOLS_CONFIG = PLUGIN_ROOT / "config" / "tools.yaml"
REFERENCE_PATTERN = re.compile(
    r"(?P<path>(?:skills/[a-z0-9-]+/|\.\./[a-z0-9-]+/)?"
    r"references/[A-Za-z0-9_./-]+\.md)"
)
BACKTICK_AVATAR_NAME = re.compile(r"`(avatar-[a-z0-9-]+)`")


def skill_files():
    return sorted(SKILLS_ROOT.rglob("SKILL.md"))


def registered_commands(script_path):
    tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    commands = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            if any(
                isinstance(target, ast.Name) and target.id == "_COMMANDS"
                for target in node.targets
            ):
                commands.update(
                    key.value
                    for key in node.value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )

        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "cmd":
            continue
        comparator = node.comparators[0]
        if isinstance(node.ops[0], ast.Eq) and isinstance(comparator, ast.Constant):
            if isinstance(comparator.value, str):
                commands.add(comparator.value)
        elif isinstance(node.ops[0], ast.In) and isinstance(comparator, (ast.Tuple, ast.List)):
            commands.update(
                item.value
                for item in comparator.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )

    return commands


class PluginConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools_config = yaml.safe_load(TOOLS_CONFIG.read_text(encoding="utf-8"))

    def test_tools_yaml_is_valid_and_has_unique_names(self):
        tools = self.tools_config["tools"]
        names = [tool["name"] for tool in tools]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreater(len(names), 0)

    def test_registered_tool_scripts_and_commands_exist(self):
        for tool in self.tools_config["tools"]:
            script_path = PLUGIN_ROOT / tool["path"]
            self.assertTrue(script_path.is_file(), tool["name"])
            command = tool.get("command")
            if command:
                self.assertIn(command, registered_commands(script_path), tool["name"])

    def test_all_skill_references_exist(self):
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            for match in REFERENCE_PATTERN.finditer(content):
                reference = match.group("path")
                if reference.startswith("skills/"):
                    target = PLUGIN_ROOT / reference
                else:
                    target = skill_file.parent / reference
                self.assertTrue(target.resolve().is_file(), f"{skill_file}: {reference}")

    def test_backticked_skill_names_resolve(self):
        known_skills = {path.parent.name for path in skill_files()}
        non_skill_identifiers = {
            "avatar-code-reviewer",
            "avatar-code-writer",
            "avatar-sdk",
        }
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            for name in BACKTICK_AVATAR_NAME.findall(content):
                if name in non_skill_identifiers:
                    continue
                self.assertIn(name, known_skills, f"{skill_file}: {name}")

    def test_old_unprefixed_skill_names_do_not_return(self):
        current_names = {path.parent.name for path in skill_files()}
        old_names = {name[len("avatar-") :] for name in current_names}
        backticked_token = re.compile(r"`([a-z][a-z0-9-]+)`")
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            stale = sorted(set(backticked_token.findall(content)) & old_names)
            self.assertEqual(stale, [], f"{skill_file}: {stale}")

    def test_skill_files_stay_within_authoring_limit(self):
        for skill_file in skill_files():
            line_count = len(skill_file.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(line_count, 500, skill_file)

    def test_sources_have_no_machine_specific_paths_or_claude_calls(self):
        forbidden = (
            "C:\\Users\\",
            "D:/avatar-platform",
            "D:/iflytek-digital-human",
            "/home/user/",
            "~/.claude",
            "~/.avatar-code",
            ".claude/avatar",
            "AskUserQuestion",
        )
        for source_file in PLUGIN_ROOT.rglob("*"):
            if not source_file.is_file() or "tests" in source_file.parts:
                continue
            if source_file.suffix.lower() not in {".md", ".py", ".json", ".yaml", ".yml"}:
                continue
            content = source_file.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, content, source_file)

    def test_skill_entrypoints_do_not_embed_example_scene_or_app_ids(self):
        forbidden_patterns = (
            re.compile(r"sceneId[^\n]{0,20}\b\d{12,}\b", re.IGNORECASE),
            re.compile(r"appId[^\n]{0,20}\b\d{8}\b", re.IGNORECASE),
        )
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                self.assertIsNone(pattern.search(content), skill_file)

    def test_default_live_assets_match_platform_defaults(self):
        live_source = (PLUGIN_ROOT / "tools" / "xfyun_live.py").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_ANCHOR_ID = "111310001"', live_source)
        self.assertIn('DEFAULT_VCN = "x4_lingxiaoqi_oral"', live_source)
        tools_yaml = TOOLS_CONFIG.read_text(encoding="utf-8")
        self.assertRegex(tools_yaml, r"anchor: string\s+# 可选，形象ID，默认111310001")
        self.assertRegex(tools_yaml, r"vcn: string\s+# 可选，发音人，默认x4_lingxiaoqi_oral")

    def test_android_quick_guide_excludes_historical_invalid_calls(self):
        guide = (
            SKILLS_ROOT / "avatar-integration-guides" / "android.md"
        ).read_text(encoding="utf-8")
        invalid_calls = (
            "createStreamPlayer",
            "sendText",
            "onNlpResult",
            "onAsrResult",
            "onAvatarReady",
            "writeAudioFrame",
            "startAudioInteract",
        )
        for call in invalid_calls:
            self.assertNotIn(call, guide)
        self.assertNotRegex(guide, r"AvatarPlatform\.initialize\([^,]+,[^,]+\)")

    def test_android_gradle_stability_contract(self):
        shared = (
            SKILLS_ROOT / "avatar-shared" / "android-gradle-stability.md"
        ).read_text(encoding="utf-8")
        gradle_properties = (
            SKILLS_ROOT
            / "avatar-executing"
            / "templates"
            / "android-build-template"
            / "gradle.properties"
        ).read_text(encoding="utf-8")
        settings = (
            SKILLS_ROOT
            / "avatar-executing"
            / "templates"
            / "android-build-template"
            / "settings.gradle.template"
        ).read_text(encoding="utf-8")
        wrapper = (
            SKILLS_ROOT
            / "avatar-executing"
            / "templates"
            / "android-build-template"
            / "gradle"
            / "wrapper"
            / "gradle-wrapper.properties"
        ).read_text(encoding="utf-8")

        for marker in (
            "同一工程同一时间只运行一个 Gradle 调用",
            "命令超时不代表 Gradle 已停止",
            "--offline",
            "org.gradle.parallel=false",
            "org.gradle.workers.max=2",
        ):
            self.assertIn(marker, shared)

        self.assertIn("org.gradle.jvmargs=-Xmx1280m", gradle_properties)
        self.assertIn("org.gradle.parallel=false", gradle_properties)
        self.assertIn("org.gradle.workers.max=2", gradle_properties)
        self.assertNotIn("org.gradle.parallel=true", gradle_properties)
        self.assertNotIn("-Xmx2048m", gradle_properties)

        repository_markers = (
            "maven.aliyun.com/repository/google",
            "mirrors.cloud.tencent.com/nexus/repository/maven-public",
            "repo.huaweicloud.com/repository/maven",
            "google()",
        )
        positions = [settings.index(marker) for marker in repository_markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("mirrors.cloud.tencent.com/gradle/gradle-8.0.2-bin.zip", wrapper)

        routed_skills = (
            "avatar-workflow-entry",
            "avatar-toolchain",
            "avatar-executing",
            "avatar-troubleshoot",
            "avatar-verification",
        )
        for skill_name in routed_skills:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("android-gradle-stability.md", content, skill_name)

    def test_quick_and_strict_workflow_modes(self):
        modes = (SKILLS_ROOT / "avatar-shared" / "delivery-modes.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_mode: quick", modes)
        self.assertIn("process_documents: false", modes)
        self.assertIn("writer_reviewer_loop: false", modes)
        self.assertIn("不创建 `design-spec.md` 或 `implementation-plan.md`", modes)
        self.assertIn("两种模式都不能跳过", modes)

        workflow_skills = (
            "avatar-workflow-entry",
            "avatar-brainstorming",
            "avatar-planning",
            "avatar-executing",
            "avatar-verification",
        )
        combined = ""
        for skill_name in workflow_skills:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("workflow_mode", content, skill_name)
            combined += content

        self.assertNotRegex(combined, r"delivery_mode\s*[:=]\s*(?:quick|strict)")

        brainstorming = (
            SKILLS_ROOT / "avatar-brainstorming" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("不创建 `design-spec.md`", brainstorming)
        self.assertIn("不调用 `spec-reviewer`", brainstorming)
        self.assertIn("直接调用 `avatar-executing`", brainstorming)

        planning = (SKILLS_ROOT / "avatar-planning" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_mode=quick", planning)
        self.assertIn("直接跳过本阶段", planning)
        self.assertIn("不调用 plan-writer/plan-reviewer", planning)

        executing = (SKILLS_ROOT / "avatar-executing" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("主 agent 依 Playbook 直接实现", executing)
        self.assertIn("不派发 writer/reviewer", executing)

        verification = (
            SKILLS_ROOT / "avatar-verification" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("不创建 `verification-report.md`", verification)
        self.assertIn("模式只改变报告形态，不降低验证覆盖", verification)

    def test_web_sdk_delivery_uses_executable_hard_gates(self):
        workflow = (
            SKILLS_ROOT / "avatar-workflow-entry" / "SKILL.md"
        ).read_text(encoding="utf-8")
        executing = (
            SKILLS_ROOT / "avatar-executing" / "SKILL.md"
        ).read_text(encoding="utf-8")
        artifact = (
            SKILLS_ROOT / "avatar-artifact-download" / "SKILL.md"
        ).read_text(encoding="utf-8")
        verification = (
            SKILLS_ROOT / "avatar-verification" / "SKILL.md"
        ).read_text(encoding="utf-8")
        playbook = (
            SKILLS_ROOT
            / "avatar-executing"
            / "references"
            / "web-sdk-build-playbook.md"
        ).read_text(encoding="utf-8")

        self.assertIn("sdk_artifact.py", artifact)
        for content in (workflow, executing, verification, playbook):
            self.assertIn("web_delivery.py", content)
        self.assertIn("blocked_missing_sdk", artifact)
        self.assertIn("needs_runtime_verification", verification)
        self.assertIn("module.default", playbook)
        self.assertIn("auth-verification.md", playbook)

    def test_sdk_docs_do_not_claim_permanent_or_fabricated_download_links(self):
        forbidden = (
            "无过期时间",
            "所有链接均为固定 OSS 链接",
        )
        for source_file in PLUGIN_ROOT.rglob("*"):
            if not source_file.is_file() or "tests" in source_file.parts:
                continue
            if source_file.suffix.lower() not in {".md", ".py", ".json", ".yaml", ".yml"}:
                continue
            content = source_file.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                self.assertNotIn(marker, content, source_file)
            self.assertIsNone(
                re.search(
                    r"https://www\.xfyun\.cn/doc/avatar/(?:\s|[`\"'<>)]|$)",
                    content,
                ),
                source_file,
            )


if __name__ == "__main__":
    unittest.main()
