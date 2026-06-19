"""Shared save-scoped paths for execution-object stores."""

from __future__ import annotations

from pathlib import Path

from core.paths import PROJECT_ROOT
from core.save import manager as save_manager


EXECUTION_OBJECT_STORE_RELATIVE_PATH = Path("outputs") / "execution_objects" / "execution_objects.json"


def expected_save_id(project_root: Path = PROJECT_ROOT) -> str | None:
    return save_manager.current_save_id(Path(project_root))


def execution_object_store_path(project_root: Path = PROJECT_ROOT) -> Path | None:
    workspace = save_manager.current_save_workspace_dir(Path(project_root))
    if workspace is None:
        return None
    return workspace / EXECUTION_OBJECT_STORE_RELATIVE_PATH
