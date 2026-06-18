#!/usr/bin/env python3
"""Shared save-scoped paths for execution-object stores."""

from __future__ import annotations

from pathlib import Path

from steps.common import BASE_DIR
from tools import save_manager


EXECUTION_OBJECT_STORE_RELATIVE_PATH = Path("outputs") / "execution_objects" / "execution_objects.json"


def expected_save_id(project_root: Path = BASE_DIR) -> str | None:
    return save_manager.current_save_id(Path(project_root))


def execution_object_store_path(project_root: Path = BASE_DIR) -> Path | None:
    workspace = save_manager.current_save_workspace_dir(Path(project_root))
    if workspace is None:
        return None
    return workspace / EXECUTION_OBJECT_STORE_RELATIVE_PATH
