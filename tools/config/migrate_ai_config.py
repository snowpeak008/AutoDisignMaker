"""Migrate legacy AI settings into settings/ai_config.json."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config.ai_config import (
    AIConfig,
    AIProfile,
    ImageConfig,
    LLMConfig,
    create_default_config,
    save_ai_config,
)
from core.config.loader import _read_toml
from core.io import write_text
from core.paths import LOGS_DIR, SETTINGS_DIR


LEGACY_PROFILES_PATH = SETTINGS_DIR / "ai_profiles.json"
LEGACY_API_CONFIG_PATH = SETTINGS_DIR / "api_config.toml"
APP_CONFIG_PATH = SETTINGS_DIR / "app.toml"
PROJECT_SETTINGS_PATH = SETTINGS_DIR / "project_settings.json"
MIGRATION_LOG_PATH = LOGS_DIR / "config_migration.log"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _legacy_profile_to_v2(raw: dict[str, Any], fallback_id: str) -> AIProfile:
    llm = raw.get("llm") if isinstance(raw.get("llm"), dict) else {}
    image = raw.get("image") if isinstance(raw.get("image"), dict) else {}
    return AIProfile(
        id=str(raw.get("id") or fallback_id),
        name=str(raw.get("name") or raw.get("id") or fallback_id),
        adapter=str(raw.get("adapter") or "openai"),
        llm=LLMConfig(
            source="api" if str(llm.get("source") or "config") != "local" else "api",
            provider=str(llm.get("provider") or "openai"),
            base_url=str(llm.get("base_url") or ""),
            api_key=str(llm.get("api_key") or ""),
            model=str(llm.get("model") or "gpt-5.5"),
            reasoning_effort=llm.get("reasoning_effort"),
        ),
        image=ImageConfig(
            enabled=bool(image.get("enabled", False)),
            source="api",
            provider=str(image.get("provider") or "openai"),
            base_url=str(image.get("base_url") or ""),
            api_key=str(image.get("api_key") or ""),
            model=str(image.get("model") or "gpt-image-2"),
        ),
        metadata={"migrated_from": "ai_profiles.json"},
    )


def _profile_from_api_config(api_config: dict[str, Any]) -> AIProfile | None:
    llm = api_config.get("llm") if isinstance(api_config.get("llm"), dict) else {}
    image = api_config.get("image") if isinstance(api_config.get("image"), dict) else {}
    image2 = api_config.get("image2") if isinstance(api_config.get("image2"), dict) else {}
    if not llm and not image and not image2:
        return None
    merged_image = dict(image)
    merged_image.update(image2)
    return AIProfile(
        id="legacy_api",
        name="旧版 API 配置",
        adapter="openai",
        llm=LLMConfig(
            source="api",
            provider=str(llm.get("provider") or "openai"),
            base_url=str(llm.get("base_url") or ""),
            api_key=str(llm.get("api_key") or ""),
            model=str(llm.get("model") or llm.get("default_model") or "gpt-5.5"),
            reasoning_effort=llm.get("reasoning_effort"),
        ),
        image=ImageConfig(
            enabled=False,
            source="api",
            provider=str(merged_image.get("provider") or llm.get("provider") or "openai"),
            base_url=str(merged_image.get("base_url") or llm.get("base_url") or ""),
            api_key=str(merged_image.get("api_key") or llm.get("api_key") or ""),
            model=str(merged_image.get("model") or merged_image.get("default_model") or "gpt-image-2"),
        ),
        metadata={"migrated_from": "api_config.toml"},
    )


def _app_model_profile(app_config: dict[str, Any]) -> AIProfile | None:
    model = app_config.get("model") if isinstance(app_config.get("model"), dict) else {}
    if not model:
        return None
    return AIProfile(
        id="app_model",
        name="app.toml 模型配置",
        adapter="openai",
        llm=LLMConfig(
            source="api",
            provider=str(model.get("provider") or "openai"),
            base_url=str(model.get("base_url") or ""),
            api_key=str(model.get("api_key") or ""),
            model=str(model.get("model") or "gpt-5.5"),
            temperature=float(model.get("temperature") or 0.7),
            timeout=int(model.get("timeout") or 300),
        ),
        image=ImageConfig(enabled=False, source="none"),
        metadata={"migrated_from": "app.toml"},
    )


def migrate_from_legacy(*, target_path: Path | None = None) -> AIConfig:
    defaults = create_default_config()
    profiles: list[AIProfile] = []
    legacy_profiles = _read_json(LEGACY_PROFILES_PATH)
    for index, raw in enumerate(legacy_profiles.get("profiles", []), 1):
        if isinstance(raw, dict):
            profiles.append(_legacy_profile_to_v2(raw, f"legacy_profile_{index}"))
    api_profile = _profile_from_api_config(_read_toml(LEGACY_API_CONFIG_PATH))
    if api_profile:
        profiles.append(api_profile)
    app_profile = _app_model_profile(_read_toml(APP_CONFIG_PATH))
    if app_profile:
        profiles.append(app_profile)
    if not profiles:
        profiles = defaults.profiles
    project_settings = _read_json(PROJECT_SETTINGS_PATH)
    active = str(legacy_profiles.get("active_profile") or "")
    adapter = str(project_settings.get("pipeline_adapter") or "").strip().lower()
    if adapter in {"codex", "claude", "openai", "local", "none"}:
        for profile in defaults.profiles:
            if profile.adapter == adapter:
                profiles.insert(0, profile)
                active = profile.id
                break
    active_ids = {profile.id for profile in profiles}
    active = active if active in active_ids else profiles[0].id
    config = AIConfig(active_profile_id=active, profiles=profiles)
    if target_path:
        save_ai_config(config, path=target_path)
    return config


def backup_legacy_files(*, settings_dir: Path = SETTINGS_DIR) -> Path | None:
    files = [
        settings_dir / "ai_profiles.json",
        settings_dir / "api_config.toml",
        settings_dir / "app.toml",
        settings_dir / "project_settings.json",
    ]
    existing = [path for path in files if path.exists()]
    if not existing:
        return None
    backup_dir = settings_dir / f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in existing:
        shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def run_migration(*, target_path: Path | None = None, backup: bool = True) -> bool:
    target = target_path or SETTINGS_DIR / "ai_config.json"
    legacy_exists = LEGACY_PROFILES_PATH.exists() or LEGACY_API_CONFIG_PATH.exists() or bool(_read_toml(APP_CONFIG_PATH).get("model"))
    if target.exists() or not legacy_exists:
        return False
    config = migrate_from_legacy(target_path=target)
    backup_dir = backup_legacy_files() if backup else None
    log_lines = [
        f"{datetime.now().isoformat(timespec='seconds')} migrated AI config",
        f"target={target}",
        f"active_profile_id={config.active_profile_id}",
        f"profiles={','.join(profile.id for profile in config.profiles)}",
    ]
    if backup_dir:
        log_lines.append(f"backup={backup_dir}")
    write_text(MIGRATION_LOG_PATH, "\n".join(log_lines) + "\n")
    return True


if __name__ == "__main__":
    print("开始迁移AI配置...")
    if run_migration():
        print("✓ 迁移成功")
    else:
        print("✗ 迁移失败或无需迁移")
