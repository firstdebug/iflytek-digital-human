"""运行数据与凭据安全测试。

对应 Codex 侧 tests/test_runtime_security.py，路径断言改为 Claude 技能包根目录。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "claude" / "iflytek-digital-human"
TOOLS_DIR = PLUGIN_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import write_env_safe
import xfyun_common
import xfyun_secrets


class CookiePathTests(unittest.TestCase):
    def test_default_cookie_path_is_in_plugin_runtime_directory(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XFYUN_AVATAR_COOKIE_FILE", None)
            self.assertEqual(
                xfyun_common.resolve_cookie_file(),
                PLUGIN_ROOT / ".runtime" / "xfyun_cookies.json",
            )

    def test_cookie_path_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            expected = Path(temp_dir) / "session.json"
            with mock.patch.dict(
                os.environ, {"XFYUN_AVATAR_COOKIE_FILE": str(expected)}
            ):
                self.assertEqual(xfyun_common.resolve_cookie_file(), expected.resolve())

    def test_save_cookies_creates_parent_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file = Path(temp_dir) / "nested" / "cookies.json"
            cookies = {"ssoSessionId": "session", "account_id": "account"}
            with mock.patch.object(xfyun_common, "COOKIE_FILE", cookie_file):
                xfyun_common.save_cookies(cookies)
                self.assertEqual(xfyun_common.load_cookies(), cookies)


class MaskSecretTests(unittest.TestCase):
    def test_default_secret_path_is_in_plugin_runtime_directory(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XFYUN_AVATAR_SECRETS_DIR", None)
            self.assertEqual(
                xfyun_secrets.resolve_secrets_dir(),
                PLUGIN_ROOT / ".runtime" / "secrets",
            )

    def test_secret_path_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                os.environ, {"XFYUN_AVATAR_SECRETS_DIR": temp_dir}
            ):
                self.assertEqual(
                    xfyun_secrets.resolve_secrets_dir(), Path(temp_dir).resolve()
                )

    def test_zero_suffix_does_not_reveal_original_value(self):
        original = "https://example.test/private/token"
        masked = xfyun_secrets.mask_secret(original, show_prefix=8, show_suffix=0)
        self.assertEqual(masked, "https://********")
        self.assertNotIn(original, masked)

    def test_short_value_is_fully_masked(self):
        self.assertEqual(xfyun_secrets.mask_secret("short"), "*****")

    def test_negative_visibility_is_rejected(self):
        with self.assertRaises(ValueError):
            xfyun_secrets.mask_secret("secret", show_suffix=-1)


class WriteEnvHelpersTests(unittest.TestCase):
    def test_find_app_record_requires_exact_app_id(self):
        records = [{"appId": "wrong"}, {"appId": "target"}]
        self.assertEqual(
            write_env_safe.find_app_record(records, "target"), records[1]
        )
        self.assertIsNone(write_env_safe.find_app_record(records, "missing"))

    def test_output_path_expands_user_marker(self):
        with mock.patch.object(
            write_env_safe.os.path, "expanduser", return_value="C:/resolved/.env"
        ) as expanduser:
            result = write_env_safe.resolve_output_path("~/.env")
        expanduser.assert_called_once_with("~/.env")
        self.assertEqual(result, Path("C:/resolved/.env"))

    def test_env_content_uses_platform_defaults(self):
        content = write_env_safe.build_env_content(
            "app", "key", "secret", "scene"
        )
        self.assertIn("XF_AVATAR_ID=111310001", content)
        self.assertIn("XF_VCN=x4_lingxiaoqi_oral", content)

    def test_env_content_allows_explicit_asset_overrides(self):
        content = write_env_safe.build_env_content(
            "app", "key", "secret", "scene", "authorized-avatar", "authorized-vcn"
        )
        self.assertIn("XF_AVATAR_ID=authorized-avatar", content)
        self.assertIn("XF_VCN=authorized-vcn", content)

    def test_write_env_selects_exact_record_and_creates_parent(self):
        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "flag": True,
                    "data": {
                        "records": [
                            {
                                "appId": "wrong",
                                "apiKey": "wrong-key",
                                "apiSecret": "wrong-secret",
                            },
                            {
                                "appId": "target",
                                "apiKey": "target-key-value",
                                "apiSecret": "target-secret-value",
                            },
                        ]
                    },
                }

        class FakeSession:
            @staticmethod
            def post(*args, **kwargs):
                return FakeResponse()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "nested" / ".env"
            with mock.patch.object(write_env_safe.xc, "get_session", return_value=FakeSession()), \
                    mock.patch.object(write_env_safe.xc, "post", return_value=FakeResponse.json()):
                self.assertTrue(
                    write_env_safe.write_env("target", "scene", output_file)
                )

            content = output_file.read_text(encoding="utf-8")
            self.assertIn("XF_API_KEY=target-key-value", content)
            self.assertIn("XF_API_SECRET=target-secret-value", content)
            self.assertNotIn("wrong-key", content)


class QueryServicesReusesCommonSessionTests(unittest.TestCase):
    def test_query_services_does_not_duplicate_login_stack(self):
        source = (TOOLS_DIR / "xfyun_query_services.py").read_text(encoding="utf-8")
        self.assertIn("import xfyun_common as xc", source)
        self.assertIn("xc.get_session()", source)
        # 重复的登录/Cookie 实现必须已删除，避免两套登录态互相覆盖
        for duplicated in ("def do_browser_login", "def wait_for_login", "def save_cookies"):
            self.assertNotIn(duplicated, source)


if __name__ == "__main__":
    unittest.main()
