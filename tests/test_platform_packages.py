"""Static and unit checks for the Cursor and Codex distribution packages."""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


REPO = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "iflytek-digital-human"
LEGACY_PLUGIN_NAME = "avatar-platform"
CLAUDE_PACKAGE = REPO / "claude" / PLUGIN_NAME
PACKAGES = {
    "cursor": REPO / "cursor",
    "codex": REPO / "plugins" / PLUGIN_NAME,
}
ALL_RUNTIME_PACKAGES = {
    "claude": CLAUDE_PACKAGE,
    **PACKAGES,
}
PLUGIN_ROOT_ENVS = {
    "claude": "CLAUDE_PLUGIN_ROOT",
    "cursor": "CURSOR_PLUGIN_ROOT",
    "codex": "CODEX_PLUGIN_ROOT",
}
FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    old_path = list(sys.path)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = old_path
    return module


class PlatformPackageTests(unittest.TestCase):
    def run_telemetry(self, platform, home, *args):
        root = PACKAGES[platform]
        env = os.environ.copy()
        env["CURSOR_HOME" if platform == "cursor" else "CODEX_HOME"] = str(home)
        env["XFYUN_AVATAR_COOKIE_FILE"] = str(home / "missing-cookie.json")
        env["IFLYTEK_DIGITAL_HUMAN_GATE_CONSENT_PATH"] = str(
            home / "gate-consent.json"
        )
        return subprocess.run(
            [sys.executable, str(root / "tools" / "telemetry.py"), *args],
            cwd=str(root), env=env, check=True, text=True,
            capture_output=True,
        ).stdout.strip()

    def test_manifests_and_required_resources_exist(self):
        manifests = {
            "claude": ".claude-plugin/plugin.json",
            "cursor": ".cursor-plugin/plugin.json",
            "codex": ".codex-plugin/plugin.json",
        }
        for platform, root in ALL_RUNTIME_PACKAGES.items():
            manifest = json.loads((root / manifests[platform]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], PLUGIN_NAME)
            self.assertEqual(manifest["version"], "1.1.0")
            package = root / "package.json"
            if package.is_file():
                self.assertEqual(
                    json.loads(package.read_text(encoding="utf-8"))["version"],
                    "1.1.0",
                    f"{platform}: package.json",
                )
            for relative in (
                "docs/capabilities.md",
                "config/privacy_notice.json",
                "config/telemetry.json",
                "tools/telemetry.py",
                "tools/telemetry_common.py",
                "tools/uploader.py",
                "tools/web_delivery.py",
                "tools/platform_endpoints.py",
                "skills/avatar-workflow-entry/SKILL.md",
                "skills/avatar-consent-gate/SKILL.md",
            ):
                self.assertTrue((root / relative).is_file(), f"{platform}: {relative}")

    def test_plugin_version_resolves_for_all_runtime_packages(self):
        for platform, root in ALL_RUNTIME_PACKAGES.items():
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                env = {
                    PLUGIN_ROOT_ENVS[platform]: str(root),
                    "IFLYTEK_DIGITAL_HUMAN_GATE_CONSENT_PATH": str(
                        Path(temp) / "gate-consent.json"
                    ),
                }
                if platform == "cursor":
                    env["CURSOR_HOME"] = str(Path(temp) / "cursor-home")
                if platform == "codex":
                    env["CODEX_HOME"] = str(Path(temp) / "codex-home")
                with mock.patch.dict("os.environ", env, clear=True), \
                        mock.patch("pathlib.Path.home", return_value=Path(temp)):
                    module = load_module(
                        root / "tools" / "telemetry_common.py",
                        f"telemetry_common_version_{platform}",
                    )
                    self.assertEqual(module.plugin_version(), "1.1.0")

    def test_plugin_version_can_be_overridden_for_repackaged_agents(self):
        for platform, root in ALL_RUNTIME_PACKAGES.items():
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                env = {
                    "IFLYTEK_DIGITAL_HUMAN_PLUGIN_VERSION": "9.9.9-test",
                    "IFLYTEK_DIGITAL_HUMAN_GATE_CONSENT_PATH": str(
                        Path(temp) / "gate-consent.json"
                    ),
                }
                if platform == "cursor":
                    env["CURSOR_HOME"] = str(Path(temp) / "cursor-home")
                if platform == "codex":
                    env["CODEX_HOME"] = str(Path(temp) / "codex-home")
                with mock.patch.dict("os.environ", env, clear=True), \
                        mock.patch("pathlib.Path.home", return_value=Path(temp)):
                    module = load_module(
                        root / "tools" / "telemetry_common.py",
                        f"telemetry_common_version_override_{platform}",
                    )
                    self.assertEqual(module.plugin_version(), "9.9.9-test")

    def test_marketplaces_use_new_plugin_identity(self):
        claude = json.loads(
            (REPO / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        codex = json.loads(
            (REPO / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        cursor = json.loads(
            (REPO / ".cursor-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(claude["name"], PLUGIN_NAME + "-marketplace")
        self.assertEqual(claude["plugins"][0]["name"], PLUGIN_NAME)
        self.assertEqual(
            claude["plugins"][0]["source"],
            "./claude/" + PLUGIN_NAME,
        )
        self.assertEqual(codex["name"], PLUGIN_NAME + "-codex")
        self.assertEqual(codex["plugins"][0]["name"], PLUGIN_NAME)
        self.assertEqual(
            codex["plugins"][0]["source"]["path"],
            "./plugins/" + PLUGIN_NAME,
        )
        self.assertEqual(cursor["name"], PLUGIN_NAME)

        claude_manifest = json.loads(
            (CLAUDE_PACKAGE / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(claude_manifest["name"], PLUGIN_NAME)

    def test_claude_hooks_use_new_plugin_command_prefix(self):
        intent = (CLAUDE_PACKAGE / "hooks" / "avatar_intent.py").read_text(
            encoding="utf-8"
        )
        tracker = (CLAUDE_PACKAGE / "hooks" / "tracker.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(PLUGIN_NAME, intent)
        self.assertIn(PLUGIN_NAME, tracker)

    def test_skill_frontmatter_matches_directory(self):
        for platform, root in PACKAGES.items():
            for skill in root.joinpath("skills").rglob("SKILL.md"):
                match = FRONTMATTER.match(skill.read_text(encoding="utf-8"))
                self.assertIsNotNone(match, f"{platform}: {skill}")
                data = yaml.safe_load(match.group(1)) or {}
                self.assertEqual(set(data), {"name", "description"}, str(skill))
                self.assertEqual(data.get("name"), skill.parent.name, str(skill))

    def test_tool_registry_paths_exist(self):
        for platform, root in PACKAGES.items():
            registry = yaml.safe_load((root / "config" / "tools.yaml").read_text(encoding="utf-8"))
            for tool in registry["tools"]:
                self.assertTrue((root / tool["path"]).is_file(), f"{platform}: {tool['path']}")

    def test_agent_skill_references_match_packaged_skills(self):
        for platform, root in PACKAGES.items():
            config = json.loads((root / "config" / "agents.json").read_text(encoding="utf-8"))
            available = {
                path.parent.name
                for path in (root / "skills").rglob("SKILL.md")
            }
            for agent in config.get("agents", []):
                for skill in agent.get("skills", []):
                    self.assertIn(skill, available, f"{platform}: {skill}")

    def test_package_does_not_ship_backup_skill_references(self):
        for platform, root in PACKAGES.items():
            backups = list((root / "skills").rglob("*.backup*"))
            self.assertEqual([], backups, f"{platform}: stale backup files {backups}")

    def test_platform_migration_docs_describe_hook_boundary(self):
        for platform, root in PACKAGES.items():
            text = (root / "docs" / "migration-codex-cursor.md").read_text(encoding="utf-8")
            self.assertIn("Claude Code 的 Hook 机制", text)
            self.assertIn("Cursor / Codex 适配包", text)
            self.assertIn("入口 Skill", text)

    def test_runtime_identity_is_platform_specific(self):
        for platform, root in PACKAGES.items():
            with tempfile.TemporaryDirectory() as temp:
                env_name = "CURSOR_HOME" if platform == "cursor" else "CODEX_HOME"
                with mock.patch.dict("os.environ", {env_name: temp}, clear=False):
                    module = load_module(
                        root / "tools" / "telemetry_common.py",
                        f"telemetry_common_{platform}",
                    )
                self.assertEqual(module.AGENT_NAME, platform)
                self.assertEqual(
                    module.TELEMETRY_DIR,
                    Path(temp) / PLUGIN_NAME / "telemetry",
                )

    def test_legacy_telemetry_is_copied_to_new_plugin_directory(self):
        for platform, root in PACKAGES.items():
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                legacy = home / LEGACY_PLUGIN_NAME / "telemetry"
                legacy.mkdir(parents=True)
                (legacy / "consent.json").write_text(
                    '{"accepted": false}', encoding="utf-8"
                )
                env_name = "CURSOR_HOME" if platform == "cursor" else "CODEX_HOME"
                with mock.patch.dict("os.environ", {env_name: temp}, clear=False):
                    module = load_module(
                        root / "tools" / "telemetry_common.py",
                        f"telemetry_common_legacy_{platform}",
                    )

                migrated = home / PLUGIN_NAME / "telemetry" / "consent.json"
                self.assertEqual(module.TELEMETRY_DIR, migrated.parent)
                self.assertEqual(migrated.read_text(encoding="utf-8"), '{"accepted": false}')
                self.assertTrue((legacy / "consent.json").is_file())

        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            legacy = home / ".claude" / LEGACY_PLUGIN_NAME / "telemetry"
            legacy.mkdir(parents=True)
            (legacy / "consent.json").write_text(
                '{"accepted": false}', encoding="utf-8"
            )
            with mock.patch("pathlib.Path.home", return_value=home):
                module = load_module(
                    CLAUDE_PACKAGE / "tools" / "telemetry_common.py",
                    "telemetry_common_legacy_claude",
                )

            migrated = (
                home / ".claude" / PLUGIN_NAME / "telemetry" / "consent.json"
            )
            self.assertEqual(module.TELEMETRY_DIR, migrated.parent)
            self.assertEqual(migrated.read_text(encoding="utf-8"), '{"accepted": false}')
            self.assertTrue((legacy / "consent.json").is_file())

    def test_uploader_defaults_to_platform_agent(self):
        for platform, root in PACKAGES.items():
            content = (root / "tools" / "uploader.py").read_text(encoding="utf-8")
            self.assertNotIn("or 'claude'", content)
            self.assertIn(f"or '{platform}'", content)

    def test_no_claude_plugin_root_dependency(self):
        for platform, root in PACKAGES.items():
            for base in (root / "skills", root / "tools"):
                for path in base.rglob("*"):
                    if path.is_file() and path.suffix.lower() in {".md", ".py"}:
                        self.assertNotIn(
                            "CLAUDE_PLUGIN_ROOT",
                            path.read_text(encoding="utf-8", errors="ignore"),
                            f"{platform}: {path}",
                        )

    def test_explicit_lifecycle_requires_consent(self):
        for platform in PACKAGES:
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                output = json.loads(self.run_telemetry(
                    platform, home, "start", "--type", "troubleshoot"))
                self.assertEqual(output, {
                    "status": "skipped", "reason": "disabled"})
                self.assertFalse(
                    (home / PLUGIN_NAME / "telemetry" / "state.json").exists())

    def test_consent_creates_and_validates_gate_credential(self):
        for platform in PACKAGES:
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                self.run_telemetry(platform, home, "consent", "--decline")
                gate = home / "gate-consent.json"
                value = json.loads(gate.read_text(encoding="utf-8"))
                self.assertEqual(value["schema_version"], 1)
                self.assertEqual(value["consent"], "declined")
                self.assertEqual(value["source"], "telemetry-cli")
                self.assertIn("recorded_at", value)
                self.assertEqual(
                    self.run_telemetry(platform, home, "consent", "--validate-gate"),
                    "valid (declined)",
                )
                value["consent"] = "accepted"
                gate.write_text(json.dumps(value), encoding="utf-8")
                self.assertEqual(
                    self.run_telemetry(platform, home, "consent", "--validate-gate"),
                    "invalid (inconsistent_status)",
                )

    def test_consent_status_does_not_bypass_missing_gate(self):
        for platform in PACKAGES:
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                self.run_telemetry(platform, home, "consent", "--accept")
                gate = home / "gate-consent.json"
                gate.unlink()
                self.assertEqual(
                    self.run_telemetry(platform, home, "consent", "--status"),
                    "accepted",
                )
                self.assertFalse(gate.is_file())
                self.assertEqual(
                    self.run_telemetry(platform, home, "consent", "--validate-gate"),
                    "invalid (missing)",
                )

    def test_explicit_lifecycle_records_and_deduplicates_skills(self):
        for platform in PACKAGES:
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                project = home / "project"
                project.mkdir()
                self.run_telemetry(platform, home, "consent", "--accept")
                started = json.loads(self.run_telemetry(
                    platform, home, "start", "--project", str(project)))
                workflow_id = started["workflowId"]
                self.assertTrue(workflow_id.startswith("wf_" + platform + "-"))

                command = (
                    "invoke", "--workflow", workflow_id,
                    "--skill", "avatar-executing",
                    "--type", "sdk_integration",
                )
                first = json.loads(self.run_telemetry(platform, home, *command))
                second = json.loads(self.run_telemetry(platform, home, *command))
                self.assertTrue(first["recorded"])
                self.assertFalse(second["recorded"])

                state_path = home / PLUGIN_NAME / "telemetry" / "state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(len(state["workflows"]), 1)
                self.assertEqual(state["workflows"][0]["agent"], platform)
                self.assertEqual(
                    state["workflows"][0]["workflow_type"], "sdk_integration")
                self.assertEqual(
                    [item["skill_name"] for item in state["invocations"]],
                    ["avatar-workflow-entry", "avatar-executing"],
                )
                self.assertTrue(all(
                    item["agent"] == platform for item in state["invocations"]))

                runtime = project / ".runtime"
                runtime.mkdir()
                (runtime / "verification-result.json").write_text(json.dumps({
                    "ready_to_deliver": True,
                    "issues_found": 0,
                    "issues_fixed": 0,
                }), encoding="utf-8")
                closed = self.run_telemetry(
                    platform, home, "complete", "--workflow", workflow_id,
                    "--type", "sdk_integration", "--project", str(project))
                self.assertEqual(closed, "completed via verification_flag")
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(state["workflows"][0]["status"], "completed")

    def test_entry_skill_documents_explicit_lifecycle(self):
        for platform, root in PACKAGES.items():
            content = (root / "skills" / "avatar-workflow-entry" /
                       "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("telemetry.py\" start", content, platform)
            self.assertIn("telemetry.py\" invoke", content, platform)
            self.assertIn("--workflow", content, platform)


if __name__ == "__main__":
    unittest.main()
