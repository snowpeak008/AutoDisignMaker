from __future__ import annotations

import json

from core.config import ai_config


def test_create_default_config_has_four_profiles() -> None:
    config = ai_config.create_default_config()

    assert config.active_profile_id == "default"
    assert config.schema_version == 3
    assert config.dev.active_entry_id == "default"
    assert config.image.active_entry_id == "codex_cli_image"
    assert config.completion.active_entry_id == "completion_openai_api"
    assert {profile.id for profile in config.profiles} >= {
        "default",
        "codex_cli",
        "claude_cli",
        "local_ollama",
    }


def test_save_and_load_ai_config(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    config = ai_config.create_default_config()
    config.dev.active_entry_id = "codex_cli"

    ai_config.save_ai_config(config, path=path)
    loaded = ai_config.load_ai_config(path=path)

    assert loaded.active_profile_id == "codex_cli"
    assert loaded.active_profile.adapter == "codex"
    assert loaded.dev.active_entry_id == "codex_cli"


def test_save_ai_config_does_not_mutate_input_active_profile(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    config = ai_config.create_default_config()
    config.dev.active_entry_id = "codex_cli"

    ai_config.save_ai_config(config, path=path)
    loaded = ai_config.load_ai_config(path=path)

    assert config.active_profile_id == "default"
    assert loaded.active_profile_id == "codex_cli"


def test_set_active_profile(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    ai_config.ensure_ai_config_file(path=path)

    ai_config.set_active_profile("local_ollama", path=path)

    assert ai_config.get_active_profile(path=path).id == "local_ollama"


def test_profile_serialization_normalizes_legacy_active_key(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    ai_config.save_ai_config(
        {
            "schema_version": 1,
            "active_profile": "legacy",
            "profiles": [
                {
                    "id": "legacy",
                    "name": "Legacy",
                    "adapter": "openai",
                    "llm": {
                        "source": "api",
                        "base_url": "https://relay.example",
                        "api_key": "sk-test",
                        "model": "gpt-4o",
                    },
                    "image": {"enabled": False, "source": "none"},
                }
            ],
        },
        path=path,
    )

    loaded = ai_config.load_ai_config(path=path)

    assert loaded.schema_version == 3
    assert loaded.dev.active_entry_id == "legacy"
    assert loaded.completion.active_entry_id == "completion_legacy"
    assert loaded.active_profile_id == "legacy"
    assert loaded.active_profile.llm.model == "gpt-4o"


def test_loading_legacy_file_writes_v3_schema(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "active_profile_id": "legacy_api",
                "profiles": [
                    {
                        "id": "legacy_api",
                        "name": "Legacy API",
                        "adapter": "openai",
                        "llm": {
                            "source": "api",
                            "base_url": "https://relay.example/v1",
                            "api_key": "sk-legacy",
                            "model": "gpt-4o",
                        },
                        "image": {"enabled": False, "source": "none"},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = ai_config.load_ai_config(path=path)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert loaded.schema_version == 3
    assert saved["schema_version"] == 3
    assert saved["dev"]["active_entry_id"] == "legacy_api"
    assert "profiles" not in saved


def test_empty_image_active_entry_defaults_to_first_entry(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    data = ai_config.config_to_dict(ai_config.create_default_config())
    data["image"]["active_entry_id"] = ""
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    loaded = ai_config.load_ai_config(path=path)

    assert loaded.image.active_entry_id == "codex_cli_image"
    assert ai_config.image_config_from_entry(loaded.image.active_entry).enabled is True


def test_compat_profiles_have_independent_image_configs() -> None:
    config = ai_config.create_default_config()
    config.image.active_entry_id = "codex_cli_image"
    config = ai_config.AIConfig(dev=config.dev, image=config.image, completion=config.completion)

    assert config.profiles[0].image is not config.profiles[1].image
    assert config.profiles[1].image.enabled is True
    config.profiles[0].image.enabled = False
    assert config.profiles[1].image.enabled is True


def test_dialog_type_assignment_preserves_custom_label() -> None:
    from core.ui.ai_config_unified_dialog import AIConfigUnifiedDialog

    custom = ai_config.APIEntry("prod", "生产环境 OpenAI", "openai_dev_api")
    AIConfigUnifiedDialog._set_entry_type(None, custom, "custom_dev_api")  # type: ignore[arg-type]
    assert custom.label == "生产环境 OpenAI"

    default = ai_config.APIEntry("api", "OpenAI 兼容 API", "openai_dev_api")
    AIConfigUnifiedDialog._set_entry_type(None, default, "local_codex_cli")  # type: ignore[arg-type]
    assert default.label == "本地 Codex CLI"


def test_migration_tool_merges_legacy_api_config(tmp_path, monkeypatch) -> None:
    from tools.config import migrate_ai_config

    api_config = tmp_path / "api_config.toml"
    api_config.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai"',
                'base_url = "https://relay.example/v1"',
                'api_key = "sk-legacy"',
                'model = "gpt-4o"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(migrate_ai_config, "LEGACY_API_CONFIG_PATH", api_config)
    monkeypatch.setattr(migrate_ai_config, "LEGACY_PROFILES_PATH", tmp_path / "missing_profiles.json")
    monkeypatch.setattr(migrate_ai_config, "APP_CONFIG_PATH", tmp_path / "missing_app.toml")
    monkeypatch.setattr(migrate_ai_config, "PROJECT_SETTINGS_PATH", tmp_path / "missing_project.json")
    monkeypatch.setattr(migrate_ai_config, "MIGRATION_LOG_PATH", tmp_path / "config_migration.log")
    target = tmp_path / "ai_config.json"

    assert migrate_ai_config.run_migration(target_path=target, backup=False) is True
    migrated = json.loads(target.read_text(encoding="utf-8"))

    assert migrated["schema_version"] == 3
    assert migrated["dev"]["active_entry_id"] == "legacy_api"
    assert migrated["dev"]["entries"][0]["api_key"] == "sk-legacy"


def test_v3_active_entries_roundtrip(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    config = ai_config.create_default_config()
    config.dev.active_entry_id = "codex_cli"
    config.image.active_entry_id = "codex_cli_image"
    config.completion.active_entry_id = "completion_codex_cli"

    ai_config.save_ai_config(config, path=path)
    loaded = ai_config.load_ai_config(path=path)

    assert loaded.dev.active_entry_id == "codex_cli"
    assert loaded.image.active_entry_id == "codex_cli_image"
    assert loaded.completion.active_entry_id == "completion_codex_cli"
    assert ai_config.get_active_image_entry(path=path).config_type == "codex_cli_image"
