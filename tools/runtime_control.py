#!/usr/bin/env python3
"""Persistent runtime control files for graceful pipeline stops."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


STOP_REQUEST_NAME = "stop_request.json"
RUN_STATE_NAME = "run_state.json"


class PipelineStopRequested(RuntimeError):
    """Raised when the operator requested a graceful stop at a safe boundary."""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"


def control_dir(project_root: Path) -> Path:
    return Path(project_root) / "outputs" / "runtime_control"


def stop_request_path(project_root: Path) -> Path:
    return control_dir(project_root) / STOP_REQUEST_NAME


def run_state_path(project_root: Path) -> Path:
    return control_dir(project_root) / RUN_STATE_NAME


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path


def current_run_id(project_root: Path) -> str:
    state = read_json(run_state_path(project_root), {})
    if not isinstance(state, dict):
        return ""
    return str(state.get("run_id") or "")


def request_stop(
    project_root: Path,
    *,
    mode: str = "graceful",
    boundary: str = "after_current_unit",
    reason: str = "operator_stop",
    scope: str = "current_run",
    run_id: str | None = None,
) -> dict[str, Any]:
    resolved_run_id = run_id if run_id is not None else current_run_id(project_root)
    payload = {
        "schema_version": 1,
        "status": "requested",
        "mode": mode,
        "boundary": boundary,
        "reason": reason,
        "scope": scope,
        "run_id": resolved_run_id,
        "requested_at": now_iso(),
    }
    write_json(stop_request_path(project_root), payload)
    return payload


def clear_stop_request(project_root: Path) -> None:
    path = stop_request_path(project_root)
    if path.exists():
        path.unlink()


def clear_stale_stop_request(project_root: Path, run_id: str) -> None:
    request = read_stop_request(project_root)
    if request.get("status") == "requested" and str(request.get("run_id") or "") == run_id:
        return
    clear_stop_request(project_root)


def read_stop_request(project_root: Path) -> dict[str, Any]:
    data = read_json(stop_request_path(project_root), {})
    return data if isinstance(data, dict) else {}


def stop_requested(project_root: Path) -> bool:
    request = read_stop_request(project_root)
    return request.get("status") == "requested"


def write_run_state(project_root: Path, **updates: Any) -> dict[str, Any]:
    current = read_json(run_state_path(project_root), {})
    if not isinstance(current, dict):
        current = {}
    current.update({
        "schema_version": 1,
        "updated_at": now_iso(),
        **updates,
    })
    write_json(run_state_path(project_root), current)
    return current


def mark_stopped(project_root: Path, **updates: Any) -> dict[str, Any]:
    request = read_stop_request(project_root)
    stopped = {
        "status": "stopped",
        "stopped_at": now_iso(),
        "stop_request": request,
        **updates,
    }
    write_run_state(project_root, **stopped)
    if request:
        request["status"] = "handled"
        request["handled_at"] = now_iso()
        write_json(stop_request_path(project_root), request)
    return stopped
