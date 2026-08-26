#!/usr/bin/env python3
"""Validate an avatar-grill execution contract without contacting the platform."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(TOOLS_DIR))
from platform_endpoints import CANONICAL_WS_URL  # noqa: E402


SECRET_KEYS = {
    "apikey",
    "api_key",
    "apisecret",
    "api_secret",
    "authorization",
    "cookie",
    "access_token",
    "refresh_token",
    "password",
    "private_key",
}
WS_URL = CANONICAL_WS_URL
PLACEHOLDER = re.compile(
    r"<(?:verified-app-id|verified-scene-id|project|sceneId|appId|"
    r"project-path|your-[a-z0-9_-]+)>",
    re.IGNORECASE,
)
KNOWN_PLATFORMS = {"web", "android", "ios", "webapi", "template", "live", "unspecified"}
KNOWN_TASKS = {
    "docs", "sdk_build", "sdk_extend", "web_template", "live_streaming",
    "webapi", "credentials", "resource_management", "model_config",
    "knowledge_base", "configuration", "permissions", "diagnose", "verify",
}
WS_TASKS = {"sdk_build", "sdk_extend", "webapi"}
APP_TASKS = {
    "sdk_build", "sdk_extend", "web_template", "live_streaming", "webapi",
    "credentials", "resource_management", "model_config", "knowledge_base",
}
SCENE_TASKS = {
    "sdk_build", "sdk_extend", "web_template", "live_streaming", "webapi",
    "model_config", "knowledge_base",
}
SCENE_RUNTIME_TASKS = {
    "sdk_build", "sdk_extend", "webapi", "web_template", "live_streaming",
}
READ_ONLY_TASKS = {"docs", "verify"}
DIAGNOSE_MUTATIONS = {"create_project_files", "update_config"}
KNOWN_MUTATIONS = {
    "none",
    "create_project_files",
    "write_env",
    "download_sdk",
    "create_interface_scene",
    "publish_scene",
    "create_template",
    "create_live",
    "bind_model",
    "create_knowledge_base",
    "upload_knowledge",
    "enable_knowledge",
    "update_config",
}
TASK_MINIMUM_MUTATIONS = {
    "sdk_build": {"create_project_files"},
    "sdk_extend": {"create_project_files"},
    "webapi": {"create_project_files"},
    "web_template": {"create_template"},
    "live_streaming": {"create_live"},
    "credentials": {"write_env"},
    "configuration": {"update_config"},
    "permissions": {"create_project_files"},
}

# docs、verify 仍然只读；diagnose 可以只诊断，或只修复本地工程配置。
# 平台写操作必须回到 Grill，修改 task.kind 或补充授权后重新确认契约。
DIAGNOSE_MUTATION_POLICY = "docs、verify 只允许 [] 或 [none]；diagnose 只允许空操作、create_project_files 或 update_config，其他平台写操作必须回到 Grill 重新确认契约。"
KNOWN_STATUSES = {
    "draft",
    "confirmed",
    "executing",
    "verifying",
    "completed",
    "blocked",
    "failed",
}


def _walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + (str(index),))


def validate(data):
    errors = []
    if not isinstance(data, dict):
        return ["contract root must be an object"]

    required = ("schema_version", "contract_id", "status", "task",
                "platform", "features", "resources", "acceptance",
                "confirmation", "allowed_mutations")
    for key in required:
        if key not in data:
            errors.append(f"missing required field: {key}")

    status = data.get("status")
    if status not in KNOWN_STATUSES:
        errors.append(f"status must be one of {sorted(KNOWN_STATUSES)}")

    for path, value in _walk(data):
        if path and path[-1].lower() in SECRET_KEYS:
            errors.append(f"secret field is forbidden: {'.'.join(path)}")
        if isinstance(value, str) and PLACEHOLDER.search(value):
            errors.append(f"placeholder is not allowed: {'.'.join(path)}")

    task = data.get("task") or {}
    task_kind = task.get("kind") if isinstance(task, dict) else None
    if task_kind not in KNOWN_TASKS:
        errors.append(f"task.kind must be one of {sorted(KNOWN_TASKS)}")
    if not isinstance(task, dict) or not task.get("goal"):
        errors.append("task.goal is required")

    mutations = data.get("allowed_mutations")
    if not isinstance(mutations, list):
        errors.append("allowed_mutations must be an array")
        mutation_set = set()
    else:
        if not all(isinstance(item, str) for item in mutations):
            errors.append("allowed_mutations entries must be strings")
            mutation_set = {item for item in mutations if isinstance(item, str)}
        else:
            mutation_set = set(mutations)
        unknown = mutation_set - KNOWN_MUTATIONS
        if unknown:
            errors.append(f"unknown allowed_mutations: {sorted(unknown)}")
        if "none" in mutation_set and len(mutation_set) > 1:
            errors.append("allowed_mutations none cannot be combined with write operations")
        if task_kind in READ_ONLY_TASKS:
            if mutation_set not in (set(), {"none"}):
                errors.append(f"task.kind={task_kind} only allows no mutations")
        elif task_kind == "diagnose":
            if mutation_set - DIAGNOSE_MUTATIONS and mutation_set != {"none"}:
                errors.append(
                    f"task.kind=diagnose mutation is invalid; {DIAGNOSE_MUTATION_POLICY}"
                )
        elif not mutation_set or mutation_set == {"none"}:
            errors.append(f"task.kind={task_kind} requires allowed mutations")
        required_mutations = TASK_MINIMUM_MUTATIONS.get(task_kind, set())
        missing_mutations = required_mutations - mutation_set
        if missing_mutations:
            errors.append(
                f"task.kind={task_kind} requires mutations: {sorted(missing_mutations)}"
            )

    platform = data.get("platform") or {}
    if not isinstance(platform, dict):
        errors.append("platform must be an object")
    else:
        if platform.get("value") not in KNOWN_PLATFORMS:
            errors.append(f"platform.value must be one of {sorted(KNOWN_PLATFORMS)}")
        if not platform.get("source") or platform.get("verified") is not True:
            errors.append("platform must include source and verified=true")

    features = data.get("features") or {}
    enabled = features.get("enabled", []) if isinstance(features, dict) else []
    excluded = features.get("excluded", []) if isinstance(features, dict) else []
    if not isinstance(enabled, list) or not isinstance(excluded, list):
        errors.append("features.enabled and features.excluded must be arrays")
    elif set(enabled) & set(excluded):
        errors.append("a feature cannot be both enabled and excluded")

    resources = data.get("resources") or {}
    if not isinstance(resources, dict):
        errors.append("resources must be an object")
        resources = {}
    ws = resources.get("ws_url")
    if task_kind in WS_TASKS and not isinstance(ws, dict):
        errors.append("resources.ws_url is required for SDK and WebAPI tasks")
    if isinstance(ws, dict):
        if ws.get("value") != WS_URL:
            errors.append("resources.ws_url must equal the canonical platform URL")
        if ws.get("source") != "avatar-platform-constant" or ws.get("verified") is not True:
            errors.append("resources.ws_url must be verified from avatar-platform-constant")

    for name in ("app_id", "scene_id"):
        resource = resources.get(name)
        required = task_kind in (APP_TASKS if name == "app_id" else SCENE_TASKS)
        if resource is None:
            if required:
                errors.append(f"resources.{name} is required for task.kind={task_kind}")
            continue
        if not isinstance(resource, dict):
            errors.append(f"resources.{name} must be an object")
            continue
        mode = resource.get("mode", "existing")
        if mode not in {"existing", "create", "not_required"}:
            errors.append(f"resources.{name}.mode must be existing/create/not_required")
        if mode == "not_required":
            continue
        if mode == "existing":
            if not resource.get("value"):
                errors.append(f"resources.{name}.value is required")
            if resource.get("source") != "platform-query" or resource.get("verified") is not True:
                errors.append(f"resources.{name} must be verified from platform-query")
        if mode == "create" and status in {"draft", "confirmed", "executing"} and resource.get("value"):
            errors.append(f"resources.{name} with mode=create cannot contain a value before verification")
    app = resources.get("app_id") or {}
    scene = resources.get("scene_id") or {}
    if app and app.get("mode", "existing") != "not_required" and app.get("app_type") is None:
        errors.append("resources.app_id.app_type is required")
    if app.get("mode") == "create":
        errors.append("resources.app_id cannot use mode=create; select a verified platform app")
    if (app.get("mode", "existing") == "existing" and
            scene.get("mode", "existing") == "existing" and
            scene.get("paired_app_id") != app.get("value")):
        errors.append("scene paired_app_id must equal app_id.value")
    scene_mode = scene.get("mode", "existing") if isinstance(scene, dict) else "existing"
    if scene and scene_mode == "existing" and scene.get("published") is not True:
        if status == "completed":
            errors.append("completed existing scene must be published")
        elif status not in {"draft", "blocked"} and task_kind in SCENE_RUNTIME_TASKS and "publish_scene" not in mutation_set:
            errors.append("unpublished scene requires allowed_mutations publish_scene")
    if scene.get("mode") == "create" and scene.get("target_app_id") != app.get("value"):
        errors.append("scene mode=create requires target_app_id equal to app_id.value")
    if (scene_mode == "create" and
            task_kind in {"sdk_build", "sdk_extend", "webapi", "resource_management"} and
            "create_interface_scene" not in mutation_set):
        errors.append("scene mode=create requires allowed_mutations create_interface_scene")
    if (scene_mode == "create" and
            (scene.get("publish") is True or status == "completed") and
            "publish_scene" not in mutation_set):
        errors.append("scene mode=create requires allowed_mutations publish_scene")
    if status == "completed" and scene_mode == "create":
        for field in ("value", "source"):
            if not scene.get(field):
                errors.append(f"completed created scene requires resources.scene_id.{field}")
        if scene.get("verified") is not True:
            errors.append("completed created scene requires resources.scene_id.verified=true")
        if scene.get("published") is not True:
            errors.append("completed created scene requires resources.scene_id.published=true")

    sdk = resources.get("sdk")
    if isinstance(sdk, dict):
        sdk_mode = sdk.get("mode", "existing")
        if sdk_mode not in {"existing", "download", "not_required"}:
            errors.append("resources.sdk.mode must be existing/download/not_required")
        if sdk_mode == "download" and "download_sdk" not in mutation_set:
            errors.append("SDK download requires allowed_mutations download_sdk")

    credential_resource = resources.get("credentials")
    if (isinstance(credential_resource, dict) and
            credential_resource.get("write_env") is True and
            "write_env" not in mutation_set):
        errors.append("credential write requires allowed_mutations write_env")

    knowledge = resources.get("knowledge_base")
    if task_kind == "knowledge_base" and not isinstance(knowledge, dict):
        errors.append("resources.knowledge_base is required for task.kind=knowledge_base")
    if isinstance(knowledge, dict):
        knowledge_mode = knowledge.get("mode", "existing")
        if knowledge_mode not in {"existing", "create", "not_required"}:
            errors.append("resources.knowledge_base.mode must be existing/create/not_required")
        if knowledge_mode == "create" and "create_knowledge_base" not in mutation_set:
            errors.append("new knowledge base requires allowed_mutations create_knowledge_base")
        if knowledge.get("upload") is True and "upload_knowledge" not in mutation_set:
            errors.append("knowledge_base upload requires allowed_mutations upload_knowledge")
        if knowledge.get("enable") is True and "enable_knowledge" not in mutation_set:
            errors.append("knowledge_base enable requires allowed_mutations enable_knowledge")
        if knowledge.get("publish") is True and "publish_scene" not in mutation_set:
            errors.append("knowledge_base publish requires allowed_mutations publish_scene")

    model = resources.get("model")
    if task_kind == "model_config" and not isinstance(model, dict):
        errors.append("resources.model is required for task.kind=model_config")
    if isinstance(model, dict):
        model_mode = model.get("mode", "existing")
        if model_mode not in {"existing", "not_required"}:
            errors.append(
                "resources.model.mode must be existing/not_required; model creation is not an implicit mutation"
            )
        if model.get("bind") is True and "bind_model" not in mutation_set:
            errors.append("model bind requires allowed_mutations bind_model")
        if model.get("publish") is True and "publish_scene" not in mutation_set:
            errors.append("model publish requires allowed_mutations publish_scene")

    if "transparent_bg" in enabled:
        decisions = data.get("decisions") or {}
        if decisions.get("protocol") != "xrtc":
            errors.append("transparent_bg requires decisions.protocol=xrtc")
    voice = {"voice_interact", "full_duplex"} & set(enabled)
    if voice:
        decisions = data.get("decisions") or {}
        permissions = data.get("permissions") or {}
        if not decisions.get("voice_interaction"):
            errors.append("voice features require decisions.voice_interaction")
        if permissions.get("microphone_confirmed") is not True:
            errors.append("voice features require permissions.microphone_confirmed=true")
    for voice_feature in ("voice_interact", "full_duplex"):
        if voice_feature not in enabled and voice_feature not in excluded:
            errors.append(f"features must explicitly exclude unused {voice_feature}")

    acceptance = data.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("acceptance must be a non-empty array")

    confirmation = data.get("confirmation") or {}
    confirmed = confirmation.get("confirmed") is True
    if status in {"confirmed", "executing", "verifying", "completed"} and not confirmed:
        errors.append(f"status={status} requires confirmation.confirmed=true")
    if status == "completed":
        evidence = data.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append("completed contract requires evidence")

    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.contract.read_text(encoding="utf-8"))
    except FileNotFoundError:
        result = {"valid": False, "errors": ["contract file does not exist"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        result = {"valid": False, "errors": [f"cannot read JSON: {exc}"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    errors = validate(data)
    result = {"valid": not errors, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
