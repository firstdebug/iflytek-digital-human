import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PLUGIN_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import sdk_artifact
import web_sdk_gate
import websocket_auth


SDK_TYPES = """
interface IAvatarPlatform {
  setApiInfo(apiInfo: ApiInfo): this
  setGlobalParams(config: IGlobalConfig): this
  start(startProps?: StartProps): Promise<void>
  writeText(text: string, extend: TextDriverExtend): Promise<string>
}
export { SDKEvents, PlayerEvents, IAvatarPlatform as default };
"""


def pass_node_check(_server):
    return True, None


def pass_server_smoke(_project):
    return True, []


def write_valid_project(root):
    sdk_dir = root / "sdk" / "avatar-sdk" / "esm"
    sdk_dir.mkdir(parents=True)
    entry = sdk_dir / "index.js"
    entry.write_text("export default class AvatarPlatform {}", encoding="utf-8")
    (sdk_dir / "index.d.ts").write_text(SDK_TYPES, encoding="utf-8")
    result = sdk_artifact.ensure_artifact("web", root)
    websocket_auth.install(root)

    (root / ".env").write_text(
        "\n".join(
            (
                "APP_ID=542c98ba",
                "API_KEY=1234567890abcdef",
                "API_SECRET=1234567890abcdef1234567890abcdef",
                "SCENE_ID=335328879436763136",
                "AVATAR_ID=111310001",
                "VCN=x4_lingxiaoqi_oral",
                "WS_URL=wss://avatar.example.test/v1/interact",
            )
        ),
        encoding="utf-8",
    )
    (root / "server.js").write_text(
        """
import { avatarAuthHandler, avatarConfigHandler } from './xfyun-auth.mjs';
app.get('/api/config', avatarConfigHandler);
app.get('/api/avatar-auth', avatarAuthHandler);
""",
        encoding="utf-8",
    )
    public = root / "public"
    public.mkdir()
    (public / "app.js").write_text(
        """
const module = await import('/sdk/avatar-sdk/esm/index.js');
const AvatarPlatform = module.default;
const { SDKEvents, PlayerEvents } = module;
const avatar = new AvatarPlatform();
avatar.setApiInfo({ serverUrl, appId, sceneId });
avatar.setGlobalParams({ avatar: { stream: { protocol: 'xrtc', fps: 25,
  bitrate: 2000, alpha: 0 } } });
avatar.on(SDKEvents.connected, onConnected);
avatar.on(SDKEvents.stream_start, onStreamStart);
await avatar.start({ wrapper });
await avatar.writeText('test', { nlp: true });
""",
        encoding="utf-8",
    )
    return result


class SdkArtifactTests(unittest.TestCase):
    def test_existing_web_sdk_is_hashed_and_manifested(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sdk_dir = root / "sdk" / "avatar-sdk" / "esm"
            sdk_dir.mkdir(parents=True)
            entry = sdk_dir / "index.js"
            entry.write_text("export default class AvatarPlatform {}", encoding="utf-8")
            (sdk_dir / "index.d.ts").write_text(SDK_TYPES, encoding="utf-8")

            result = sdk_artifact.ensure_artifact("web", root)

            self.assertEqual(result["status"], "already_exists")
            self.assertEqual(result["artifact_status"], "ready")
            self.assertEqual(
                result["sha256"], hashlib.sha256(entry.read_bytes()).hexdigest()
            )
            manifest = json.loads(
                (root / ".runtime" / "sdk-artifact.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["entry"], "sdk/avatar-sdk/esm/index.js")

    def test_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "sdk.zip"
            with zipfile.ZipFile(str(archive), "w") as zipped:
                zipped.writestr("../outside.txt", "unsafe")

            with self.assertRaises(sdk_artifact.ArtifactError):
                sdk_artifact.extract_zip_safely(archive, root / "extract")
            self.assertFalse((root / "outside.txt").exists())


class WebSdkGateTests(unittest.TestCase):
    def test_static_pass_without_browser_evidence_is_not_deliverable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_project(root)

            result = web_sdk_gate.run_checks(
                root,
                required_interaction="text",
                node_check=pass_node_check,
                server_smoke=pass_server_smoke,
            )

            self.assertEqual(result["status"], "needs_runtime_verification")
            self.assertFalse(result["ready_to_deliver"])
            self.assertEqual(result["static_issues"], [])
            marker = json.loads(
                (root / ".runtime" / "verification-result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(marker["ready_to_deliver"])
            self.assertIn("connected", marker["remaining_issues"])

    def test_hallucinated_sdk_api_fails_static_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_project(root)
            app = root / "public" / "app.js"
            app.write_text(
                app.read_text(encoding="utf-8")
                + "\navatar.setServerUrl(serverUrl);\nplayer = avatar.getPlayer();",
                encoding="utf-8",
            )

            result = web_sdk_gate.run_checks(
                root,
                required_interaction="text",
                node_check=pass_node_check,
                server_smoke=pass_server_smoke,
            )

            self.assertEqual(result["status"], "failed")
            self.assertIn("hallucinated_api:setServerUrl", result["static_issues"])
            self.assertIn("hallucinated_api:getPlayer", result["static_issues"])

    def test_ready_requires_all_browser_events_and_target_interaction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_project(root)
            runtime = root / ".runtime"
            runtime.mkdir(exist_ok=True)
            fingerprint = web_sdk_gate.project_fingerprint(root)
            (runtime / "web-runtime-evidence.json").write_text(
                json.dumps(
                    {
                        "source": "playwright",
                        "project_fingerprint": fingerprint,
                        "connected": True,
                        "stream_start": True,
                        "first_frame": True,
                        "target_interaction": "text",
                        "target_interaction_passed": True,
                        "errors": [],
                    }
                ),
                encoding="utf-8",
            )

            result = web_sdk_gate.run_checks(
                root,
                required_interaction="text",
                node_check=pass_node_check,
                server_smoke=pass_server_smoke,
            )

            self.assertEqual(result["status"], "ready_to_deliver")
            self.assertTrue(result["ready_to_deliver"])
            self.assertEqual(result["remaining_issues"], [])

    def test_core_runtime_success_ignores_generic_resource_404(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_project(root)
            runtime = root / ".runtime"
            runtime.mkdir(exist_ok=True)
            fingerprint = web_sdk_gate.project_fingerprint(root)
            (runtime / "web-runtime-evidence.json").write_text(
                json.dumps({
                    "source": "playwright",
                    "project_fingerprint": fingerprint,
                    "connected": True,
                    "stream_start": True,
                    "first_frame": True,
                    "target_interaction": "voice",
                    "target_interaction_passed": True,
                    "errors": [
                        "Failed to load resource: the server responded "
                        "with a status of 404 (Not Found)"
                    ],
                }), encoding="utf-8")

            result = web_sdk_gate.run_checks(
                root, required_interaction="voice",
                node_check=pass_node_check, server_smoke=pass_server_smoke)

            self.assertTrue(result["ready_to_deliver"])
            self.assertEqual(result["runtime_issues"], [])

    def test_authentication_failure_blocks_completion_before_success_flags(self):
        for error in ("avatar authentication failed",
                      {"code": 11203, "message": "concurrency exceeded"}):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                write_valid_project(root)
                runtime = root / ".runtime"
                runtime.mkdir(exist_ok=True)
                (runtime / "web-runtime-evidence.json").write_text(
                    json.dumps({
                        "source": "browser",
                        "connected": True,
                        "stream_start": True,
                        "first_frame": True,
                        "target_interaction": "text",
                        "target_interaction_passed": True,
                        "errors": [error],
                    }), encoding="utf-8")
                result = web_sdk_gate.run_checks(
                    root, required_interaction="text",
                    node_check=pass_node_check, server_smoke=pass_server_smoke)
                self.assertFalse(result["ready_to_deliver"])
                self.assertEqual(result["runtime_issues"][0], "authentication_failed")
                self.assertIn("runtime_errors", result["runtime_issues"])

    def test_short_masked_secret_is_rejected_without_exposing_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_project(root)
            env_file = root / ".env"
            content = env_file.read_text(encoding="utf-8")
            env_file.write_text(
                content.replace(
                    "API_SECRET=1234567890abcdef1234567890abcdef",
                    "API_SECRET=ZmQxZmIy",
                ),
                encoding="utf-8",
            )

            result = web_sdk_gate.run_checks(
                root,
                required_interaction="text",
                node_check=pass_node_check,
                server_smoke=pass_server_smoke,
            )

            encoded = json.dumps(result)
            self.assertIn("credential_invalid:api_secret", result["static_issues"])
            self.assertNotIn("ZmQxZmIy", encoded)

    def test_server_startup_and_endpoints_are_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_valid_project(root)

            result = web_sdk_gate.run_checks(
                root,
                required_interaction="text",
                node_check=pass_node_check,
                server_smoke=lambda _project: (
                    False,
                    ["auth_endpoint_failed"],
                ),
            )

            self.assertEqual(result["status"], "failed")
            self.assertIn("auth_endpoint_failed", result["static_issues"])


if __name__ == "__main__":
    unittest.main()
