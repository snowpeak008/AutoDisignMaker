"""Unified AI configuration loader and v2-to-v3 migration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.config.ai_config_schema import (
    AIConfig,
    AIProfile,
    APICategory,
    APIEntry,
    CATEGORY_COMPLETION,
    CATEGORY_DEV,
    CATEGORY_IMAGE,
    CONFIG_TYPE_CODEX_CLI_IMAGE,
    CONFIG_TYPE_CUSTOM_COMPLETION_API,
    CONFIG_TYPE_CUSTOM_DEV_API,
    CONFIG_TYPE_LOCAL_CLAUDE_CLI,
    CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI,
    CONFIG_TYPE_LOCAL_CODEX_CLI,
    CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI,
    CONFIG_TYPE_OPENAI_COMPLETION_API,
    CONFIG_TYPE_OPENAI_DEV_API,
    CONFIG_TYPE_OPENAI_IMAGE_API,
    CONFIG_TYPE_SD_WEBUI_API,
    DEFAULT_LOCAL_IMAGE_BASE_URL,
    DEFAULT_LOCAL_LLM_BASE_URL,
    DEFAULT_REMOTE_BASE_URL,
    DEV_CONFIG_TYPES,
    IMAGE_CONFIG_TYPES,
    COMPLETION_CONFIG_TYPES,
    LOCAL_CLI_TYPES,
    API_CONFIG_TYPES,
    CUSTOM_CONFIG_TYPES,
    CODEX_FILE_CONFIG_TYPES,
    IMAGE_SOURCES,
    LLMConfig,
    LLM_SOURCES,
    ImageConfig,
    SCHEMA_VERSION,
    SUPPORTED_ADAPTERS,
    TYPE_LABELS,
    category_from_dict,
    category_to_dict,
    default_entries,
    entry_model,
    extra_text,
    image_config_from_entry,
    llm_config_from_entry,
    new_entry,
    safe_id,
)
from core.paths import SETTINGS_DIR


AI_CONFIG_PATH = SETTINGS_DIR / "ai_config.json"


def _config_path(path: Path | None = None) -> Path:
    return path or AI_CONFIG_PATH


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _llm_from_dict(raw: Any, *, adapter: str) -> LLMConfig:
    data = raw if isinstance(raw, dict) else {}
    source = str(data.get("source") or ("cli" if adapter in {"codex", "claude"} else "api"))
    if source not in LLM_SOURCES:
        source = "api"
    return LLMConfig(
        source=source,
        provider=str(data.get("provider") or "openai"),
        base_url=str(data.get("base_url") or ""),
        api_key=str(data.get("api_key") or ""),
        cli_path=str(data.get("cli_path") or (adapter if source == "cli" else "")),
        model=str(data.get("model") or data.get("default_model") or "gpt-5.5"),
        temperature=_coerce_float(data.get("temperature"), 0.7),
        timeout=_coerce_int(data.get("timeout"), 300),
        reasoning_effort=data.get("reasoning_effort"),
    )


def _image_from_dict(raw: Any, *, adapter: str) -> ImageConfig:
    data = raw if isinstance(raw, dict) else {}
    source = str(data.get("source") or ("cli_builtin" if adapter == "codex" and data.get("enabled") else "api"))
    if source not in IMAGE_SOURCES:
        source = "api"
    return ImageConfig(
        enabled=bool(data.get("enabled", False)),
        source=source,
        provider=str(data.get("provider") or "openai"),
        base_url=str(data.get("base_url") or ""),
        api_key=str(data.get("api_key") or ""),
        cli_path=str(data.get("cli_path") or ("codex" if source == "cli_builtin" else "")),
        model=str(data.get("model") or data.get("default_model") or "gpt-image-2"),
    )


def profile_from_dict(raw: dict[str, Any], *, fallback_id: str = "profile") -> AIProfile:
    adapter = str(raw.get("adapter") or raw.get("provider") or "openai").strip().lower()
    if adapter not in SUPPORTED_ADAPTERS:
        adapter = "openai"
    profile_id = safe_id(str(raw.get("id") or raw.get("name") or fallback_id), fallback_id)
    name = str(raw.get("name") or profile_id)
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    return AIProfile(
        profile_id,
        name,
        adapter,
        _llm_from_dict(raw.get("llm"), adapter=adapter),
        _image_from_dict(raw.get("image"), adapter=adapter),
        dict(metadata),
    )


def profile_to_dict(profile: AIProfile) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(profile)


def create_default_config() -> AIConfig:
    return AIConfig(
        dev=APICategory(CATEGORY_DEV, default_entries(CATEGORY_DEV), "default"),
        image=APICategory(CATEGORY_IMAGE, default_entries(CATEGORY_IMAGE), ""),
        completion=APICategory(CATEGORY_COMPLETION, default_entries(CATEGORY_COMPLETION), "completion_openai_api"),
    )


def _legacy_profiles(data: dict[str, Any] | None) -> tuple[list[AIProfile], str]:
    defaults = create_default_config().profiles
    if not isinstance(data, dict):
        return defaults, "default"
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raw_profiles = [profile_to_dict(profile) for profile in defaults]
    profiles = [
        profile_from_dict(raw, fallback_id=f"profile_{index}")
        for index, raw in enumerate(raw_profiles, 1)
        if isinstance(raw, dict)
    ] or defaults
    active = str(data.get("active_profile_id") or data.get("active_profile") or profiles[0].id)
    if active not in {profile.id for profile in profiles}:
        active = profiles[0].id
    return profiles, active


def _dev_entry_from_profile(profile: AIProfile) -> APIEntry:
    extra = {"model": profile.llm.model}
    if profile.llm.provider != "openai":
        extra["provider"] = profile.llm.provider
    if profile.adapter == "codex":
        return new_entry(profile.id, profile.name, CONFIG_TYPE_LOCAL_CODEX_CLI)
    if profile.adapter == "claude":
        return new_entry(profile.id, profile.name, CONFIG_TYPE_LOCAL_CLAUDE_CLI)
    config_type = CONFIG_TYPE_CUSTOM_DEV_API if profile.adapter == "local" else CONFIG_TYPE_OPENAI_DEV_API
    return new_entry(profile.id, profile.name, config_type, api_url=profile.llm.base_url, api_key=profile.llm.api_key, extra_json=extra_text(extra))


def _completion_entry_from_profile(profile: AIProfile) -> APIEntry:
    entry_id = f"completion_{profile.id}"
    if profile.adapter == "codex":
        return new_entry(entry_id, profile.name, CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI)
    if profile.adapter == "claude":
        return new_entry(entry_id, profile.name, CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI)
    config_type = CONFIG_TYPE_CUSTOM_COMPLETION_API if profile.adapter == "local" else CONFIG_TYPE_OPENAI_COMPLETION_API
    return new_entry(entry_id, profile.name, config_type, api_url=profile.llm.base_url, api_key=profile.llm.api_key, extra_json=extra_text({"model": profile.llm.model}))


def _image_entry_from_profile(profile: AIProfile) -> APIEntry | None:
    if not profile.image.enabled:
        return None
    entry_id = f"image_{profile.id}"
    if profile.image.source == "cli_builtin":
        return new_entry(entry_id, profile.name, CONFIG_TYPE_CODEX_CLI_IMAGE)
    if profile.image.source == "api":
        config_type = CONFIG_TYPE_SD_WEBUI_API if "7860" in profile.image.base_url else CONFIG_TYPE_OPENAI_IMAGE_API
        return new_entry(entry_id, profile.name, config_type, api_url=profile.image.base_url, api_key=profile.image.api_key, extra_json=extra_text({"model": profile.image.model}))
    return None


def _categories_from_profiles(profiles: list[AIProfile], active_profile_id: str) -> tuple[APICategory, APICategory, APICategory]:
    dev_entries = [_dev_entry_from_profile(profile) for profile in profiles]
    image_entries = [entry for profile in profiles if (entry := _image_entry_from_profile(profile))]
    completion_entries = [_completion_entry_from_profile(profile) for profile in profiles]
    active = active_profile_id if active_profile_id in {entry.id for entry in dev_entries} else dev_entries[0].id
    image_active = f"image_{active}" if f"image_{active}" in {entry.id for entry in image_entries} else ""
    completion_active = f"completion_{active}" if f"completion_{active}" in {entry.id for entry in completion_entries} else ""
    return (
        APICategory(CATEGORY_DEV, dev_entries, active),
        APICategory(CATEGORY_IMAGE, image_entries, image_active),
        APICategory(CATEGORY_COMPLETION, completion_entries, completion_active),
    )


def config_from_legacy_profiles(profiles: list[AIProfile], active_profile_id: str) -> AIConfig:
    dev, image, completion = _categories_from_profiles(profiles, active_profile_id)
    return AIConfig(dev=dev, image=image, completion=completion)


def _normalize_config(data: dict[str, Any] | None) -> AIConfig:
    if isinstance(data, dict) and int(data.get("schema_version") or 0) >= 3:
        return AIConfig(
            dev=category_from_dict(data.get(CATEGORY_DEV), CATEGORY_DEV),
            image=category_from_dict(data.get(CATEGORY_IMAGE), CATEGORY_IMAGE),
            completion=category_from_dict(data.get(CATEGORY_COMPLETION), CATEGORY_COMPLETION),
        )
    profiles, active = _legacy_profiles(data)
    return config_from_legacy_profiles(profiles, active)


def config_to_dict(config: AIConfig) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        CATEGORY_DEV: category_to_dict(config.dev),
        CATEGORY_IMAGE: category_to_dict(config.image),
        CATEGORY_COMPLETION: category_to_dict(config.completion),
    }


def load_ai_config(*, path: Path | None = None, create: bool = False) -> AIConfig:
    target = _config_path(path)
    if not target.exists():
        config = create_default_config()
        if create:
            save_ai_config(config, path=target)
        return config
    try:
        data = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        data = None
    config = _normalize_config(data)
    if isinstance(data, dict) and int(data.get("schema_version") or 0) < SCHEMA_VERSION:
        save_ai_config(config, path=target)
    return config


def save_ai_config(config: AIConfig | dict[str, Any], *, path: Path | None = None) -> Path:
    target = _config_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = config if isinstance(config, AIConfig) else _normalize_config(config)
    normalized.active_profile_id = normalized.dev.active_entry_id
    target.write_text(json.dumps(config_to_dict(normalized), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def ensure_ai_config_file(*, path: Path | None = None) -> Path:
    target = _config_path(path)
    if not target.exists():
        save_ai_config(create_default_config(), path=target)
    else:
        load_ai_config(path=target)
    return target


def get_active_entry(category_id: str, *, path: Path | None = None) -> APIEntry | None:
    return load_ai_config(path=path).category(category_id).active_entry


def get_active_dev_entry(*, path: Path | None = None) -> APIEntry | None:
    return get_active_entry(CATEGORY_DEV, path=path)


def get_active_image_entry(*, path: Path | None = None) -> APIEntry | None:
    return get_active_entry(CATEGORY_IMAGE, path=path)


def get_active_completion_entry(*, path: Path | None = None) -> APIEntry | None:
    return get_active_entry(CATEGORY_COMPLETION, path=path)


def get_active_profile(*, path: Path | None = None) -> AIProfile:
    return load_ai_config(path=path).active_profile


def set_active_profile(profile_id: str, *, path: Path | None = None) -> None:
    target = _config_path(path)
    config = load_ai_config(path=target, create=True)
    if not config.dev.get_entry(profile_id):
        raise ValueError(f"AI profile does not exist: {profile_id}")
    config.dev.active_entry_id = profile_id
    config.active_profile_id = profile_id
    save_ai_config(config, path=target)


def migrate_from_legacy(*, path: Path | None = None) -> AIConfig:
    from tools.config.migrate_ai_config import migrate_from_legacy as _migrate

    return _migrate(target_path=_config_path(path))


def mask_secret(value: str | None) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:3]}***{text[-4:]}"
