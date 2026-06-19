from src.core.paths import DATA_DIR, DESIGN_DATA_DIR, PROJECT_ROOT, locate_project_root


def test_project_root_marker():
    assert (PROJECT_ROOT / ".project_root").exists()
    assert locate_project_root(PROJECT_ROOT / "src" / "core") == PROJECT_ROOT


def test_design_data_path():
    assert DATA_DIR.name == "data"
    assert DESIGN_DATA_DIR == DATA_DIR / "design"


def test_design_tool_uses_core_design_data_path():
    from design_tool.data_loader import data_dir

    assert data_dir() == DESIGN_DATA_DIR
