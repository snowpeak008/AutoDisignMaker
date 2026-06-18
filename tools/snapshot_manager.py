"""Snapshot utilities for current project source artifacts."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path

from tools.pipeline_registry import get_step_name
from tools.pipeline_state import update_step_state
from tools.structured_md import read_structured_or_text, write_data


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = BASE_DIR / "source_artifacts"
SNAPSHOT_DIR = SOURCE_DIR / ".snapshots"


def _compute_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_snapshot_path(path: Path, snapshot_dir: Path) -> bool:
    path = Path(path)
    return path == snapshot_dir or snapshot_dir in path.parents


def _iter_source_files(source_dir: Path):
    snapshot_dir = source_dir / ".snapshots"
    if not source_dir.exists():
        return
    for root, dirs, filenames in os.walk(source_dir):
        root_path = Path(root)
        if _is_snapshot_path(root_path, snapshot_dir):
            dirs[:] = []
            continue
        dirs[:] = [name for name in dirs if not _is_snapshot_path(root_path / name, snapshot_dir)]
        for filename in filenames:
            yield root_path / filename


def _compute_source_manifest(source_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(_iter_source_files(source_dir)):
        digest.update(str(path.relative_to(source_dir)).replace("\\", "/").encode())
        try:
            digest.update(_compute_file_hash(path).encode())
        except OSError:
            digest.update(b"unreadable")
    return digest.hexdigest()


def _capture_source_files(source_dir: Path, backup_root: Path, project_root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    backup_root.mkdir(parents=True, exist_ok=True)
    for path in _iter_source_files(source_dir):
        rel_path = path.relative_to(source_dir)
        record: dict[str, object] = {"path": str(rel_path).replace("\\", "/")}
        try:
            record["hash"] = _compute_file_hash(path)
            record["size_bytes"] = path.stat().st_size
            backup_path = backup_root / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
            record["backup_path"] = str(backup_path.relative_to(project_root)).replace("\\", "/")
        except OSError as exc:
            record["hash"] = "unreadable"
            record["size_bytes"] = 0
            record["error"] = str(exc)
        records.append(record)
    return sorted(records, key=lambda item: str(item["path"]))


def _snapshot_dir(project_root: Path) -> Path:
    return project_root / "source_artifacts" / ".snapshots"


def _load_snapshot_data(path: Path) -> dict:
    if not path.exists():
        return {}
    return read_structured_or_text(path)


def _save_snapshot_data(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_data(path, data, title="Snapshot")


def create_snapshot(step_number: int, step_name: str | None = None, project_root: Path | None = None) -> Path:
    project_root = Path(project_root or BASE_DIR)
    step_name = step_name or get_step_name(step_number)
    source_dir = project_root / "source_artifacts"
    snapshot_dir = _snapshot_dir(project_root)
    source_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    current_manifest = _compute_source_manifest(source_dir)
    previous = sorted(snapshot_dir.glob(f"step_{step_number}_*.md"), key=os.path.getmtime, reverse=True)
    if previous:
        previous_data = _load_snapshot_data(previous[0])
        if previous_data.get("manifest") == current_manifest:
            previous_data["status"] = "in_progress"
            previous_data["reused_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")
            _save_snapshot_data(previous[0], previous_data)
            snapshot_id = previous_data.get("snapshot_id", previous[0].stem)
            update_step_state(
                project_root,
                step_number,
                "in_progress",
                snapshot_id=snapshot_id,
                output_path=str(previous[0].relative_to(project_root)).replace("\\", "/"),
            )
            print(f"快照已复用：步骤{step_number} - {step_name}（源资料内容未变化）")
            return previous[0]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"step_{step_number}_{stamp}"
    snapshot_path = snapshot_dir / f"{snapshot_id}.md"
    backup_root = snapshot_dir / snapshot_id / "files"
    snapshot = {
        "snapshot_id": snapshot_id,
        "step": step_number,
        "step_name": step_name,
        "timestamp": stamp,
        "status": "in_progress",
        "manifest": current_manifest,
        "files": _capture_source_files(source_dir, backup_root, project_root),
    }
    _save_snapshot_data(snapshot_path, snapshot)
    update_step_state(
        project_root,
        step_number,
        "in_progress",
        snapshot_id=snapshot_id,
        output_path=str(snapshot_path.relative_to(project_root)).replace("\\", "/"),
    )
    print(f"快照已创建：步骤{step_number} - {step_name}")
    return snapshot_path


def update_snapshot_status(step_number: int, status: str, project_root: Path | None = None, message: str | None = None) -> Path | None:
    project_root = Path(project_root or BASE_DIR)
    snapshot_dir = _snapshot_dir(project_root)
    if not snapshot_dir.exists():
        update_step_state(project_root, step_number, status, message=message or "未找到快照目录")
        return None
    candidates = sorted(snapshot_dir.glob(f"step_{step_number}_*.md"), reverse=True)
    if not candidates:
        update_step_state(project_root, step_number, status, message=message or "未找到步骤快照")
        return None
    latest = candidates[0]
    data = _load_snapshot_data(latest)
    snapshot_id = data.get("snapshot_id", latest.stem)
    data["status"] = status
    data["updated_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")
    if status == "success":
        source_dir = project_root / "source_artifacts"
        backup_root = snapshot_dir / snapshot_id / "files"
        data["files"] = _capture_source_files(source_dir, backup_root, project_root)
        for old_snapshot in candidates[1:]:
            old_files = snapshot_dir / old_snapshot.stem
            try:
                old_snapshot.unlink()
                if old_files.exists():
                    shutil.rmtree(old_files)
            except OSError:
                pass
    _save_snapshot_data(latest, data)
    update_step_state(
        project_root,
        step_number,
        status,
        snapshot_id=snapshot_id,
        output_path=str(latest.relative_to(project_root)).replace("\\", "/"),
        message=message,
    )
    print(f"快照状态已更新：步骤{step_number} -> {status}")
    return latest


def list_snapshots(project_root: Path | None = None) -> list[dict]:
    project_root = Path(project_root or BASE_DIR)
    snapshot_dir = _snapshot_dir(project_root)
    if not snapshot_dir.exists():
        return []
    snapshots = []
    for path in sorted(snapshot_dir.glob("step_*.md")):
        data = _load_snapshot_data(path)
        data["snapshot_file"] = str(path.relative_to(project_root)).replace("\\", "/")
        snapshots.append(data)
    return snapshots
