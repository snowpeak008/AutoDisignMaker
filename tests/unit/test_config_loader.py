from src.core.config_loader import load_config


def test_load_config_project_name():
    config = load_config()
    assert config.get("project.name") == "AutoDesignMaker"
    assert config.get("paths.design_data") == "data/design"

