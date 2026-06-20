#!/usr/bin/env python3
"""Design project execution object manager.

Manages design workbench project state as execution objects,
providing versioning, history tracking, and save/load operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.engines.execution_objects.workflow import ExecutionObjectStore


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _project_title(project_state: dict[str, Any]) -> str:
    """Generate a title for a design project execution object."""
    project_name = project_state.get("projectName", "未命名项目")
    return f"设计项目: {project_name}"


def _extract_related_facts(project_state: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata facts from project state."""
    nodes = project_state.get("nodes", {})
    domains = project_state.get("domains", {})

    completed_nodes = sum(
        1 for node in nodes.values()
        if isinstance(node, dict) and node.get("decisionState") == "completed"
    )

    total_entities = sum(
        len(node.get("designEntities", []))
        for node in nodes.values()
        if isinstance(node, dict)
    )

    return {
        "engine_version": "DesignEngine v1.0",
        "domain_count": len(domains),
        "node_count": len(nodes),
        "completed_nodes": completed_nodes,
        "total_entities": total_entities,
        "has_profile": "profile" in project_state,
        "last_updated": _now_iso(),
    }


def save_design_project(
    store: ExecutionObjectStore,
    project_state: dict[str, Any],
    *,
    title: str | None = None,
    save_type: str = "manual",
    auto_verify: bool = True,
) -> dict[str, Any]:
    """Save design project to execution object store.

    Args:
        store: Execution object store
        project_state: Complete design project state dictionary
        title: Optional custom title (defaults to project name)
        save_type: "manual" or "auto" (for auto-save)
        auto_verify: If True, immediately verify the object (default for manual saves)

    Returns:
        Created execution object dictionary
    """
    project_name = project_state.get("projectName", "未命名项目")
    object_title = title or _project_title(project_state)
    related_facts = _extract_related_facts(project_state)

    # Generate write scope
    write_scope = [
        "design:project_state",
        "design:nodes",
        "design:domains",
        f"design:project:{project_name}",
    ]

    # Create draft
    draft = store.create_draft(
        object_type="design_project",
        title=object_title,
        source_diagnostic_id=f"workbench:design_project:{project_name}",
        prefilled_content={},
        user_content=project_state,
        related_facts=related_facts,
        write_scope=write_scope,
        metadata={
            "stage": "design",
            "business_id": f"design_project:{project_name}",
            "created_by": "design_workbench",
            "save_type": save_type,
            "auto_save_version": related_facts.get("auto_save_version", 1),
        },
    )

    execution_object_id = draft["execution_object_id"]

    # For manual saves, submit and verify immediately
    if auto_verify and save_type == "manual":
        from core.engines.execution_objects.type_registry import get_confirmation_level

        confirmation_level = get_confirmation_level("design_project")

        # Submit
        store.submit(
            execution_object_id,
            final_content=project_state,
            confirmation_level=confirmation_level,
            submission_confirmation_marker=f"{project_name}:submitted",
            submitter_marker="workbench_user",
        )

        # Analyze
        store.start_analysis(execution_object_id)
        store.complete_impact_analysis(
            execution_object_id,
            affected_scopes=write_scope,
            invalidation_scope=write_scope,
            summary=f"设计项目保存: {project_name}",
            diagnostics={"save_type": save_type},
        )

        # Approve
        store.approve(
            execution_object_id,
            confirmation_evidence={
                "confirmation_type": "user_save_action",
                "confirmed_by": "workbench_user",
                "confirmed_at": _now_iso(),
            },
        )

        # Start execution (no actual execution needed for design projects)
        store.start_execution(execution_object_id)

        # Verify immediately
        store.verify_execution(
            execution_object_id,
            verification_evidence={
                "verified_at": _now_iso(),
                "verification_method": "auto_verify",
                "project_state_hash": store._hash_content(project_state),
            },
        )

    return store.get(execution_object_id)


def auto_save_design_project(
    store: ExecutionObjectStore,
    project_state: dict[str, Any],
) -> dict[str, Any]:
    """Auto-save design project (creates draft only).

    Args:
        store: Execution object store
        project_state: Complete design project state dictionary

    Returns:
        Created draft execution object
    """
    return save_design_project(
        store,
        project_state,
        save_type="auto",
        auto_verify=False,
    )


def load_latest_design_project(
    store: ExecutionObjectStore,
) -> dict[str, Any] | None:
    """Load the latest verified design project.

    Args:
        store: Execution object store

    Returns:
        Project state dictionary or None if no verified project exists
    """
    # Find all verified design_project objects
    objects = store.list_objects(states={"verified"})
    design_projects = [
        obj for obj in objects
        if obj.get("object_type") == "design_project"
    ]

    if not design_projects:
        return None

    # Sort by updated_at descending
    design_projects.sort(
        key=lambda obj: obj.get("updated_at", ""),
        reverse=True,
    )

    latest = design_projects[0]
    return latest.get("user_content", {})


def list_design_project_versions(
    store: ExecutionObjectStore,
    *,
    include_drafts: bool = False,
) -> list[dict[str, Any]]:
    """List all design project versions.

    Args:
        store: Execution object store
        include_drafts: If True, include draft versions

    Returns:
        List of execution objects sorted by updated_at (newest first)
    """
    states = {"verified"}
    if include_drafts:
        states.update({"draft", "submitted", "approved"})

    objects = store.list_objects(states=states)
    design_projects = [
        obj for obj in objects
        if obj.get("object_type") == "design_project"
    ]

    # Sort by updated_at descending
    design_projects.sort(
        key=lambda obj: obj.get("updated_at", ""),
        reverse=True,
    )

    return design_projects


def restore_design_project_version(
    store: ExecutionObjectStore,
    execution_object_id: str,
) -> dict[str, Any]:
    """Restore a specific version of the design project.

    Args:
        store: Execution object store
        execution_object_id: ID of the execution object to restore

    Returns:
        Project state dictionary

    Raises:
        ValueError: If execution_object_id is not a design_project
    """
    obj = store.get(execution_object_id)

    if obj.get("object_type") != "design_project":
        raise ValueError(
            f"Execution object {execution_object_id} is not a design_project"
        )

    return obj.get("user_content", {})


def get_design_project_metadata(
    store: ExecutionObjectStore,
    execution_object_id: str,
) -> dict[str, Any]:
    """Get metadata for a design project execution object.

    Args:
        store: Execution object store
        execution_object_id: ID of the execution object

    Returns:
        Metadata dictionary with project info
    """
    obj = store.get(execution_object_id)

    return {
        "execution_object_id": obj.get("execution_object_id"),
        "title": obj.get("title"),
        "state": obj.get("state"),
        "created_at": obj.get("created_at"),
        "updated_at": obj.get("updated_at"),
        "project_name": obj.get("user_content", {}).get("projectName"),
        "save_type": obj.get("metadata", {}).get("save_type"),
        "related_facts": obj.get("related_facts", {}),
    }


__all__ = [
    "save_design_project",
    "auto_save_design_project",
    "load_latest_design_project",
    "list_design_project_versions",
    "restore_design_project_version",
    "get_design_project_metadata",
]
