#!/usr/bin/env python3
"""User artifact execution object manager.

Manages user exports from the design workbench as execution objects.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.engines.execution_objects.workflow import ExecutionObjectStore


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def save_user_artifact(
    store: ExecutionObjectStore,
    *,
    export_format: str,
    export_scope: str,
    content: dict[str, Any],
    title: str | None = None,
    source_project_id: str = "",
    target_directory: str = "workspace/exports/",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save a user export artifact to execution object store.

    Args:
        store: Execution object store
        export_format: Format of the export (e.g., "devflow_concept", "json", "markdown")
        export_scope: Scope of export (e.g., "full", "current_domain", "selected_nodes")
        content: Exported content as dictionary
        title: Optional custom title
        source_project_id: ID of the source design project execution object
        target_directory: Directory where file would be saved
        metadata: Additional metadata

    Returns:
        Created execution object dictionary
    """
    object_title = title or f"{export_format} 导出 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    related_facts = {
        "export_timestamp": _now_iso(),
        "source_project_id": source_project_id,
        "target_directory": target_directory,
        "export_format": export_format,
        "export_scope": export_scope,
    }

    write_scope = [
        "workspace:exports",
        f"workspace:exports:{export_format}",
    ]

    user_content = {
        "export_format": export_format,
        "export_scope": export_scope,
        "include_gameplay_global_view": metadata.get("include_gameplay_global_view", False) if metadata else False,
        "content": content,
    }

    # Create draft
    draft = store.create_draft(
        object_type="user_artifact",
        title=object_title,
        source_diagnostic_id=f"workbench:export:{export_format}",
        prefilled_content={},
        user_content=user_content,
        related_facts=related_facts,
        write_scope=write_scope,
        metadata={
            "created_by": "design_workbench",
            "export_format": export_format,
            "source_project_id": source_project_id,
            **(metadata or {}),
        },
    )

    execution_object_id = draft["execution_object_id"]

    # Auto-verify user artifacts
    from core.engines.execution_objects.type_registry import get_confirmation_level

    confirmation_level = get_confirmation_level("user_artifact")

    store.submit(
        execution_object_id,
        final_content=user_content,
        confirmation_level=confirmation_level,
        submission_confirmation_marker=f"export:{export_format}",
        submitter_marker="workbench_user",
    )

    store.start_analysis(execution_object_id)
    store.complete_impact_analysis(
        execution_object_id,
        affected_scopes=write_scope,
        invalidation_scope=[],
        summary=f"用户导出: {export_format}",
        diagnostics={"export_scope": export_scope},
    )

    store.approve(
        execution_object_id,
        confirmation_evidence={
            "confirmation_type": "user_export_action",
            "confirmed_by": "workbench_user",
            "confirmed_at": _now_iso(),
        },
    )

    store.start_execution(execution_object_id)
    store.verify_execution(
        execution_object_id,
        verification_evidence={
            "verified_at": _now_iso(),
            "verification_method": "auto_verify",
            "export_format": export_format,
        },
    )

    return store.get(execution_object_id)


def list_user_artifacts(
    store: ExecutionObjectStore,
    *,
    export_format: str | None = None,
    source_project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all user artifacts.

    Args:
        store: Execution object store
        export_format: Optional filter by export format
        source_project_id: Optional filter by source project

    Returns:
        List of execution objects sorted by updated_at (newest first)
    """
    objects = store.list_objects(states={"verified"})
    artifacts = [
        obj for obj in objects
        if obj.get("object_type") == "user_artifact"
    ]

    # Apply filters
    if export_format:
        artifacts = [
            obj for obj in artifacts
            if obj.get("user_content", {}).get("export_format") == export_format
        ]

    if source_project_id:
        artifacts = [
            obj for obj in artifacts
            if obj.get("related_facts", {}).get("source_project_id") == source_project_id
        ]

    artifacts.sort(key=lambda obj: obj.get("updated_at", ""), reverse=True)
    return artifacts


def get_user_artifact(
    store: ExecutionObjectStore,
    execution_object_id: str,
) -> dict[str, Any]:
    """Get a specific user artifact's content.

    Args:
        store: Execution object store
        execution_object_id: ID of the user artifact execution object

    Returns:
        Artifact content dictionary

    Raises:
        ValueError: If execution_object_id is not a user_artifact
    """
    obj = store.get(execution_object_id)

    if obj.get("object_type") != "user_artifact":
        raise ValueError(
            f"Execution object {execution_object_id} is not a user_artifact"
        )

    return obj.get("user_content", {})


def delete_user_artifact(
    store: ExecutionObjectStore,
    execution_object_id: str,
) -> dict[str, Any]:
    """Mark a user artifact as cancelled (soft delete).

    Args:
        store: Execution object store
        execution_object_id: ID of the user artifact execution object

    Returns:
        Updated execution object dictionary

    Raises:
        ValueError: If execution_object_id is not a user_artifact
    """
    obj = store.get(execution_object_id)

    if obj.get("object_type") != "user_artifact":
        raise ValueError(
            f"Execution object {execution_object_id} is not a user_artifact"
        )

    return store.cancel(
        execution_object_id,
        reason="用户删除导出制品",
        cancellation_evidence={
            "cancelled_by": "workbench_user",
            "cancelled_at": _now_iso(),
        },
    )


__all__ = [
    "save_user_artifact",
    "list_user_artifacts",
    "get_user_artifact",
    "delete_user_artifact",
]
