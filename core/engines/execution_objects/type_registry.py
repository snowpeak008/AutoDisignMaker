#!/usr/bin/env python3
"""Execution object type registry.

Defines all execution object types, their confirmation levels, and metadata.
"""

from __future__ import annotations

from typing import Any


EXECUTION_OBJECT_TYPES: dict[str, dict[str, Any]] = {
    # ── 新增：设计相关执行对象 ──────────────────────────────────
    "design_project": {
        "display_name": "设计项目",
        "description": "设计工作台的游戏设计项目完整状态",
        "confirmation_level": "elevated_confirm",
        "write_scope_prefix": "design:",
        "manager_module": "core.engines.execution_objects.design_project",
        "category": "design",
    },
    "workspace_snapshot": {
        "display_name": "工作区快照",
        "description": "沙盒工作区文件状态快照",
        "confirmation_level": "normal_confirm",
        "write_scope_prefix": "workspace:",
        "manager_module": "core.engines.execution_objects.workspace_snapshot",
        "category": "workspace",
    },
    "user_artifact": {
        "display_name": "用户导出制品",
        "description": "用户从设计工作台导出的内容",
        "confirmation_level": "normal_confirm",
        "write_scope_prefix": "workspace:exports",
        "manager_module": "core.engines.execution_objects.user_artifact",
        "category": "export",
    },

    # ── 已有：开发相关执行对象 ──────────────────────────────────
    "program_task": {
        "display_name": "程序开发任务",
        "description": "程序代码开发任务",
        "confirmation_level": "normal_confirm",
        "write_scope_prefix": "program:",
        "category": "development",
    },
    "art_task": {
        "display_name": "美术制作任务",
        "description": "美术资源制作任务",
        "confirmation_level": "t3_art_confirm",
        "write_scope_prefix": "art:",
        "category": "art",
    },
    "rollback_plan": {
        "display_name": "回滚计划",
        "description": "代码或资源回滚计划",
        "confirmation_level": "destructive_confirm",
        "write_scope_prefix": "rollback:",
        "category": "maintenance",
    },
    "asset_contract_change": {
        "display_name": "资产契约变更",
        "description": "资产契约结构变更",
        "confirmation_level": "elevated_confirm",
        "write_scope_prefix": "contract:",
        "category": "architecture",
    },
    "reference_migration": {
        "display_name": "引用迁移",
        "description": "资产引用路径迁移",
        "confirmation_level": "elevated_confirm",
        "write_scope_prefix": "reference:",
        "category": "maintenance",
    },
    "unity_replacement_batch": {
        "display_name": "Unity批量替换",
        "description": "Unity项目文件批量替换",
        "confirmation_level": "destructive_confirm",
        "write_scope_prefix": "unity:",
        "category": "unity",
    },
    "relationship_graph_correction": {
        "display_name": "关系图修正",
        "description": "资产关系图数据修正",
        "confirmation_level": "elevated_confirm",
        "write_scope_prefix": "graph:",
        "category": "architecture",
    },
    "integration_validation": {
        "display_name": "集成验证",
        "description": "集成测试验证记录",
        "confirmation_level": "normal_confirm",
        "write_scope_prefix": "integration:",
        "category": "validation",
    },
    "merged_execution_object": {
        "display_name": "合并执行对象",
        "description": "多个执行对象的合并记录",
        "confirmation_level": "elevated_confirm",
        "write_scope_prefix": "merge:",
        "category": "maintenance",
    },
    "t3_art_baseline_change": {
        "display_name": "T3美术基线变更",
        "description": "T3级美术资源基线变更",
        "confirmation_level": "t3_art_confirm",
        "write_scope_prefix": "art:baseline:",
        "category": "art",
    },
}


def get_type_metadata(object_type: str) -> dict[str, Any]:
    """Get metadata for an execution object type.

    Args:
        object_type: The execution object type identifier

    Returns:
        Type metadata dictionary

    Raises:
        ValueError: If object_type is not registered
    """
    if object_type not in EXECUTION_OBJECT_TYPES:
        raise ValueError(f"Unknown execution object type: {object_type}")
    return EXECUTION_OBJECT_TYPES[object_type].copy()


def get_confirmation_level(object_type: str) -> str:
    """Get the required confirmation level for an execution object type.

    Args:
        object_type: The execution object type identifier

    Returns:
        Confirmation level string (e.g., "normal_confirm", "elevated_confirm")

    Raises:
        ValueError: If object_type is not registered
    """
    metadata = get_type_metadata(object_type)
    return metadata["confirmation_level"]


def get_display_name(object_type: str) -> str:
    """Get the display name for an execution object type.

    Args:
        object_type: The execution object type identifier

    Returns:
        Human-readable display name

    Raises:
        ValueError: If object_type is not registered
    """
    metadata = get_type_metadata(object_type)
    return metadata["display_name"]


def get_write_scope_prefix(object_type: str) -> str:
    """Get the write scope prefix for an execution object type.

    Args:
        object_type: The execution object type identifier

    Returns:
        Write scope prefix string (e.g., "design:", "workspace:")

    Raises:
        ValueError: If object_type is not registered
    """
    metadata = get_type_metadata(object_type)
    return metadata.get("write_scope_prefix", "")


def get_manager_module(object_type: str) -> str | None:
    """Get the manager module path for an execution object type.

    Args:
        object_type: The execution object type identifier

    Returns:
        Module path string or None if no dedicated manager exists

    Raises:
        ValueError: If object_type is not registered
    """
    metadata = get_type_metadata(object_type)
    return metadata.get("manager_module")


def list_types_by_category(category: str) -> list[str]:
    """List all execution object types in a category.

    Args:
        category: Category name (e.g., "design", "development", "art")

    Returns:
        List of object type identifiers in the category
    """
    return [
        obj_type
        for obj_type, metadata in EXECUTION_OBJECT_TYPES.items()
        if metadata.get("category") == category
    ]


def list_all_types() -> list[str]:
    """List all registered execution object types.

    Returns:
        List of all object type identifiers
    """
    return list(EXECUTION_OBJECT_TYPES.keys())


def is_registered_type(object_type: str) -> bool:
    """Check if an execution object type is registered.

    Args:
        object_type: The execution object type identifier

    Returns:
        True if registered, False otherwise
    """
    return object_type in EXECUTION_OBJECT_TYPES


__all__ = [
    "EXECUTION_OBJECT_TYPES",
    "get_type_metadata",
    "get_confirmation_level",
    "get_display_name",
    "get_write_scope_prefix",
    "get_manager_module",
    "list_types_by_category",
    "list_all_types",
    "is_registered_type",
]
