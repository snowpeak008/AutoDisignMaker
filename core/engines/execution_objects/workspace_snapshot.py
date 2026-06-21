#!/usr/bin/env python3
"""Workspace snapshot execution object manager.

Captures and tracks current draft workspace state as execution objects.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from core.engines.execution_objects.workflow import ExecutionObjectStore


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_workspace_files(workspace_root: Path) -> list[dict[str, Any]]:
    """Scan workspace directory and build file manifest.

    Args:
        workspace_root: Path to the draft workspace directory

    Returns:
        List of file metadata dictionaries
    """
    if not workspace_root.exists():
        return []

    files = []
    for path in workspace_root.rglob("*"):
        if not path.is_file():
            continue

        # Skip hidden files and system files
        if path.name.startswith("."):
            continue

        try:
            rel_path = path.relative_to(workspace_root).as_posix()
            size_bytes = path.stat().st_size
            sha256_hash = _sha256(path)

            # Infer file role
            role = "unknown"
            if "projects/" in rel_path:
                role = "design_project_export"
            elif "exports/" in rel_path:
                role = "user_export"
            elif "outputs/" in rel_path:
                role = "pipeline_output"
            elif "source_artifacts/" in rel_path:
                role = "source_artifact"

            files.append({
                "path": rel_path,
                "sha256": sha256_hash,
                "size_bytes": size_bytes,
                "role": role,
            })
        except (OSError, ValueError):
            continue

    return sorted(files, key=lambda f: f["path"])


def capture_workspace_snapshot(
    store: ExecutionObjectStore,
    workspace_root: Path,
    *,
    trigger_event: str,
    reason: str = "",
) -> dict[str, Any]:
    """Capture workspace current state as a snapshot execution object.

    Args:
        store: Execution object store
        workspace_root: Path to the draft workspace directory
        trigger_event: Event that triggered this snapshot (e.g., "user_save", "step_complete")
        reason: Human-readable reason for the snapshot

    Returns:
        Created execution object dictionary
    """
    file_manifest = _scan_workspace_files(workspace_root)
    total_size = sum(f["size_bytes"] for f in file_manifest)

    title = f"工作区快照 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    related_facts = {
        "total_files": len(file_manifest),
        "total_size_bytes": total_size,
        "snapshot_reason": reason or trigger_event,
        "trigger_event": trigger_event,
    }

    write_scope = ["workspace:snapshot", "workspace:projects", "workspace:exports"]

    # Create draft
    draft = store.create_draft(
        object_type="workspace_snapshot",
        title=title,
        source_diagnostic_id=f"workspace:snapshot:{_now_iso()}",
        prefilled_content={},
        user_content={
            "snapshot_type": "full",
            "trigger_event": trigger_event,
            "file_manifest": file_manifest,
        },
        related_facts=related_facts,
        write_scope=write_scope,
        metadata={
            "created_by": "workspace_snapshot_manager",
            "trigger_event": trigger_event,
        },
    )

    execution_object_id = draft["execution_object_id"]

    # Auto-verify workspace snapshots
    from core.engines.execution_objects.type_registry import get_confirmation_level

    confirmation_level = get_confirmation_level("workspace_snapshot")

    store.submit(
        execution_object_id,
        final_content={
            "snapshot_type": "full",
            "trigger_event": trigger_event,
            "file_manifest": file_manifest,
        },
        confirmation_level=confirmation_level,
        submission_confirmation_marker=f"workspace_snapshot:{trigger_event}",
        submitter_marker="system",
    )

    store.start_analysis(execution_object_id)
    store.complete_impact_analysis(
        execution_object_id,
        affected_scopes=write_scope,
        invalidation_scope=[],
        summary=f"工作区快照: {trigger_event}",
        diagnostics={"file_count": len(file_manifest)},
    )

    store.approve(
        execution_object_id,
        confirmation_evidence={
            "confirmation_type": "auto_approve",
            "confirmed_at": _now_iso(),
        },
    )

    store.start_execution(execution_object_id)
    store.verify_execution(
        execution_object_id,
        verification_evidence={
            "verified_at": _now_iso(),
            "verification_method": "auto_verify",
            "file_count": len(file_manifest),
        },
    )

    return store.get(execution_object_id)


def get_latest_workspace_snapshot(
    store: ExecutionObjectStore,
) -> dict[str, Any] | None:
    """Get the latest verified workspace snapshot.

    Args:
        store: Execution object store

    Returns:
        Execution object dictionary or None if no snapshots exist
    """
    objects = store.list_objects(states={"verified"})
    snapshots = [
        obj for obj in objects
        if obj.get("object_type") == "workspace_snapshot"
    ]

    if not snapshots:
        return None

    snapshots.sort(key=lambda obj: obj.get("updated_at", ""), reverse=True)
    return snapshots[0]


def list_workspace_snapshots(
    store: ExecutionObjectStore,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List all workspace snapshots.

    Args:
        store: Execution object store
        limit: Optional maximum number of snapshots to return

    Returns:
        List of execution objects sorted by updated_at (newest first)
    """
    objects = store.list_objects(states={"verified"})
    snapshots = [
        obj for obj in objects
        if obj.get("object_type") == "workspace_snapshot"
    ]

    snapshots.sort(key=lambda obj: obj.get("updated_at", ""), reverse=True)

    if limit is not None:
        snapshots = snapshots[:limit]

    return snapshots


def compare_workspace_snapshots(
    snapshot_a: dict[str, Any],
    snapshot_b: dict[str, Any],
) -> dict[str, Any]:
    """Compare two workspace snapshots and return differences.

    Args:
        snapshot_a: First snapshot execution object
        snapshot_b: Second snapshot execution object

    Returns:
        Dictionary with added, removed, modified files
    """
    manifest_a = snapshot_a.get("user_content", {}).get("file_manifest", [])
    manifest_b = snapshot_b.get("user_content", {}).get("file_manifest", [])

    files_a = {f["path"]: f for f in manifest_a}
    files_b = {f["path"]: f for f in manifest_b}

    added = [files_b[path] for path in sorted(set(files_b) - set(files_a))]
    removed = [files_a[path] for path in sorted(set(files_a) - set(files_b))]

    modified = []
    for path in sorted(set(files_a) & set(files_b)):
        if files_a[path]["sha256"] != files_b[path]["sha256"]:
            modified.append({
                "path": path,
                "before": files_a[path],
                "after": files_b[path],
            })

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "summary": {
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modified),
        },
    }


def get_workspace_file_history(
    store: ExecutionObjectStore,
    file_path: str,
) -> list[dict[str, Any]]:
    """Get history of a specific file across all snapshots.

    Args:
        store: Execution object store
        file_path: Relative path to the file in workspace

    Returns:
        List of snapshot entries containing this file, newest first
    """
    snapshots = list_workspace_snapshots(store)
    history = []

    for snapshot in snapshots:
        manifest = snapshot.get("user_content", {}).get("file_manifest", [])
        for file_entry in manifest:
            if file_entry["path"] == file_path:
                history.append({
                    "snapshot_id": snapshot["execution_object_id"],
                    "snapshot_time": snapshot["updated_at"],
                    "file_entry": file_entry,
                })
                break

    return history


__all__ = [
    "capture_workspace_snapshot",
    "get_latest_workspace_snapshot",
    "list_workspace_snapshots",
    "compare_workspace_snapshots",
    "get_workspace_file_history",
]
