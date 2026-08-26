import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "avatar-grill" / "scripts" / "validate_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_contract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def contract():
    return {
        "schema_version": "1.0",
        "contract_id": "avatar-run-test-001",
        "status": "draft",
        "task": {"kind": "sdk_build", "goal": "test", "project_path": "D:/tests/avatar"},
        "platform": {"value": "web", "source": "user", "verified": True},
        "features": {"enabled": ["text_interact"], "excluded": ["voice_interact", "full_duplex"]},
        "resources": {
            "ws_url": {"value": MODULE.WS_URL, "source": "avatar-platform-constant", "verified": True},
            "app_id": {"value": "app-test", "source": "platform-query", "app_type": 1, "verified": True},
            "scene_id": {"value": "scene-test", "source": "platform-query", "paired_app_id": "app-test", "published": True, "verified": True},
        },
        "decisions": {"interaction": "text", "protocol": "xrtc"},
        "allowed_mutations": ["create_project_files", "write_env", "download_sdk"],
        "acceptance": ["build_passed"],
        "confirmation": {"confirmed": False, "confirmed_at": None},
    }


class ContractValidationTests(unittest.TestCase):
    def test_valid_draft(self):
        self.assertEqual(MODULE.validate(contract()), [])

    def test_wrong_ws_url_is_rejected(self):
        data = contract()
        data["resources"]["ws_url"]["value"] = "wss://wrong.example/v1/interact"
        self.assertTrue(any("canonical platform URL" in e for e in MODULE.validate(data)))

    def test_unpaired_scene_is_rejected(self):
        data = contract()
        data["resources"]["scene_id"]["paired_app_id"] = "other-app"
        self.assertTrue(any("paired_app_id" in e for e in MODULE.validate(data)))

    def test_secret_and_placeholder_are_rejected(self):
        data = contract()
        data["apiSecret"] = "secret"
        data["task"]["project_path"] = "<project>"
        errors = MODULE.validate(data)
        self.assertTrue(any("secret field" in e for e in errors))
        self.assertTrue(any("placeholder" in e for e in errors))

    def test_generic_type_is_not_treated_as_placeholder(self):
        data = contract()
        data["task"]["goal"] = "实现 List<String> API"
        self.assertFalse(any("placeholder" in e for e in MODULE.validate(data)))

    def test_allowed_mutations_is_required(self):
        data = contract()
        del data["allowed_mutations"]
        self.assertTrue(any("allowed_mutations" in e for e in MODULE.validate(data)))

    def test_unknown_mutation_is_rejected(self):
        data = contract()
        data["allowed_mutations"].append("invent_platform_operation")
        self.assertTrue(any("unknown allowed_mutations" in e for e in MODULE.validate(data)))

    def test_diagnose_allows_read_only_or_local_repairs(self):
        for mutations in (
            [],
            ["none"],
            ["create_project_files"],
            ["update_config"],
            ["create_project_files", "update_config"],
        ):
            data = contract()
            data["task"]["kind"] = "diagnose"
            data["allowed_mutations"] = mutations
            self.assertEqual(MODULE.validate(data), [], mutations)

    def test_diagnose_rejects_platform_mutations(self):
        for mutation in ("publish_scene", "create_knowledge_base"):
            data = contract()
            data["task"]["kind"] = "diagnose"
            data["allowed_mutations"] = [mutation]
            self.assertTrue(
                any("task.kind=diagnose mutation is invalid" in error for error in MODULE.validate(data)),
                mutation,
            )

    def test_docs_and_verify_reject_all_write_mutations(self):
        for task_kind in ("docs", "verify"):
            data = contract()
            data["task"]["kind"] = task_kind
            data["allowed_mutations"] = ["create_project_files"]
            self.assertTrue(
                any("only allows no mutations" in error for error in MODULE.validate(data)),
                task_kind,
            )

    def test_reused_knowledge_base_only_requires_selected_operations(self):
        data = contract()
        data["task"]["kind"] = "knowledge_base"
        data["allowed_mutations"] = ["enable_knowledge"]
        data["resources"]["knowledge_base"] = {
            "mode": "existing",
            "value": "kb-test",
            "enable": True,
        }
        self.assertEqual(MODULE.validate(data), [])

        data["resources"]["knowledge_base"]["publish"] = True
        self.assertTrue(any(
            "publish_scene" in error for error in MODULE.validate(data)
        ))
        data["allowed_mutations"].append("publish_scene")
        self.assertEqual(MODULE.validate(data), [])

    def test_new_knowledge_base_requires_create_mutation(self):
        data = contract()
        data["task"]["kind"] = "knowledge_base"
        data["allowed_mutations"] = ["enable_knowledge"]
        data["resources"]["knowledge_base"] = {
            "mode": "create",
            "enable": True,
        }
        self.assertTrue(
            any("create_knowledge_base" in error for error in MODULE.validate(data))
        )

    def test_reused_model_requires_only_selected_bind_and_publish(self):
        data = contract()
        data["task"]["kind"] = "model_config"
        data["allowed_mutations"] = ["bind_model"]
        data["resources"]["model"] = {
            "mode": "existing",
            "value": "model-test",
            "bind": True,
            "publish": False,
        }
        self.assertEqual(MODULE.validate(data), [])

        data["resources"]["model"]["publish"] = True
        self.assertTrue(any(
            "publish_scene" in error for error in MODULE.validate(data)
        ))
        data["allowed_mutations"].append("publish_scene")
        self.assertEqual(MODULE.validate(data), [])

    def test_sdk_extend_can_reuse_sdk_and_existing_env(self):
        data = contract()
        data["task"]["kind"] = "sdk_extend"
        data["allowed_mutations"] = ["create_project_files"]
        self.assertEqual(MODULE.validate(data), [])

    def test_sdk_build_requires_only_project_creation_by_default(self):
        data = contract()
        data["allowed_mutations"] = ["create_project_files"]
        self.assertEqual(MODULE.validate(data), [])

        data["allowed_mutations"] = ["download_sdk"]
        self.assertTrue(any(
            "create_project_files" in error for error in MODULE.validate(data)
        ))

    def test_sdk_extend_download_and_env_write_follow_resource_intent(self):
        data = contract()
        data["task"]["kind"] = "sdk_extend"
        data["allowed_mutations"] = ["create_project_files"]
        data["resources"]["sdk"] = {"mode": "download"}
        data["resources"]["credentials"] = {"write_env": True}
        errors = MODULE.validate(data)
        self.assertTrue(any("download_sdk" in error for error in errors))
        self.assertTrue(any("write_env" in error for error in errors))

        data["allowed_mutations"].extend(["download_sdk", "write_env"])
        self.assertEqual(MODULE.validate(data), [])

    def test_webapi_demo_requires_project_files_mutation(self):
        data = contract()
        data["task"]["kind"] = "webapi"
        data["allowed_mutations"] = ["update_config"]
        self.assertTrue(
            any("create_project_files" in error for error in MODULE.validate(data))
        )

    def test_voice_requires_explicit_permission_confirmation(self):
        data = contract()
        data["features"]["enabled"] = ["voice_interact"]
        data["features"]["excluded"] = ["full_duplex"]
        errors = MODULE.validate(data)
        self.assertTrue(any("voice_interaction" in e for e in errors))
        self.assertTrue(any("microphone_confirmed" in e for e in errors))

    def test_transparent_background_requires_xrtc(self):
        data = contract()
        data["features"]["enabled"] = ["transparent_bg"]
        data["decisions"]["protocol"] = "webrtc"
        self.assertTrue(any("transparent_bg" in e for e in MODULE.validate(data)))

    def test_confirmed_status_requires_confirmation(self):
        data = contract()
        data["status"] = "confirmed"
        self.assertTrue(any("confirmation.confirmed" in e for e in MODULE.validate(data)))

    def test_completed_requires_evidence(self):
        data = contract()
        data["status"] = "completed"
        data["confirmation"]["confirmed"] = True
        self.assertTrue(any("requires evidence" in e for e in MODULE.validate(data)))

    def test_create_scene_does_not_require_preexisting_scene_id(self):
        data = contract()
        data["resources"]["scene_id"] = {"mode": "create", "target_app_id": "app-test"}
        data["allowed_mutations"].append("create_interface_scene")
        self.assertFalse(any("scene_id" in e for e in MODULE.validate(data)))

    def test_unpublished_existing_scene_is_allowed_while_draft(self):
        data = contract()
        data["resources"]["scene_id"]["published"] = False
        self.assertEqual(MODULE.validate(data), [])

    def test_unpublished_scene_requires_publish_authorization_before_execution(self):
        data = contract()
        data["status"] = "confirmed"
        data["confirmation"]["confirmed"] = True
        data["resources"]["scene_id"]["published"] = False
        self.assertTrue(any("publish_scene" in e for e in MODULE.validate(data)))

        data["allowed_mutations"].append("publish_scene")
        self.assertEqual(MODULE.validate(data), [])

    def test_completed_existing_scene_must_be_published(self):
        data = contract()
        data["status"] = "completed"
        data["confirmation"]["confirmed"] = True
        data["evidence"] = [".runtime/verification-result.json"]
        data["allowed_mutations"].append("publish_scene")
        data["resources"]["scene_id"]["published"] = False
        self.assertTrue(any("must be published" in e for e in MODULE.validate(data)))

    def test_created_scene_cannot_have_value_before_verification(self):
        data = contract()
        data["status"] = "executing"
        data["confirmation"]["confirmed"] = True
        data["allowed_mutations"].extend(["create_interface_scene", "publish_scene"])
        data["resources"]["scene_id"] = {
            "mode": "create",
            "target_app_id": "app-test",
            "value": "scene-created-too-early",
        }
        self.assertTrue(any("before verification" in e for e in MODULE.validate(data)))

    def test_completed_created_scene_requires_resolved_platform_fields(self):
        data = contract()
        data["status"] = "completed"
        data["confirmation"]["confirmed"] = True
        data["evidence"] = [".runtime/verification-result.json"]
        data["allowed_mutations"].extend(["create_interface_scene", "publish_scene"])
        data["resources"]["scene_id"] = {
            "mode": "create",
            "target_app_id": "app-test",
        }
        errors = MODULE.validate(data)
        for field in ("value", "source", "verified=true", "published=true"):
            self.assertTrue(any(field in error for error in errors), field)

    def test_completed_created_scene_accepts_resolved_platform_fields(self):
        data = contract()
        data["status"] = "completed"
        data["confirmation"]["confirmed"] = True
        data["evidence"] = [".runtime/verification-result.json"]
        data["allowed_mutations"].extend(["create_interface_scene", "publish_scene"])
        data["resources"]["scene_id"] = {
            "mode": "create",
            "target_app_id": "app-test",
            "value": "scene-created",
            "source": "platform-query",
            "verified": True,
            "published": True,
        }
        self.assertEqual(MODULE.validate(data), [])

    def test_docs_contract_does_not_require_platform_resources(self):
        data = contract()
        data["task"]["kind"] = "docs"
        data["platform"] = {"value": "unspecified", "source": "user", "verified": True}
        data["resources"] = {}
        data["allowed_mutations"] = []
        self.assertEqual(MODULE.validate(data), [])

    def test_cli_accepts_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(contract()), encoding="utf-8")
            self.assertEqual(MODULE.main([str(path)]), 0)

    def test_skill_is_single_grill_entry_and_does_not_route_old_workflow(self):
        content = (ROOT / "skills" / "avatar-grill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: avatar-grill", content)
        self.assertIn("references/question-tree.md", content)
        self.assertIn("scripts/validate_contract.py", content)
        self.assertIn("references/capability-execution.md", content)

    def test_all_three_manifests_point_to_root_skills(self):
        for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json"):
            data = json.loads((ROOT / name).read_text(encoding="utf-8"))
            self.assertEqual(data["skills"], "./skills/")
            self.assertEqual(data["name"], "avatar-grill")


if __name__ == "__main__":
    unittest.main()
