from pathlib import Path

import pytest

from src.core.config_loader import ConfigLoader, load_config


def test_load_config_project_name():
    config = load_config()
    assert config.get("project.name") == "AutoDesignMaker"
    assert config.get("paths.design_data") == "data/design"


def test_missing_app_config_raises_clear_error(tmp_path: Path):
    loader = ConfigLoader(
        app_config_file=tmp_path / "missing.toml",
        project_settings_file=tmp_path / "project_settings.json",
    )
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        loader.load()


def test_invalid_toml_raises_clear_error(tmp_path: Path):
    app_config = tmp_path / "app.toml"
    app_config.write_text("invalid toml [", encoding="utf-8")
    loader = ConfigLoader(
        app_config_file=app_config,
        project_settings_file=tmp_path / "project_settings.json",
    )
    with pytest.raises(ValueError, match="Failed to parse TOML configuration"):
        loader.load()


def test_project_settings_created_on_load(tmp_path: Path):
    app_config = tmp_path / "app.toml"
    settings = tmp_path / "project_settings.json"
    app_config.write_text("[project]\nname = \"AutoDesignMaker\"\n", encoding="utf-8")
    loader = ConfigLoader(app_config_file=app_config, project_settings_file=settings)
    loader.load()
    assert settings.exists()
