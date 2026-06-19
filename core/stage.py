"""Stage directory and gate-log helpers.

Migrated from steps/common.py (stage tool segment) + tools/pipeline_step_common.py.
Change: append_gate_log writes to logs/pipeline/gate_log.yaml instead of root gate_log.yaml.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import ARTIFACTS_DIR, LOGS_DIR
from core.io import read_json, rel, write_json


GATE_LOG_PATH = LOGS_DIR / "pipeline" / "gate_log.yaml"


def stage_dir(step_number: int) -> Path:
    return ARTIFACTS_DIR / f"stage_{step_number:02d}"


def _safe_reset_dir(path: Path, root: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = path.resolve()
    if target_resolved == root_resolved or root_resolved not in target_resolved.parents:
        raise RuntimeError(f"Refusing to reset path outside artifact root: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def reset_stage(step_number: int) -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = stage_dir(step_number)
    _safe_reset_dir(path, ARTIFACTS_DIR)
    return path


def classify_stage_file(path_text: str) -> str:
    normalized = path_text.replace("\\", "/")
    name = Path(normalized).name
    if normalized.startswith("guidance/"):
        return "guidance"
    if normalized.startswith("imported/"):
        return "source_import"
    if normalized.startswith("upstream/"):
        return "upstream_reference"
    if name in {"artifact_index.json", "reference_manifest.json"}:
        return "stage_index"
    if name in {"validation_report.json", "artifact_reviews.json", "artifact_validation_layer.json"}:
        return "validation"
    if name == "artifact_layer_manifest.json":
        return "artifact_layer"
    if name == "README.md" or name.startswith("MISSING_") or name.startswith("OPTIONAL_"):
        return "operator_report"
    if name.startswith("migration_audit"):
        return "audit"
    return "stage_file"


def append_gate_log(
    step_number: int,
    status: str,
    *,
    imported: bool = False,
    message: str = "",
) -> None:
    GATE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    entry = (
        f"- step: {step_number:02d}\n"
        f"  status: {status}\n"
        f"  imported: {str(imported).lower()}\n"
        f"  timestamp: {timestamp}\n"
    )
    if message:
        safe_msg = message.replace("\n", " ")
        entry += f"  message: {safe_msg!r}\n"
    with GATE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def refresh_reference_manifest_file_inventory(stage_path: Path) -> dict[str, Any]:
    """Re-scan stage_path files and update reference_manifest.json file list."""
    from core.io import file_manifest
    ref_path = stage_path / "reference_manifest.json"
    data = read_json(ref_path, {})
    if not isinstance(data, dict):
        data = {}
    data["files"] = [
        {
            "path": item["path"],
            "stage_path": rel(stage_path / item["path"]),
            "role": classify_stage_file(item["path"]),
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in file_manifest(stage_path)
        if item["path"] != "reference_manifest.json"
    ]
    write_json(ref_path, data)
    return data


__all__ = [
    "GATE_LOG_PATH",
    "stage_dir",
    "reset_stage",
    "classify_stage_file",
    "append_gate_log",
    "refresh_reference_manifest_file_inventory",
]
