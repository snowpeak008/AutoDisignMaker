"""差量更新包生成器 — migrated from tools/delta_patch_generator.py."""

from __future__ import annotations

import hashlib
import os
import zipfile
from datetime import datetime
from pathlib import Path

from core.paths import SANDBOX_DIR
from core.utils.structured_md import read_structured_or_text, write_data

BUILD_ROOT = SANDBOX_DIR / "outputs" / "builds"
RELEASE_DIR = SANDBOX_DIR / "outputs" / "release_history"


def _compute_file_hash(filepath) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def scan_files(directory) -> dict[str, str]:
    result: dict[str, str] = {}
    if not os.path.exists(directory):
        return result
    for root, _, files in os.walk(directory):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, directory).replace("\\", "/")
            result[rel_path] = _compute_file_hash(full_path)
    return result


def compute_delta(old_files: dict, new_files: dict) -> dict:
    added = {f: h for f, h in new_files.items() if f not in old_files}
    removed = {f: h for f, h in old_files.items() if f not in new_files}
    modified = {f: new_files[f] for f in new_files if f in old_files and old_files[f] != new_files[f]}
    return {"added": added, "removed": removed, "modified": modified}


def create_patch_package(new_build_dir: str | Path, delta: dict, output_dir: str | Path) -> Path:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    patch_filename = os.path.join(str(output_dir), f"patch_{timestamp}.zip")
    changed_files = list(delta["added"].keys()) + list(delta["modified"].keys())
    with zipfile.ZipFile(patch_filename, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in changed_files:
            full_path = os.path.join(str(new_build_dir), rel_path)
            if os.path.exists(full_path):
                zf.write(full_path, rel_path)
    return Path(patch_filename)


def generate_delta_patch(old_build_dir: str | Path, new_build_dir: str | Path) -> dict:
    old_files = scan_files(str(old_build_dir))
    new_files = scan_files(str(new_build_dir))
    delta = compute_delta(old_files, new_files)
    patch_path = create_patch_package(new_build_dir, delta, RELEASE_DIR)
    manifest = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "patch_file": str(patch_path),
        "added": len(delta["added"]),
        "removed": len(delta["removed"]),
        "modified": len(delta["modified"]),
        "total_changes": len(delta["added"]) + len(delta["removed"]) + len(delta["modified"]),
    }
    manifest_path = patch_path.with_suffix(".json")
    write_data(manifest_path, manifest, title="Delta Patch Manifest")
    return manifest
