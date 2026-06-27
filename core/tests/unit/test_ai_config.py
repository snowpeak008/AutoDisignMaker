from __future__ import annotations

import json

from core.config import ai_config


def test_create_default_config_has_four_profiles() -> None:
    config = ai_config.create_default_config()

    assert config.active_profile_id == "default"
    assert {profile.id for profile in config.profiles} >= {
        "default",
        "codex_cli",
        "claude_cli",
        "local_ollama",
    }


def test_save_and_load_ai_config(tmp_path) -> None:
    path = tmp_path / "ai_config.json"
    config = ai_config.create_default_config()
    config.active_profile_id = "codex_cli"

    ai_config.save_ai_config(config, path=path)
    loaded = ai_config.load_ai_config(path=path)

    assert loaded.active_profile_id == "codex_cli"
    assert loaded.active_profile.adapter == "codex"


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

    assert loaded.schema_version == 2
    assert loaded.active_profile_id == "legacy"
    assert loaded.active_profile.llm.model == "gpt-4o"


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

    assert migrated["active_profile_id"] == "legacy_api"
    assert migrated["profiles"][0]["llm"]["api_key"] == "sk-legacy"
