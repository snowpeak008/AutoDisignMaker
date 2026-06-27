"""Unified AI configuration profiles."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.paths import SETTINGS_DIR


AI_CONFIG_PATH = SETTINGS_DIR / "ai_config.json"
SCHEMA_VERSION = 2

DEFAULT_REMOTE_BASE_URL = "https://vip.auto-code.net/v1"
DEFAULT_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LOCAL_IMAGE_BASE_URL = "http://127.0.0.1:7860/sdapi/v1"

SUPPORTED_ADAPTERS = {"openai", "codex", "claude", "local", "none"}
LLM_SOURCES = {"api", "cli", "none"}
IMAGE_SOURCES = {"api", "cli_builtin", "none"}


@dataclass
class LLMConfig:
    source: str = "api"
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    cli_path: str = ""
    model: str = "gpt-5.5"
    temperature: float = 0.7
    timeout: int = 300
    reasoning_effort: str | None = None


@dataclass
class ImageConfig:
    enabled: bool = False
    source: str = "api"
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    cli_path: str = ""
    model: str = "gpt-image-2"


@dataclass
class AIProfile:
    id: str
    name: str
    adapter: str
    llm: LLMConfig = field(default_factory=LLMConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIConfig:
    schema_version: int = SCHEMA_VERSION
    active_profile_id: str = "default"
    profiles: list[AIProfile] = field(default_factory=list)

    def get_profile(self, profile_id: str) -> AIProfile | None:
        for profile in self.profiles:
            if profile.id == profile_id:
                return profile
        return None

    @property
    def active_profile(self) -> AIProfile:
        return self.get_profile(self.active_profile_id) or self.profiles[0]


def _config_path(path: Path | None = None) -> Path:
    return path or AI_CONFIG_PATH


def _safe_id(value: str, fallback: str = "profile") -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value).strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or fallback


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
        cli_path=str(data.get("cli_path") or adapter if source == "cli" else data.get("cli_path") or ""),
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
    profile_id = _safe_id(str(raw.get("id") or raw.get("name") or fallback_id), fallback_id)
    name = str(raw.get("name") or profile_id)
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    return AIProfile(
        id=profile_id,
        name=name,
        adapter=adapter,
        llm=_llm_from_dict(raw.get("llm"), adapter=adapter),
        image=_image_from_dict(raw.get("image"), adapter=adapter),
        metadata=dict(metadata),
    )


def profile_to_dict(profile: AIProfile) -> dict[str, Any]:
    return asdict(profile)


def create_default_config() -> AIConfig:
    return AIConfig(
        profiles=[
            AIProfile(
                id="default",
                name="默认 OpenAI",
                adapter="openai",
                llm=LLMConfig(
                    source="api",
                    provider="openai",
                    base_url=DEFAULT_REMOTE_BASE_URL,
                    api_key="",
                    model="gpt-5.5",
                ),
                image=ImageConfig(
                    enabled=False,
                    source="api",
                    provider="openai",
                    base_url=DEFAULT_REMOTE_BASE_URL,
                    api_key="",
                    model="gpt-image-2",
                ),
            ),
            AIProfile(
                id="codex_cli",
                name="Codex CLI",
                adapter="codex",
                llm=LLMConfig(source="cli", cli_path="codex", model="gpt-5.5"),
                image=ImageConfig(enabled=True, source="cli_builtin", cli_path="codex"),
            ),
            AIProfile(
                id="claude_cli",
                name="Claude Code CLI",
                adapter="claude",
                llm=LLMConfig(source="cli", cli_path="claude", model="claude-sonnet-4-6"),
                image=ImageConfig(enabled=False, source="none"),
            ),
            AIProfile(
                id="local_ollama",
                name="本地 Ollama",
                adapter="openai",
                llm=LLMConfig(
                    source="api",
                    provider="openai",
                    base_url=DEFAULT_LOCAL_LLM_BASE_URL,
                    api_key="local",
                    model="qwen2.5:14b",
                ),
                image=ImageConfig(
                    enabled=True,
                    source="api",
                    provider="openai",
                    base_url=DEFAULT_LOCAL_IMAGE_BASE_URL,
                    api_key="local",
                    model="sd-webui",
                ),
            ),
        ]
    )


def _normalize_config(data: dict[str, Any] | None) -> AIConfig:
    defaults = create_default_config()
    if not isinstance(data, dict):
        return defaults
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raw_profiles = [profile_to_dict(profile) for profile in defaults.profiles]
    profiles: list[AIProfile] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_profiles, 1):
        if not isinstance(raw, dict):
            continue
        profile = profile_from_dict(raw, fallback_id=f"profile_{index}")
        if profile.id in seen:
            suffix = 2
            base_id = profile.id
            while f"{base_id}_{suffix}" in seen:
                suffix += 1
            profile.id = f"{base_id}_{suffix}"
        seen.add(profile.id)
        profiles.append(profile)
    if not profiles:
        profiles = defaults.profiles
    active = str(data.get("active_profile_id") or data.get("active_profile") or profiles[0].id)
    if active not in {profile.id for profile in profiles}:
        active = profiles[0].id
    return AIConfig(
        schema_version=SCHEMA_VERSION,
        active_profile_id=active,
        profiles=profiles,
    )


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
    return _normalize_config(data)


def save_ai_config(config: AIConfig | dict[str, Any], *, path: Path | None = None) -> Path:
    target = _config_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = config if isinstance(config, AIConfig) else _normalize_config(config)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "active_profile_id": normalized.active_profile_id,
        "profiles": [profile_to_dict(profile) for profile in normalized.profiles],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def ensure_ai_config_file(*, path: Path | None = None) -> Path:
    target = _config_path(path)
    if not target.exists():
        save_ai_config(create_default_config(), path=target)
    return target


def get_active_profile(*, path: Path | None = None) -> AIProfile:
    config = load_ai_config(path=path)
    return config.active_profile


def set_active_profile(profile_id: str, *, path: Path | None = None) -> None:
    target = _config_path(path)
    config = load_ai_config(path=target, create=True)
    if not config.get_profile(profile_id):
        raise ValueError(f"AI profile does not exist: {profile_id}")
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
