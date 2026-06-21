from pathlib import Path

from core.config.loader import ConfigLoader, load_config


def test_load_config_project_name():
    config = load_config()
    assert config.get("project.name") == "AutoDesignMaker"
    assert config.get("plugins.manifest_path") == "pipeline/_registry.json"


def test_missing_app_config_uses_defaults(tmp_path: Path):
    loader = ConfigLoader(
        app_config_file=tmp_path / "missing.toml",
        project_settings_file=tmp_path / "project_settings.json",
    )
    loader.load()
    assert loader.get("project.name") == "AutoDesignMaker"


def test_invalid_toml_uses_defaults(tmp_path: Path):
    app_config = tmp_path / "app.toml"
    app_config.write_text("invalid toml [", encoding="utf-8")
    loader = ConfigLoader(
        app_config_file=app_config,
        project_settings_file=tmp_path / "project_settings.json",
    )
    loader.load()
    assert loader.get("project.name") == "AutoDesignMaker"


def test_project_settings_created_on_save(tmp_path: Path):
    app_config = tmp_path / "app.toml"
    settings = tmp_path / "project_settings.json"
    app_config.write_text("[project]\nname = \"AutoDesignMaker\"\n", encoding="utf-8")
    loader = ConfigLoader(app_config_file=app_config, project_settings_file=settings)
    loader.load()
    assert not settings.exists()
    loader.set_project_setting("last_active_stage", "03")
    assert settings.exists()
