from __future__ import annotations

from core.paths import (
    DATA_DIR,
    DESIGN_DATA_DIR,
    DRAFT_DIR,
    DRAFTS_DIR,
    KNOWLEDGE_DIR,
    PROJECT_ROOT,
    SANDBOX_DIR,
    locate_project_root,
)


def test_project_root_marker():
    assert (PROJECT_ROOT / ".project_root").exists()
    assert locate_project_root(PROJECT_ROOT / "core") == PROJECT_ROOT


def test_design_data_path():
    assert DATA_DIR == KNOWLEDGE_DIR / "design_data"
    assert DESIGN_DATA_DIR == DATA_DIR


def test_runtime_root_is_session_draft():
    assert DRAFT_DIR.parent == DRAFTS_DIR
    assert SANDBOX_DIR == DRAFT_DIR
    assert SANDBOX_DIR != PROJECT_ROOT / "sandbox"


def test_design_tool_uses_core_design_data_path():
    from core.design.data_loader import data_dir, runtime_project_root

    assert data_dir() == DESIGN_DATA_DIR
    assert runtime_project_root() == DRAFT_DIR
