"""技能包一致性测试。

对应 Codex 侧 tests/test_plugin_consistency.py，按 Claude 约定调整：
- skill 目录名不强制 avatar- 前缀，但 frontmatter name 必须等于目录名
- 允许 Claude 原生 frontmatter 键（tags/priority/required_tools/optional_tools）
- 允许使用 AskUserQuestion（Claude 原生询问工具）
"""
import re
import unittest
import zipfile
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"
TOOLS_CONFIG = PLUGIN_ROOT / "config" / "tools.yaml"

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((?P<path>[^)#\s]+\.md)\)")
BACKTICK_SKILL_NAME = re.compile(r"`(avatar-[a-z0-9-]+|voice-interact|text-driver|text-interact|audio-driver|action-control|subtitle-setup|transparent-bg|full-duplex|toolchain|integration-guides|shared)`")

ALLOWED_FRONTMATTER_KEYS = {
    "name",
    "description",
    "tags",
    "priority",
    "required_tools",
    "optional_tools",
}

# 非 skill 的标识符（agent 名、SDK 名等），不参与目录存在性校验
NON_SKILL_IDENTIFIERS = {
    "avatar-code-reviewer",
    "avatar-code-writer",
    "avatar-sdk",
    "avatar-preflight",
    "avatar-artifact-download",
}


def skill_files():
    return sorted(SKILLS_ROOT.rglob("SKILL.md"))


def read_frontmatter(skill_file):
    content = skill_file.read_text(encoding="utf-8")
    match = FRONTMATTER.match(content)
    if not match:
        return None
    return yaml.safe_load(match.group(1))


class SkillFrontmatterTests(unittest.TestCase):
    def test_every_skill_has_frontmatter(self):
        for skill_file in skill_files():
            self.assertIsNotNone(read_frontmatter(skill_file), skill_file)

    def test_frontmatter_name_matches_directory_name(self):
        """Claude 的 skill 发现依赖 name 与目录名一致。"""
        for skill_file in skill_files():
            data = read_frontmatter(skill_file)
            self.assertEqual(
                data.get("name"),
                skill_file.parent.name,
                f"{skill_file}: name={data.get('name')} dir={skill_file.parent.name}",
            )

    def test_frontmatter_keys_are_allowed(self):
        for skill_file in skill_files():
            data = read_frontmatter(skill_file)
            unexpected = set(data) - ALLOWED_FRONTMATTER_KEYS
            self.assertEqual(unexpected, set(), f"{skill_file}: {unexpected}")

    def test_description_is_present_and_single_paragraph(self):
        for skill_file in skill_files():
            data = read_frontmatter(skill_file)
            description = data.get("description", "")
            self.assertTrue(description.strip(), skill_file)
            self.assertNotIn("\n\n", description.strip(), skill_file)


class SkillReferenceTests(unittest.TestCase):
    def test_markdown_links_resolve(self):
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            for match in MARKDOWN_LINK.finditer(content):
                reference = match.group("path")
                if reference.startswith("http"):
                    continue
                if reference.startswith("skills/"):
                    target = PLUGIN_ROOT / reference
                else:
                    target = skill_file.parent / reference
                self.assertTrue(
                    target.resolve().is_file(), f"{skill_file}: {reference}"
                )

    def test_backticked_skill_names_resolve(self):
        known_skills = {path.parent.name for path in skill_files()}
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            for name in BACKTICK_SKILL_NAME.findall(content):
                if name in NON_SKILL_IDENTIFIERS:
                    continue
                self.assertIn(name, known_skills, f"{skill_file}: {name}")

    def test_shared_material_references_resolve(self):
        """所有对 shared/ 材料的相对引用必须存在。"""
        pattern = re.compile(r"`\.\./shared/([a-z0-9-]+\.md)`")
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            for name in pattern.findall(content):
                target = SKILLS_ROOT / "shared" / name
                self.assertTrue(target.is_file(), f"{skill_file}: shared/{name}")


class NoMachineSpecificPathsTests(unittest.TestCase):
    def test_sources_have_no_machine_specific_paths(self):
        forbidden = (
            "C:\\Users\\",
            "C:/Users/",
            "D:/avatar-platform",
            "D:\\avatar-platform",
            "/home/user/",
            "~/.xfyun",
        )
        for source_file in PLUGIN_ROOT.rglob("*"):
            if not source_file.is_file():
                continue
            parts = source_file.parts
            if ("tests" in parts or "codex" in parts or "cursor" in parts
                    or ".runtime" in parts or "avatar-web-demo" in parts):
                continue
            # 迁移报告按设计记录了修复前的路径写法，作为文档不参与本扫描
            if source_file.name == "MIGRATION_REPORT.md":
                continue
            if source_file.suffix.lower() not in {
                ".md",
                ".py",
                ".json",
                ".yaml",
                ".yml",
                ".template",
                ".properties",
            }:
                continue
            content = source_file.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                self.assertNotIn(marker, content, f"{source_file}: {marker}")

    def test_skill_entrypoints_do_not_embed_example_scene_or_app_ids(self):
        forbidden_patterns = (
            re.compile(r"sceneId[^\n]{0,20}\b\d{12,}\b", re.IGNORECASE),
            re.compile(r"appId[^\n]{0,20}\b\d{8}\b", re.IGNORECASE),
        )
        for skill_file in skill_files():
            content = skill_file.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                self.assertIsNone(pattern.search(content), skill_file)


class ToolsRegistryTests(unittest.TestCase):
    def test_tools_yaml_parses(self):
        data = yaml.safe_load(TOOLS_CONFIG.read_text(encoding="utf-8"))
        self.assertIn("tools", data)
        self.assertGreater(len(data["tools"]), 0)

    def test_tool_names_are_unique(self):
        data = yaml.safe_load(TOOLS_CONFIG.read_text(encoding="utf-8"))
        names = [tool["name"] for tool in data["tools"]]
        self.assertEqual(len(names), len(set(names)))

    def test_tool_scripts_exist(self):
        data = yaml.safe_load(TOOLS_CONFIG.read_text(encoding="utf-8"))
        for tool in data["tools"]:
            script = PLUGIN_ROOT / tool["path"]
            self.assertTrue(script.is_file(), f"{tool['name']}: {tool['path']}")

    def test_declared_commands_exist_in_scripts(self):
        """tools.yaml 声明的 command 必须真实存在于脚本的命令分派中。"""
        import ast

        def script_commands(path):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            found = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                    if any(
                        isinstance(t, ast.Name) and t.id == "_COMMANDS"
                        for t in node.targets
                    ):
                        found.update(
                            key.value
                            for key in node.value.keys
                            if isinstance(key, ast.Constant)
                            and isinstance(key.value, str)
                        )
                if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                    continue
                if not isinstance(node.left, ast.Name) or node.left.id != "cmd":
                    continue
                comparator = node.comparators[0]
                if isinstance(node.ops[0], ast.Eq) and isinstance(
                    comparator, ast.Constant
                ):
                    if isinstance(comparator.value, str):
                        found.add(comparator.value)
                elif isinstance(node.ops[0], ast.In) and isinstance(
                    comparator, (ast.Tuple, ast.List)
                ):
                    found.update(
                        element.value
                        for element in comparator.elts
                        if isinstance(element, ast.Constant)
                        and isinstance(element.value, str)
                    )
            return found

        data = yaml.safe_load(TOOLS_CONFIG.read_text(encoding="utf-8"))
        for tool in data["tools"]:
            command = tool.get("command")
            if not command:
                continue
            script = PLUGIN_ROOT / tool["path"]
            self.assertIn(
                command,
                script_commands(script),
                f"{tool['name']}: command={command} not found in {tool['path']}",
            )

    def test_default_anchor_is_platform_default(self):
        """默认形象必须是平台默认 111310001，不是账号特定的历史值。"""
        content = TOOLS_CONFIG.read_text(encoding="utf-8")
        self.assertIn("默认111310001", content)
        self.assertNotIn("默认110117026", content)

        live_script = (PLUGIN_ROOT / "tools" / "xfyun_live.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('DEFAULT_ANCHOR_ID = "111310001"', live_script)


class GitignoreTests(unittest.TestCase):
    def test_runtime_and_credentials_are_ignored(self):
        content = (PLUGIN_ROOT / ".gitignore").read_text(encoding="utf-8")
        for entry in (".runtime/", "xfyun_cookies.json", ".env"):
            self.assertIn(entry, content, entry)


class AndroidGradleStabilityTests(unittest.TestCase):
    TEMPLATE_DIR = (
        SKILLS_ROOT / "avatar-executing" / "templates" / "android-build-template"
    )

    def test_stability_reference_exists(self):
        self.assertTrue((SKILLS_ROOT / "shared" / "android-gradle-stability.md").is_file())

    def test_gradle_properties_use_serial_bounded_build(self):
        content = (self.TEMPLATE_DIR / "gradle.properties").read_text(encoding="utf-8")
        self.assertIn("org.gradle.jvmargs=-Xmx1280m", content)
        self.assertIn("org.gradle.parallel=false", content)
        self.assertIn("org.gradle.workers.max=2", content)
        self.assertNotIn("-Xmx2048m", content)

    def test_settings_template_has_mirror_fallbacks(self):
        content = (self.TEMPLATE_DIR / "settings.gradle.template").read_text(
            encoding="utf-8"
        )
        for mirror in (
            "maven.aliyun.com",
            "mirrors.cloud.tencent.com",
            "repo.huaweicloud.com",
        ):
            self.assertIn(mirror, content, mirror)

    def test_wrapper_uses_domestic_mirror_and_timeout(self):
        content = (
            self.TEMPLATE_DIR / "gradle" / "wrapper" / "gradle-wrapper.properties"
        ).read_text(encoding="utf-8")
        self.assertIn("mirrors.cloud.tencent.com", content)
        self.assertIn("networkTimeout", content)

    def test_wrapper_jar_is_a_complete_gradle_wrapper(self):
        wrapper = self.TEMPLATE_DIR / "gradle" / "wrapper" / "gradle-wrapper.jar"
        self.assertTrue(wrapper.is_file())
        self.assertTrue(zipfile.is_zipfile(str(wrapper)))
        with zipfile.ZipFile(str(wrapper)) as archive:
            self.assertIn(
                "org/gradle/wrapper/GradleWrapperMain.class",
                archive.namelist(),
            )

    def test_build_skills_reference_stability_playbook(self):
        expected = {
            "avatar-workflow-entry",
            "avatar-executing",
            "avatar-verification",
            "avatar-troubleshoot",
            "toolchain",
        }
        for skill_name in expected:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("android-gradle-stability.md", content, skill_name)


if __name__ == "__main__":
    unittest.main()

    def test_default_live_assets_match_platform_defaults(self):
        live_source = (PLUGIN_ROOT / "tools" / "xfyun_live.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('DEFAULT_ANCHOR_ID = "111310001"', live_source)
        self.assertIn('DEFAULT_VCN = "x4_lingxiaoqi_oral"', live_source)
        tools_yaml = TOOLS_CONFIG.read_text(encoding="utf-8")
        self.assertIn("默认111310001", tools_yaml)
        self.assertNotIn("默认110117026", tools_yaml)


class AndroidGradleStabilityTests(unittest.TestCase):
    def test_gradle_stability_contract(self):
        shared = (SKILLS_ROOT / "shared" / "android-gradle-stability.md").read_text(
            encoding="utf-8"
        )
        template = (
            SKILLS_ROOT / "avatar-executing" / "templates" / "android-build-template"
        )
        gradle_properties = (template / "gradle.properties").read_text(encoding="utf-8")
        settings = (template / "settings.gradle.template").read_text(encoding="utf-8")
        wrapper = (
            template / "gradle" / "wrapper" / "gradle-wrapper.properties"
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

    def test_wrapper_jar_is_a_complete_gradle_wrapper(self):
        wrapper = (
            SKILLS_ROOT / "avatar-executing" / "templates" / "android-build-template"
            / "gradle" / "wrapper" / "gradle-wrapper.jar"
        )
        self.assertTrue(wrapper.is_file())
        self.assertTrue(zipfile.is_zipfile(str(wrapper)))
        with zipfile.ZipFile(str(wrapper)) as archive:
            self.assertIn(
                "org/gradle/wrapper/GradleWrapperMain.class",
                archive.namelist(),
            )

    def test_routed_skills_reference_stability_doc(self):
        routed_skills = (
            "avatar-workflow-entry",
            "toolchain",
            "avatar-executing",
            "avatar-troubleshoot",
            "avatar-verification",
        )
        for skill_name in routed_skills:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("android-gradle-stability.md", content, skill_name)


if __name__ == "__main__":
    unittest.main()
