"""Validate the AutoDesignMaker project structure."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.paths import (  # noqa: E402
    APP_CONFIG_FILE,
    CONFIG_DIR,
    DATA_DIR,
    DESIGN_DATA_DIR,
    DOCS_DIR,
    MEMORY_DIR,
    PLUGIN_MANIFEST_FILE,
    PROJECT_SETTINGS_FILE,
    SRC_DIR,
    UCOS_DIR,
    WORKSPACE_DIR,
    locate_project_root,
)


REQUIRED_DIRS = [
    SRC_DIR,
    SRC_DIR / "core",
    SRC_DIR / "plugins" / "stages" / "design",
    SRC_DIR / "plugins" / "stages" / "development",
    SRC_DIR / "engines" / "design",
    SRC_DIR / "engines" / "orchestrator",
    CONFIG_DIR,
    DATA_DIR,
    DESIGN_DATA_DIR,
    DESIGN_DATA_DIR / "domains",
    DESIGN_DATA_DIR / "templates",
    DESIGN_DATA_DIR / "entity_schemas",
    WORKSPACE_DIR,
    WORKSPACE_DIR / "projects",
    WORKSPACE_DIR / "exports",
    WORKSPACE_DIR / "saves",
    WORKSPACE_DIR / "outputs" / "artifacts",
    UCOS_DIR,
    MEMORY_DIR,
    DOCS_DIR,
]

REQUIRED_FILES = [
    PROJECT_ROOT / ".project_root",
    APP_CONFIG_FILE,
    PROJECT_SETTINGS_FILE,
    PLUGIN_MANIFEST_FILE,
    SRC_DIR / "core" / "paths.py",
    SRC_DIR / "core" / "config_loader.py",
    SRC_DIR / "core" / "plugin_manager.py",
    SRC_DIR / "main.py",
    PROJECT_ROOT / "orchestrator.py",
]

REQUIRED_IMPORTS = [
    "src.core.paths",
    "src.core.config_loader",
    "src.core.plugin_manager",
    "design_tool.data_loader",
    "orchestrator",
]


def validate_structure() -> bool:
    errors: list[str] = []

    located = locate_project_root(PROJECT_ROOT)
    if located != PROJECT_ROOT:
        errors.append(f"PROJECT_ROOT mismatch: {located} != {PROJECT_ROOT}")

    for directory in REQUIRED_DIRS:
        if not directory.is_dir():
            errors.append(f"Missing directory: {directory.relative_to(PROJECT_ROOT)}")

    for file_path in REQUIRED_FILES:
        if not file_path.is_file():
            errors.append(f"Missing file: {file_path.relative_to(PROJECT_ROOT)}")

    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - validation should report all import failures.
            errors.append(f"Import failed: {module_name}: {exc}")

    if errors:
        print("AutoDesignMaker structure validation failed")
        for error in errors:
            print(f"- {error}")
        return False

    print("AutoDesignMaker structure validation passed")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if validate_structure() else 1)

