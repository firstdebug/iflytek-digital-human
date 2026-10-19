import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = PLUGIN_ROOT / "tools" / "xfyun_subscription.py"


def load_tool():
    sys.path.insert(0, str(TOOL_PATH.parent))
    try:
        spec = importlib.util.spec_from_file_location("xfyun_subscription_test", TOOL_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def flatten_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from flatten_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from flatten_keys(child)


class SubscriptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def test_interface_product_default_payload(self):
        payload = self.tool.build_order_payload(1)
        self.assertEqual(payload, {
            "appType": 1,
            "orderType": 2,
            "appName": "123",
            "appDesc": "123",
            "company": "123",
            "contact": "",
            "phone": "",
            "effectTime": 2592000000,
            "avatarInteraction": {
                "avatarInteractionConcNum": 1,
                "avatarInteractionTime": 12000000,
            },
            "llmConversation": {
                "llmTokensNum": 1,
                "llmDialogNum": 500000,
                "llmDocNum": 100,
            },
            "sceneNum": 3,
        })
        self.assertEqual(self.tool.REVIEW_POLICIES[1], "auto_review")

    def test_standard_product_default_payload(self):
        payload = self.tool.build_order_payload(2)
        self.assertEqual(payload, {
            "appType": 2,
            "orderType": 2,
            "appName": "应用申请",
            "appDesc": "应用申请123",
            "company": "应用申请",
            "contact": "",
            "phone": "",
            "effectTime": 604800000,
            "avatarInteraction": {"avatarInteractionConcNum": 1},
            "llmConversation": {
                "llmTokensNum": 1,
                "llmDialogNum": 500000,
                "llmDocNum": 100,
            },
            "productType": ["WEB_CONVERSATION", "PC_ASSISTANT", "DIGITAL_LIVE"],
            "sceneNum": 3,
        })
        self.assertEqual(self.tool.REVIEW_POLICIES[2], "operations_review")

    def test_default_payloads_do_not_contain_captcha(self):
        for app_type in (1, 2):
            self.assertNotIn("captcha", {key.lower() for key in flatten_keys(self.tool.build_order_payload(app_type))})

    def test_cli_maps_custom_arguments_to_api_camel_case(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.tool.main([
                "1", "--dry-run", "--app-name", "接口应用", "--app-desc", "接口描述",
                "--effect-time", "42", "--scene-num", "7",
            ])
        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["appName"], "接口应用")
        self.assertEqual(payload["appDesc"], "接口描述")
        self.assertEqual(payload["effectTime"], 42)
        self.assertEqual(payload["sceneNum"], 7)
        self.assertNotIn("app_name", payload)
        self.assertNotIn("appname", payload)


if __name__ == "__main__":
    unittest.main()
