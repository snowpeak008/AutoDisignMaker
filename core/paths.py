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

# ── 核心目录 ──────────────────────────────────────────────
CORE_DIR        = PROJECT_ROOT / "core"
PIPELINE_DIR    = PROJECT_ROOT / "pipeline"

# ── 知识库 ────────────────────────────────────────────────
KNOWLEDGE_DIR   = PROJECT_ROOT / "knowledge"
SCHEMAS_DIR     = KNOWLEDGE_DIR / "schemas"
SKILLS_DIR      = KNOWLEDGE_DIR / "skills"
DATA_DIR        = KNOWLEDGE_DIR / "design_data"     # 原 data/design/
DESIGN_DATA_DIR = DATA_DIR

# ── 设置 ──────────────────────────────────────────────────
SETTINGS_DIR         = PROJECT_ROOT / "settings"
APP_CONFIG_FILE      = SETTINGS_DIR / "app.toml"
PROJECT_SETTINGS_FILE = SETTINGS_DIR / "project_settings.json"
API_CONFIG_FILE      = SETTINGS_DIR / "api_config.toml"

# ── 插件注册表 ────────────────────────────────────────────
PLUGIN_MANIFEST_FILE = PIPELINE_DIR / "_registry.json"

# ── 沙盒（运行时输出） ────────────────────────────────────
SANDBOX_DIR          = PROJECT_ROOT / "sandbox"
SOURCE_ARTIFACTS_DIR = SANDBOX_DIR / "source_artifacts"
OUTPUTS_DIR          = SANDBOX_DIR / "outputs"
ARTIFACTS_DIR        = OUTPUTS_DIR / "artifacts"
CHECKPOINTS_DIR      = OUTPUTS_DIR / "checkpoints"
RUNTIME_CONTROL_DIR  = OUTPUTS_DIR / "runtime_control"

# ── 存档 ──────────────────────────────────────────────────
SAVES_DIR            = PROJECT_ROOT / "saves"
# ── 沙盒工作区 ─────────────────────────────────────────────
WORKSPACE_DIR         = SANDBOX_DIR / "workspace"
WORKSPACE_PROJECTS_DIR = WORKSPACE_DIR / "projects"
WORKSPACE_EXPORTS_DIR  = WORKSPACE_DIR / "exports"


# ── 日志 ──────────────────────────────────────────────────
LOGS_DIR             = PROJECT_ROOT / "logs"

# ── 其他 ──────────────────────────────────────────────────
UCOS_DIR             = PROJECT_ROOT / "ucos"
MEMORY_DIR           = PROJECT_ROOT / "memory"
DOCS_DIR             = PROJECT_ROOT / "docs"
SCRIPTS_DIR          = PROJECT_ROOT / "scripts"
TESTS_DIR            = CORE_DIR / "tests"
ARCHIVE_DIR          = PROJECT_ROOT / "_archive"


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
    "CORE_DIR",
    "PIPELINE_DIR",
    "KNOWLEDGE_DIR",
    "SCHEMAS_DIR",
    "SKILLS_DIR",
    "DATA_DIR",
    "DESIGN_DATA_DIR",
    "SETTINGS_DIR",
    "APP_CONFIG_FILE",
    "PROJECT_SETTINGS_FILE",
    "API_CONFIG_FILE",
    "PLUGIN_MANIFEST_FILE",
    "SANDBOX_DIR",
    "SOURCE_ARTIFACTS_DIR",
    "OUTPUTS_DIR",
    "ARTIFACTS_DIR",
    "CHECKPOINTS_DIR",
    "RUNTIME_CONTROL_DIR",
    "SAVES_DIR",
    "LOGS_DIR",
    "UCOS_DIR",
    "MEMORY_DIR",
    "DOCS_DIR",
    "SCRIPTS_DIR",
    "TESTS_DIR",
    "ARCHIVE_DIR",
    "locate_project_root",
    "ensure_directory_exists",
    "project_path",
    "get_stage_artifact_dir",
    "resolve_configured_path",
]
