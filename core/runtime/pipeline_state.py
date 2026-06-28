"""Pipeline state read/write for the current draft source_artifacts directory."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import SOURCE_ARTIFACTS_DIR
from core.registry import get_step_name
from core.utils.structured_md import read_structured_or_text, write_data

STATE_FILENAME = "pipeline_state.md"
VALID_STATUSES = {
    "pending",
    "in_progress",
    "success",
    "failed",
    "skipped",
    "blocked",
    "stopped",
    "waiting_confirmation",
    "completed_with_review",
}


def _state_path(project_root: Path) -> Path:
    return SOURCE_ARTIFACTS_DIR / STATE_FILENAME


def load_pipeline_state(project_root: Path) -> dict[str, Any]:
    path = _state_path(project_root)
    if not path.exists():
        return {"steps": {}}
    data = read_structured_or_text(path)
    if isinstance(data, dict):
        data.setdefault("steps", {})
        return data
    return {"steps": {}}


def save_pipeline_state(project_root: Path, state: dict[str, Any]) -> Path:
    path = _state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_data(path, state, title="Pipeline State")
    return path


def update_step_state(
    project_root: Path,
    step_number: int,
    status: str,
    *,
    snapshot_id: str | None = None,
    output_path: str | None = None,
    message: str | None = None,
) -> Path:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid pipeline status: {status}")
    state = load_pipeline_state(project_root)
    key = str(step_number)
    step_state = state["steps"].get(key, {})
    step_state.update({
        "step": step_number,
        "step_name": get_step_name(step_number),
        "status": status,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    })
    if snapshot_id is not None:
        step_state["snapshot_id"] = snapshot_id
    if output_path is not None:
        step_state["output_path"] = output_path
    if message is not None:
        step_state["message"] = message
    state["steps"][key] = step_state
    return save_pipeline_state(project_root, state)


def get_step_state(project_root: Path, step_number: int) -> dict[str, Any] | None:
    return load_pipeline_state(project_root).get("steps", {}).get(str(step_number))
