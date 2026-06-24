from pathlib import Path

from core.config import loader as config_loader
from core.config.loader import (
    ConfigLoader,
    get_api_config,
    load_config,
    openai_endpoint,
)


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
    app_config.write_text('[project]\nname = "AutoDesignMaker"\n', encoding="utf-8")
    loader = ConfigLoader(app_config_file=app_config, project_settings_file=settings)
    loader.load()
    assert not settings.exists()
    loader.set_project_setting("last_active_stage", "03")
    assert settings.exists()


def test_image2_config_inherits_image_and_llm_settings(tmp_path: Path, monkeypatch):
    api_config = tmp_path / "api_config.toml"
    api_config.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai"',
                'base_url = "https://relay.example/v1"',
                'api_key = "sk-test"',
                'model = "gpt-5.5"',
                "",
                "[image]",
                'model = "gpt-image-2"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_loader, "_API_CONFIG_PATH", api_config)

    cfg = get_api_config("image2")

    assert cfg["api_key"] == "sk-test"
    assert cfg["base_url"] == "https://relay.example/v1"
    assert cfg["default_model"] == "gpt-image-2"


def test_openai_endpoint_normalizes_base_url() -> None:
    assert (
        openai_endpoint("https://relay.example", "responses")
        == "https://relay.example/v1/responses"
    )


def test_image_api_settings_inherits_llm_key_for_image_provider(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.asset_production import image_api_config

    api_config = tmp_path / "api_config.toml"
    api_config.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai"',
                'base_url = "https://relay.example"',
                'api_key = "sk-test"',
                'model = "gpt-5.5"',
                "",
                "[image]",
                'model = "gpt-image-2"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_loader, "_API_CONFIG_PATH", api_config)

    settings = image_api_config.load_image_api_settings()

    assert settings.api_key == "sk-test"
    assert settings.base_url == "https://relay.example/v1"
    assert settings.image_model == "gpt-image-2"


def test_image_api_settings_llm_only_uses_image_default_model(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.asset_production import image_api_config

    api_config = tmp_path / "api_config.toml"
    api_config.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai"',
                'base_url = "https://relay.example/v1"',
                'api_key = "sk-test"',
                'model = "gpt-5.5"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_loader, "_API_CONFIG_PATH", api_config)

    settings = image_api_config.load_image_api_settings()

    assert settings.api_key == "sk-test"
    assert settings.image_model == "gpt-image-2"
    assert settings.response_model == "gpt-5.5"


def test_legacy_image_tool_imports_current_config_loader() -> None:
    from tools.asset_production.image_tool import Image2Generator

    assert Image2Generator.name == "IMAGE2 Generator"
