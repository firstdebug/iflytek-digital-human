import re
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"
FRONTMATTER_PATTERN = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)


def skill_files():
    return sorted(SKILLS_ROOT.rglob("SKILL.md"))


class SkillStructureTests(unittest.TestCase):
    def test_all_skill_names_use_avatar_prefix_and_match_folder(self):
        names = []
        for skill_file in skill_files():
            match = FRONTMATTER_PATTERN.match(skill_file.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, skill_file)
            frontmatter = yaml.safe_load(match.group(1))
            name = frontmatter["name"]
            self.assertTrue(name.startswith("avatar-"), skill_file)
            self.assertEqual(skill_file.parent.name, name, skill_file)
            names.append(name)
        self.assertEqual(len(names), len(set(names)), "Skill names must be unique")

    def test_frontmatter_contains_only_codex_trigger_fields(self):
        for skill_file in skill_files():
            match = FRONTMATTER_PATTERN.match(skill_file.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, skill_file)
            frontmatter = yaml.safe_load(match.group(1))
            self.assertEqual(set(frontmatter), {"name", "description"}, skill_file)
            self.assertTrue(frontmatter["description"].strip(), skill_file)

    def test_skill_sources_have_no_machine_specific_paths(self):
        forbidden = ("C:\\Users\\shfan4", "~/.claude", "AskUserQuestion")
        for source_file in SKILLS_ROOT.rglob("*"):
            if not source_file.is_file():
                continue
            if source_file.suffix.lower() not in {".md", ".py", ".json", ".yaml", ".yml"}:
                continue
            content = source_file.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, content, source_file)

    def test_no_backup_files_are_packaged(self):
        backups = [
            path
            for path in PLUGIN_ROOT.rglob("*")
            if path.is_file() and (".backup" in path.name or path.suffix == ".bak")
        ]
        self.assertEqual(backups, [])


if __name__ == "__main__":
    unittest.main()
