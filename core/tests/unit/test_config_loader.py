from pathlib import Path

import pytest

from core.config import ai_config
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
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", tmp_path / "missing_profiles.json")

    with pytest.warns(DeprecationWarning):
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
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", tmp_path / "missing_ai_config.json")

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
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", tmp_path / "missing_ai_config.json")

    settings = image_api_config.load_image_api_settings()

    assert settings.api_key == "sk-test"
    assert settings.image_model == "gpt-image-2"
    assert settings.response_model == "gpt-5.5"


def test_legacy_image_tool_imports_current_config_loader() -> None:
    from tools.asset_production.image_tool import Image2Generator

    assert Image2Generator.name == "IMAGE2 Generator"


def test_api_config_falls_back_when_ai_profile_file_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    api_config = tmp_path / "api_config.toml"
    api_config.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai"',
                'base_url = "https://fallback.example/v1"',
                'api_key = "sk-fallback"',
                'model = "gpt-4o"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(config_loader, "_API_CONFIG_PATH", api_config)

    with pytest.warns(DeprecationWarning):
        cfg = get_api_config("llm")

    assert cfg["api_key"] == "sk-fallback"
    assert cfg["base_url"] == "https://fallback.example/v1"
    assert cfg["default_model"] == "gpt-4o"


def test_api_config_prefers_active_ai_profile(tmp_path: Path, monkeypatch) -> None:
    profile_path = tmp_path / "ai_config.json"
    ai_config.save_ai_config(
        {
            "schema_version": 2,
            "active_profile_id": "relay",
            "profiles": [
                {
                    "id": "relay",
                    "name": "中转",
                    "adapter": "openai",
                    "llm": {
                        "source": "api",
                        "provider": "openai",
                        "base_url": "https://relay.example",
                        "api_key": "sk-relay",
                        "model": "gpt-5.5",
                    },
                    "image": {"enabled": False, "source": "none"},
                }
            ],
        },
        path=profile_path,
    )
    api_config = tmp_path / "api_config.toml"
    api_config.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai"',
                'base_url = "https://fallback.example/v1"',
                'api_key = "sk-fallback"',
                'model = "gpt-4o"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", profile_path)
    monkeypatch.setattr(config_loader, "_API_CONFIG_PATH", api_config)

    with pytest.warns(DeprecationWarning):
        cfg = get_api_config("llm")

    assert cfg["api_key"] == "sk-relay"
    assert cfg["base_url"] == "https://relay.example/v1"
    assert cfg["default_model"] == "gpt-5.5"


def test_image2_config_uses_active_image_profile(tmp_path: Path, monkeypatch) -> None:
    profile_path = tmp_path / "ai_config.json"
    ai_config.save_ai_config(
        {
            "schema_version": 2,
            "active_profile_id": "local",
            "profiles": [
                {
                    "id": "local",
                    "name": "本地",
                    "adapter": "openai",
                    "llm": {},
                    "image": {
                        "source": "api",
                        "enabled": True,
                        "provider": "openai",
                        "base_url": "http://127.0.0.1:7860/sdapi/v1",
                        "api_key": "local",
                        "model": "sd-webui",
                    },
                }
            ],
        },
        path=profile_path,
    )
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", profile_path)

    with pytest.warns(DeprecationWarning):
        cfg = get_api_config("image2")

    assert cfg["api_key"] == "local"
    assert cfg["default_model"] == "sd-webui"


def test_image_generation_enabled_uses_ai_profile(tmp_path: Path, monkeypatch) -> None:
    from core.engines import generation

    profile_path = tmp_path / "ai_config.json"
    data = ai_config.create_default_config()
    data.image.active_entry_id = "codex_cli_image"
    ai_config.save_ai_config(data, path=profile_path)
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", profile_path)
    monkeypatch.delenv("AUTODESIGNMAKER_ENABLE_IMAGE_GENERATION", raising=False)

    assert generation._image_generation_enabled() is True


def test_image_generator_routes_codex_cli_image_entry(
    tmp_path: Path, monkeypatch
) -> None:
    from core.engines import generation
    from tools.asset_production.codex_image_tool import CodexCLIImageGenerator

    profile_path = tmp_path / "ai_config.json"
    data = ai_config.create_default_config()
    data.image.active_entry_id = "codex_cli_image"
    ai_config.save_ai_config(data, path=profile_path)
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", profile_path)

    generator = generation._create_image_generator()

    assert isinstance(generator, CodexCLIImageGenerator)


def test_ai_config_default_file_is_created(tmp_path: Path) -> None:
    profile_path = tmp_path / "ai_config.json"

    created = ai_config.ensure_ai_config_file(path=profile_path)

    assert created == profile_path
    data = ai_config.load_ai_config(path=profile_path)
    assert data.active_profile_id == "default"
    assert len(data.profiles) >= 4
