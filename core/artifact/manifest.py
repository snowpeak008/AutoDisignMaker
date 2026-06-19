"""Artifact manifest helpers for versioned pipeline outputs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


_VERSIONED_DIR_RE = re.compile(
    r"^(?P<project>.+)_(?P<stage>[^_]+)_(?P<date>\d{8})_v(?P<version>\d+)$"
)


def parse_versioned_dir(path: Path) -> dict[str, Any]:
    match = _VERSIONED_DIR_RE.match(path.name)
    if not match:
        return {"project": "", "stage": "", "date": "", "version": 0, "name": path.name, "path": str(path)}
    data = match.groupdict()
    data["version"] = int(data["version"])
    data["name"] = path.name
    data["path"] = str(path)
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_entry(base_dir: Path, relative_path: str, *, role: str, status: str = "generated") -> dict[str, Any]:
    path = base_dir / relative_path
    entry: dict[str, Any] = {
        "path": relative_path.replace("\\", "/"), "role": role, "status": status, "exists": path.exists()
    }
    if path.exists() and path.is_file():
        entry["bytes"] = path.stat().st_size
        entry["sha256"] = sha256_file(path)
    return entry


def path_ref(path: Path | None, *, root: Path | None = None) -> str:
    if path is None:
        return ""
    try:
        if root is not None:
            return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        pass
    return str(path).replace("\\", "/")


def write_artifact_manifest(
    output_dir: Path, *, stage: str, mode: str, files: list[dict],
    upstream: dict | None = None, patch: dict | None = None, extra: dict | None = None,
) -> Path:
    meta = parse_versioned_dir(output_dir)
    manifest: dict[str, Any] = {
        "project": meta.get("project") or "", "stage": stage, "version": meta.get("version") or 0,
        "artifact_dir": meta.get("name") or output_dir.name, "mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"), "files": files,
    }
    if upstream:
        manifest["upstream"] = upstream
    if patch:
        manifest["patch"] = patch
    if extra:
        manifest.update(extra)
    manifest_path = output_dir / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path
