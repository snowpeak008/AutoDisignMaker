"""Path management for AutoDesignMaker.

All runtime paths are derived from the directory containing `.project_root`.
This keeps the project movable across drives and workspaces.
"""

from __future__ import annotations

from pathlib import Path


ROOT_MARKER = ".project_root"


def locate_project_root(start_path: Path | None = None) -> Path:
    """Locate the project root by walking upward until `.project_root` is found."""

    current = Path(start_path or __file__).resolve()
    if current.is_file():
        current = current.parent

    while True:
        if (current / ROOT_MARKER).exists():
            return current
        if current == current.parent:
            raise RuntimeError(
                f"Unable to locate project root: {ROOT_MARKER} was not found "
                f"from {Path(start_path or __file__).resolve()}"
            )
        current = current.parent


PROJECT_ROOT = locate_project_root()

SRC_DIR = PROJECT_ROOT / "src"
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DESIGN_DATA_DIR = DATA_DIR / "design"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
SCHEMAS_DIR = DATA_DIR / "schemas"

WORKSPACE_DIR = PROJECT_ROOT / "workspace"
PROJECTS_DIR = WORKSPACE_DIR / "projects"
EXPORTS_DIR = WORKSPACE_DIR / "exports"
SAVES_DIR = WORKSPACE_DIR / "saves"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
ARTIFACTS_DIR = OUTPUTS_DIR / "artifacts"
SOURCE_ARTIFACTS_DIR = WORKSPACE_DIR / "source_artifacts"

UCOS_DIR = PROJECT_ROOT / "ucos"
MEMORY_DIR = PROJECT_ROOT / "memory"
DOCS_DIR = PROJECT_ROOT / "docs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"
ARCHIVE_DIR = PROJECT_ROOT / "_archive"

APP_CONFIG_FILE = CONFIG_DIR / "app.toml"
PROJECT_SETTINGS_FILE = CONFIG_DIR / "project_settings.json"
PLUGIN_MANIFEST_FILE = SRC_DIR / "plugins" / "plugin_manifest.json"


def ensure_directory_exists(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_path(relative_path: str | Path) -> Path:
    return PROJECT_ROOT / relative_path


def get_stage_artifact_dir(stage_id: str) -> Path:
    safe_stage = str(stage_id).lower().replace(" ", "_")
    return ensure_directory_exists(ARTIFACTS_DIR / f"stage_{safe_stage}")


def resolve_configured_path(value: str | Path, *, base: Path = PROJECT_ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


__all__ = [
    "ROOT_MARKER",
    "PROJECT_ROOT",
    "SRC_DIR",
    "CONFIG_DIR",
    "DATA_DIR",
    "DESIGN_DATA_DIR",
    "KNOWLEDGE_DIR",
    "SCHEMAS_DIR",
    "WORKSPACE_DIR",
    "PROJECTS_DIR",
    "EXPORTS_DIR",
    "SAVES_DIR",
    "OUTPUTS_DIR",
    "ARTIFACTS_DIR",
    "SOURCE_ARTIFACTS_DIR",
    "UCOS_DIR",
    "MEMORY_DIR",
    "DOCS_DIR",
    "SCRIPTS_DIR",
    "TESTS_DIR",
    "ARCHIVE_DIR",
    "APP_CONFIG_FILE",
    "PROJECT_SETTINGS_FILE",
    "PLUGIN_MANIFEST_FILE",
    "locate_project_root",
    "ensure_directory_exists",
    "project_path",
    "get_stage_artifact_dir",
    "resolve_configured_path",
]

