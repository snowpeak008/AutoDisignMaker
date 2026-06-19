"""Snapshot utilities for source artifacts."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

from core.io import read_json, write_json
from core.paths import SOURCE_ARTIFACTS_DIR
from core.registry import get_step_name

SNAPSHOT_DIR = SOURCE_ARTIFACTS_DIR / ".snapshots"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def take_snapshot(step_number: int, *, event: str = "manual") -> Path:
    """Take a snapshot of current source artifacts before a step runs."""
    step_name = get_step_name(step_number)
    snapshot_name = f"{_stamp()}_{event}_step{step_number:02d}_{step_name}"
    snapshot_path = SNAPSHOT_DIR / snapshot_name
    snapshot_path.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    for item in sorted(SOURCE_ARTIFACTS_DIR.rglob("*")):
        if item.is_file() and ".snapshots" not in item.parts:
            rel_path = item.relative_to(SOURCE_ARTIFACTS_DIR).as_posix()
            manifest.append({
                "path": rel_path,
                "size_bytes": item.stat().st_size,
                "sha256": _file_hash(item),
            })

    write_json(snapshot_path / "manifest.json", {
        "step": step_number,
        "step_name": step_name,
        "event": event,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "file_count": len(manifest),
        "files": manifest,
    })
    return snapshot_path


def list_snapshots() -> list[Path]:
    if not SNAPSHOT_DIR.exists():
        return []
    return sorted(SNAPSHOT_DIR.iterdir(), reverse=True)


def restore_snapshot(snapshot_path: Path, *, dry_run: bool = True) -> list[str]:
    """Restore source artifacts from a snapshot (dry_run=True by default)."""
    manifest_path = snapshot_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest in snapshot: {snapshot_path}")
    manifest = read_json(manifest_path, {})
    actions: list[str] = []
    for entry in manifest.get("files", []):
        src = snapshot_path / entry["path"]
        dst = SOURCE_ARTIFACTS_DIR / entry["path"]
        if src.exists():
            actions.append(f"restore: {entry['path']}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        else:
            actions.append(f"missing in snapshot: {entry['path']}")
    return actions
