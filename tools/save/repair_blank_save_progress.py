#!/usr/bin/env python3
"""Repair a save that should be blank but inherited pipeline outputs."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT_FOR_SCRIPT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT_FOR_SCRIPT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_SCRIPT))

from core.paths import PROJECT_ROOT  # noqa: E402
from core.save import manager as save_manager  # noqa: E402


CLEAN_RELATIVE_PATHS = (
    Path("outputs") / "artifacts",
    Path("outputs") / "checkpoints",
    Path("outputs") / "run_logs",
    Path("outputs") / "runtime_control",
    Path("outputs") / "artifact_layer",
    Path("outputs") / "execution_objects" / "execution_objects.json",
    Path("workspace"),
)


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _existing_cleanup_paths(workspace_root: Path) -> list[Path]:
    paths = [workspace_root / rel for rel in CLEAN_RELATIVE_PATHS]
    source_root = workspace_root / "source_artifacts"
    if source_root.is_dir():
        paths.extend(sorted(source_root.glob("devflow_*")))
    return [path for path in paths if path.exists()]


def repair_blank_save_progress(project_root: Path, save_id: str, *, apply: bool = False) -> dict[str, Any]:
    root = save_manager._formal_root(project_root)
    save_path = save_manager.save_dir(root, save_id)
    workspace_root = save_manager.workspace_dir(root, save_id)
    manifest_path = save_manager.save_manifest_path(root, save_id)
    if not manifest_path.is_file():
        raise RuntimeError(f"Unknown save id: {save_id}")
    if not workspace_root.is_dir():
        raise RuntimeError(f"Save workspace is missing: {save_id}")

    manifest = save_manager.read_json(manifest_path, {})
    old_progress = manifest.get("progress", {})
    cleanup_paths = _existing_cleanup_paths(workspace_root)
    new_progress = save_manager._blank_progress()

    result = {
        "save_id": save_id,
        "apply": apply,
        "old_progress": old_progress,
        "new_progress": new_progress,
        "cleanup_paths": [save_manager._rel(path, root) for path in cleanup_paths],
    }
    if not apply:
        return result

    for path in cleanup_paths:
        save_manager._safe_resolve_under(workspace_root, path)
        _remove_path(path)
    for dirname in save_manager.EMPTY_DIRS:
        (workspace_root / dirname).mkdir(parents=True, exist_ok=True)

    new_progress = save_manager._progress_from_workspace_root(workspace_root)
    manifest.update({
        "last_worked_at": save_manager.now_iso(),
        "progress": new_progress,
    })
    save_manager.write_json(manifest_path, manifest)
    save_manager._replace_entry(root, manifest)
    log_record = {
        "event": "repair_blank_save_progress",
        "timestamp": save_manager.now_iso(),
        "save_id": save_id,
        "old_progress": old_progress,
        "new_progress": new_progress,
        "removed_paths": [save_manager._rel(path, root) for path in cleanup_paths],
    }
    save_manager.append_jsonl(save_path / "repair_log.jsonl", log_record)
    result["new_progress"] = new_progress
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save-id", required=True)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    result = repair_blank_save_progress(
        Path(args.project_root),
        args.save_id,
        apply=bool(args.apply),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
