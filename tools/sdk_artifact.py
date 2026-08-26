#!/usr/bin/env python3
"""Deterministically acquire and verify avatar SDK artifacts."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


SDK_CONFIG = {
    "web": {
        "version": "3.2.3.1002",
        "url": (
            "https://sdksave-1317537578.cos.ap-guangzhou.myqcloud.com/"
            "avatar-web-sdk.zip"
        ),
    }
}


class ArtifactError(RuntimeError):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _relative(path, root):
    return path.resolve().relative_to(root.resolve()).as_posix()


def find_web_entry(root):
    root = Path(root)
    candidates = sorted(root.glob("**/esm/index.js"))
    for entry in candidates:
        if entry.is_file() and entry.stat().st_size > 0:
            declaration = entry.with_suffix(".d.ts")
            if declaration.is_file() and declaration.stat().st_size > 0:
                return entry
    return None


def extract_zip_safely(archive, destination):
    archive = Path(archive).resolve()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    root_text = str(destination)
    with zipfile.ZipFile(str(archive)) as zipped:
        for member in zipped.infolist():
            target = (destination / member.filename).resolve()
            try:
                inside = os.path.commonpath((root_text, str(target))) == root_text
            except ValueError:
                inside = False
            if not inside:
                raise ArtifactError("unsafe_archive_path")
        zipped.extractall(str(destination))


def _manifest(project, status, entry=None, source=None, reason=None):
    from datetime import datetime, timezone

    data = {
        "schema_version": 1,
        "platform": "web",
        "version": SDK_CONFIG["web"]["version"],
        "status": status,
        "artifact_status": "ready" if entry else "blocked_missing_sdk",
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if entry:
        data.update(
            {
                "entry": _relative(entry, project),
                "types": _relative(entry.with_suffix(".d.ts"), project),
                "sha256": _sha256(entry),
            }
        )
    if source:
        data["source"] = source
    if reason:
        data["reason"] = reason
    _write_json_atomic(project / ".runtime" / "sdk-artifact.json", data)
    return data


def _download(url, destination, opener=None):
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": "avatar-platform/1"})
    with opener(request, timeout=60) as response:
        with destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ArtifactError("empty_download")
    if not zipfile.is_zipfile(str(destination)):
        raise ArtifactError("invalid_zip")


def ensure_artifact(platform, project, target_dir=None, url=None, opener=None):
    if platform != "web":
        raise ArtifactError("unsupported_platform")
    project = Path(project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    target = Path(target_dir).resolve() if target_dir else project / "sdk"

    entry = find_web_entry(target)
    if entry:
        return _manifest(project, "already_exists", entry=entry, source="existing")

    config = SDK_CONFIG[platform]
    source_url = url or config["url"]
    try:
        with tempfile.TemporaryDirectory(prefix="avatar-sdk-") as temp_dir:
            temp_root = Path(temp_dir)
            archive = temp_root / "sdk.zip"
            extracted = temp_root / "extracted"
            _download(source_url, archive, opener=opener)
            extract_zip_safely(archive, extracted)
            staged_entry = find_web_entry(extracted)
            if not staged_entry:
                raise ArtifactError("sdk_entry_or_types_missing")

            if target.exists():
                install_root = target / ("avatar-sdk-web_" + config["version"])
                if install_root.exists():
                    raise ArtifactError("target_collision")
                shutil.copytree(str(extracted), str(install_root))
            else:
                shutil.copytree(str(extracted), str(target))

        entry = find_web_entry(target)
        if not entry:
            raise ArtifactError("post_install_validation_failed")
        return _manifest(project, "success", entry=entry, source="oss")
    except Exception as exc:
        reason = str(exc) if isinstance(exc, ArtifactError) else exc.__class__.__name__
        return _manifest(
            project, "blocked_missing_sdk", source="oss", reason=reason
        )


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    ensure = sub.add_parser("ensure")
    ensure.add_argument("--platform", choices=sorted(SDK_CONFIG), required=True)
    ensure.add_argument("--project", required=True)
    ensure.add_argument("--target-dir")
    args = parser.parse_args(argv)
    if args.command != "ensure":
        parser.error("command required")
    result = ensure_artifact(args.platform, args.project, args.target_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["artifact_status"] == "ready" else 2


if __name__ == "__main__":
    sys.exit(main())
