#!/usr/bin/env python3
"""Install and verify the canonical Web SDK authentication module."""

import argparse
import base64
from datetime import datetime, timezone
from email.utils import format_datetime
import hashlib
import hmac
import json
import os
import re
import sys
import tempfile
import urllib.parse
from pathlib import Path

from platform_endpoints import CANONICAL_WS_URL


MODULE_NAME = "xfyun-auth.mjs"
MANIFEST_NAME = "websocket-auth.json"
REQUIRED_ENV = (
    "APP_ID",
    "API_KEY",
    "API_SECRET",
    "SCENE_ID",
    "AVATAR_ID",
    "VCN",
    "WS_URL",
)
MODULE_SOURCE = r'''import crypto from 'crypto';

const CANONICAL_WS_URL = '__CANONICAL_WS_URL__';

function required(env, name) {
  const value = env[name];
  if (!value) throw new Error(`missing ${name}`);
  return value;
}

function requireLength(value, name, length) {
  if (value.length !== length || value.includes('*')) {
    throw new Error(`invalid ${name}`);
  }
  return value;
}

export function avatarConfigFromEnv(env = process.env) {
  return {
    appId: required(env, 'APP_ID'),
    sceneId: required(env, 'SCENE_ID'),
    avatarId: required(env, 'AVATAR_ID'),
    vcn: required(env, 'VCN'),
    wsUrl: required(env, 'WS_URL'),
  };
}

export function generateSignedUrlFromEnv(env = process.env, now = new Date()) {
  const apiKey = requireLength(required(env, 'API_KEY'), 'API_KEY', 32);
  const apiSecret = requireLength(required(env, 'API_SECRET'), 'API_SECRET', 32);
  const wsUrl = required(env, 'WS_URL');
  if (wsUrl !== CANONICAL_WS_URL) {
    throw new Error('invalid WS_URL');
  }
  const url = new URL(wsUrl);
  const date = now.toUTCString();
  const host = url.host;
  const signatureOrigin = `host: ${host}\ndate: ${date}\nGET ${url.pathname} HTTP/1.1`;
  const signature = crypto
    .createHmac('sha256', apiSecret)
    .update(signatureOrigin)
    .digest('base64');
  const authorization = `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${signature}"`;
  url.searchParams.set('authorization', Buffer.from(authorization).toString('base64'));
  url.searchParams.set('date', date);
  url.searchParams.set('host', host);
  return url.toString();
}

export function avatarConfigHandler(req, res) {
  try {
    res.json(avatarConfigFromEnv());
  } catch (error) {
    res.status(500).json({ error: 'avatar environment is invalid' });
  }
}

export function avatarAuthHandler(req, res) {
  try {
    res.json({ signedUrl: generateSignedUrlFromEnv(), timestamp: Date.now() });
  } catch (error) {
    res.status(500).json({ error: 'avatar authentication is invalid' });
  }
}
'''.replace('__CANONICAL_WS_URL__', CANONICAL_WS_URL)


def _sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def _write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def install(project):
    project = Path(project).resolve()
    content = MODULE_SOURCE.encode("utf-8")
    module = project / MODULE_NAME
    _write_atomic(module, content)
    manifest = {
        "schema_version": 1,
        "module": MODULE_NAME,
        "sha256": _sha256_bytes(content),
        "generator": "websocket_auth.py",
    }
    _write_atomic(
        project / ".runtime" / MANIFEST_NAME,
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return manifest


def verify_installation(project):
    project = Path(project).resolve()
    module = project / MODULE_NAME
    manifest_path = project / ".runtime" / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return ["canonical_auth_manifest_missing"]
    if manifest.get("module") != MODULE_NAME or not module.is_file():
        return ["canonical_auth_module_missing"]
    digest = _sha256_bytes(module.read_bytes())
    if digest != manifest.get("sha256") or digest != _sha256_bytes(
        MODULE_SOURCE.encode("utf-8")
    ):
        return ["canonical_auth_module_modified"]
    return []


def server_usage_issues(project):
    project = Path(project).resolve()
    server = project / "server.js"
    if not server.is_file():
        return ["server_js_missing"]
    issues = verify_installation(project)
    text = server.read_text(encoding="utf-8", errors="ignore")
    if "generateSignedUrlFromEnv" not in text and "avatarAuthHandler" not in text:
        issues.append("canonical_auth_handler_not_used")
    if "avatarConfigHandler" not in text:
        issues.append("canonical_config_handler_not_used")
    if re.search(r"\.createHmac\s*\(", text):
        issues.append("inline_signature_logic_forbidden")
    return list(dict.fromkeys(issues))


def read_env(path):
    values = {}
    for raw in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def credential_issues(values):
    missing = [name for name in REQUIRED_ENV if not values.get(name)]
    issues = ["credential_missing:" + name.lower() for name in missing]
    for name in ("API_KEY", "API_SECRET"):
        value = values.get(name, "")
        if value and (len(value) != 32 or "*" in value):
            issues.append("credential_invalid:" + name.lower())
    ws_url = values.get("WS_URL")
    if ws_url and ws_url != CANONICAL_WS_URL:
        issues.append("credential_invalid:ws_url")
    return issues


def generate_signed_url(values, date):
    issues = credential_issues(values)
    if issues:
        raise ValueError(",".join(issues))
    parsed = urllib.parse.urlsplit(values["WS_URL"])
    origin = "host: {}\ndate: {}\nGET {} HTTP/1.1".format(
        parsed.netloc, date, parsed.path
    )
    signature = base64.b64encode(
        hmac.new(
            values["API_SECRET"].encode("utf-8"),
            origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    authorization = (
        'api_key="{}", algorithm="hmac-sha256", '
        'headers="host date request-line", signature="{}"'
    ).format(values["API_KEY"], signature)
    query = urllib.parse.urlencode(
        {
            "authorization": base64.b64encode(
                authorization.encode("utf-8")
            ).decode("ascii"),
            "date": date,
            "host": parsed.netloc,
        }
    )
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, query, "")
    )


def signed_url_issues(signed_url, values):
    issues = credential_issues(values)
    if issues:
        return issues
    try:
        expected_ws = urllib.parse.urlsplit(values["WS_URL"])
        actual = urllib.parse.urlsplit(signed_url)
        query = urllib.parse.parse_qs(actual.query)
        encoded = query.get("authorization", [""])[0]
        date = query.get("date", [""])[0]
        host = query.get("host", [""])[0]
        authorization = base64.b64decode(encoded, validate=True).decode("utf-8")
    except Exception:
        return ["signed_url_malformed"]
    if (
        actual.scheme != expected_ws.scheme
        or actual.netloc != expected_ws.netloc
        or actual.path != expected_ws.path
        or host != expected_ws.netloc
        or not date
    ):
        issues.append("signed_url_target_mismatch")
    match = re.fullmatch(
        r'api_key="([^"]+)", algorithm="hmac-sha256", '
        r'headers="host date request-line", signature="([^"]+)"',
        authorization,
    )
    if not match or match.group(1) != values["API_KEY"]:
        issues.append("signed_url_authorization_mismatch")
        return issues
    origin = "host: {}\ndate: {}\nGET {} HTTP/1.1".format(
        expected_ws.netloc, date, expected_ws.path
    )
    expected_signature = base64.b64encode(
        hmac.new(
            values["API_SECRET"].encode("utf-8"),
            origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    if not hmac.compare_digest(match.group(2), expected_signature):
        issues.append("signed_url_signature_mismatch")
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    install_cmd = sub.add_parser("install")
    install_cmd.add_argument("--project", required=True)
    verify_cmd = sub.add_parser("verify")
    verify_cmd.add_argument("--project", required=True)
    generate_cmd = sub.add_parser("generate")
    generate_cmd.add_argument("--env", required=True)
    generate_cmd.add_argument("--date", default=None)
    args = parser.parse_args(argv)
    cmd = args.command
    if cmd == "install":
        print(json.dumps(install(args.project), ensure_ascii=False, indent=2))
        return 0
    if cmd == "verify":
        issues = verify_installation(args.project)
        print(json.dumps({"status": "ok" if not issues else "failed", "issues": issues}))
        return 0 if not issues else 2
    if cmd == "generate":
        values = read_env(args.env)
        date = args.date or format_datetime(datetime.now(timezone.utc), usegmt=True)
        print(json.dumps({"signedUrl": generate_signed_url(values, date)}))
        return 0
    parser.error("command required")


if __name__ == "__main__":
    sys.exit(main())
