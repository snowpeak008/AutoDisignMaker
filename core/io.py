"""File I/O utilities for AutoDesignMaker.

Migrated from steps/common.py (file tool section).
All path resolution is relative to PROJECT_ROOT from core.paths.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT


def now_iso() -> str:
    """Return current time as ISO 8601 string (seconds precision)."""
    return datetime.now().isoformat(timespec="seconds")


def timestamp() -> str:
    """Return current time as compact timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def rel(path: Path, root: Path = PROJECT_ROOT) -> str:
    """Return path relative to root as POSIX string. Falls back to absolute."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def write_json(path: Path, data: Any) -> Path:
    """Write data as indented JSON to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON from path. Returns default on missing file or parse error."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_text(path: Path, text: str) -> Path:
    """Write text to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def file_manifest(root: Path) -> list[dict[str, Any]]:
    """Return a list of {path, size_bytes, sha256} for all files under root."""
    files: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel_path = path.relative_to(root).as_posix()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        files.append({
            "path": rel_path,
            "size_bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    return files


__all__ = [
    "now_iso",
    "timestamp",
    "rel",
    "write_json",
    "read_json",
    "write_text",
    "file_manifest",
]
