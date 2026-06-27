"""AI configuration v3 schema primitives."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any


SCHEMA_VERSION = 3
DEFAULT_REMOTE_BASE_URL = "https://vip.auto-code.net/v1"
DEFAULT_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LOCAL_IMAGE_BASE_URL = "http://127.0.0.1:7860/sdapi/v1"

CATEGORY_DEV = "dev"
CATEGORY_IMAGE = "image"
CATEGORY_COMPLETION = "completion"
CATEGORIES = {CATEGORY_DEV, CATEGORY_IMAGE, CATEGORY_COMPLETION}

CONFIG_TYPE_LOCAL_CODEX_CLI = "local_codex_cli"
CONFIG_TYPE_LOCAL_CLAUDE_CLI = "local_claude_cli"
CONFIG_TYPE_OPENAI_DEV_API = "openai_dev_api"
CONFIG_TYPE_CUSTOM_DEV_API = "custom_dev_api"
CONFIG_TYPE_CODEX_CLI_IMAGE = "codex_cli_image"
CONFIG_TYPE_OPENAI_IMAGE_API = "openai_image_api"
CONFIG_TYPE_SD_WEBUI_API = "sd_webui_api"
CONFIG_TYPE_CUSTOM_IMAGE_API = "custom_image_api"
CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI = "local_codex_completion_cli"
CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI = "local_claude_completion_cli"
CONFIG_TYPE_OPENAI_COMPLETION_API = "openai_completion_api"
CONFIG_TYPE_CUSTOM_COMPLETION_API = "custom_completion_api"

DEV_CONFIG_TYPES = (CONFIG_TYPE_LOCAL_CODEX_CLI, CONFIG_TYPE_LOCAL_CLAUDE_CLI, CONFIG_TYPE_OPENAI_DEV_API, CONFIG_TYPE_CUSTOM_DEV_API)
IMAGE_CONFIG_TYPES = (CONFIG_TYPE_CODEX_CLI_IMAGE, CONFIG_TYPE_OPENAI_IMAGE_API, CONFIG_TYPE_SD_WEBUI_API, CONFIG_TYPE_CUSTOM_IMAGE_API)
COMPLETION_CONFIG_TYPES = (CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI, CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI, CONFIG_TYPE_OPENAI_COMPLETION_API, CONFIG_TYPE_CUSTOM_COMPLETION_API)
ALL_CONFIG_TYPES = set(DEV_CONFIG_TYPES + IMAGE_CONFIG_TYPES + COMPLETION_CONFIG_TYPES)
LOCAL_CLI_TYPES = {CONFIG_TYPE_LOCAL_CODEX_CLI, CONFIG_TYPE_LOCAL_CLAUDE_CLI, CONFIG_TYPE_CODEX_CLI_IMAGE, CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI, CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI}
API_CONFIG_TYPES = ALL_CONFIG_TYPES - LOCAL_CLI_TYPES
CUSTOM_CONFIG_TYPES = {CONFIG_TYPE_CUSTOM_DEV_API, CONFIG_TYPE_CUSTOM_IMAGE_API, CONFIG_TYPE_CUSTOM_COMPLETION_API}
CODEX_FILE_CONFIG_TYPES = {CONFIG_TYPE_LOCAL_CODEX_CLI, CONFIG_TYPE_CODEX_CLI_IMAGE, CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI}

TYPE_LABELS = {
    CONFIG_TYPE_LOCAL_CODEX_CLI: "本地 Codex CLI",
    CONFIG_TYPE_LOCAL_CLAUDE_CLI: "本地 Claude Code CLI",
    CONFIG_TYPE_OPENAI_DEV_API: "OpenAI 兼容 API",
    CONFIG_TYPE_CUSTOM_DEV_API: "自定义 API",
    CONFIG_TYPE_CODEX_CLI_IMAGE: "Codex CLI 内置生图",
    CONFIG_TYPE_OPENAI_IMAGE_API: "OpenAI 图片 API",
    CONFIG_TYPE_SD_WEBUI_API: "本地 SD WebUI",
    CONFIG_TYPE_CUSTOM_IMAGE_API: "自定义图片 API",
    CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI: "本地 Codex CLI",
    CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI: "本地 Claude Code CLI",
    CONFIG_TYPE_OPENAI_COMPLETION_API: "OpenAI 补全 API",
    CONFIG_TYPE_CUSTOM_COMPLETION_API: "自定义补全 API",
}
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
class APIEntry:
    id: str
    label: str
    config_type: str
    api_url: str = ""
    api_key: str = ""
    extra_json: str = ""
    codex_toml_path: str = ""
    codex_json_path: str = ""


@dataclass
class APICategory:
    category_id: str
    entries: list[APIEntry] = field(default_factory=list)
    active_entry_id: str = ""

    def get_entry(self, entry_id: str) -> APIEntry | None:
        return next((entry for entry in self.entries if entry.id == entry_id), None)

    @property
    def active_entry(self) -> APIEntry | None:
        return self.get_entry(self.active_entry_id)


@dataclass
class AIConfig:
    schema_version: int = SCHEMA_VERSION
    dev: APICategory = field(default_factory=lambda: APICategory(CATEGORY_DEV))
    image: APICategory = field(default_factory=lambda: APICategory(CATEGORY_IMAGE))
    completion: APICategory = field(default_factory=lambda: APICategory(CATEGORY_COMPLETION))
    active_profile_id: str = ""
    profiles: list[AIProfile] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not self.dev.entries:
            self.dev = APICategory(CATEGORY_DEV, default_entries(CATEGORY_DEV), "default")
        if not self.image.entries:
            image_entries = default_entries(CATEGORY_IMAGE)
            image_active = image_entries[0].id if image_entries else ""
            self.image = APICategory(CATEGORY_IMAGE, image_entries, image_active)
        if not self.completion.entries:
            self.completion = APICategory(CATEGORY_COMPLETION, default_entries(CATEGORY_COMPLETION), "completion_openai_api")
        ensure_category_defaults(self)
        self.active_profile_id = self.dev.active_entry_id
        self.profiles = compat_profiles_from_entries(self)

    def category(self, category_id: str) -> APICategory:
        if category_id == CATEGORY_IMAGE:
            return self.image
        if category_id == CATEGORY_COMPLETION:
            return self.completion
        return self.dev

    def get_profile(self, profile_id: str) -> AIProfile | None:
        return next((profile for profile in self.profiles if profile.id == profile_id), None)

    @property
    def active_profile(self) -> AIProfile:
        return self.get_profile(self.active_profile_id) or self.profiles[0]


def safe_id(value: str, fallback: str = "entry") -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value).strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or fallback


def extra_dict(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def extra_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) and data else ""


def new_entry(entry_id: str, label: str, config_type: str, **kwargs: Any) -> APIEntry:
    return APIEntry(id=entry_id, label=label, config_type=config_type, **kwargs)


def types_for_category(category_id: str) -> tuple[str, ...]:
    if category_id == CATEGORY_IMAGE:
        return IMAGE_CONFIG_TYPES
    if category_id == CATEGORY_COMPLETION:
        return COMPLETION_CONFIG_TYPES
    return DEV_CONFIG_TYPES


def default_entries(category_id: str) -> list[APIEntry]:
    if category_id == CATEGORY_IMAGE:
        return [
            new_entry("codex_cli_image", TYPE_LABELS[CONFIG_TYPE_CODEX_CLI_IMAGE], CONFIG_TYPE_CODEX_CLI_IMAGE),
            new_entry("openai_image_api", TYPE_LABELS[CONFIG_TYPE_OPENAI_IMAGE_API], CONFIG_TYPE_OPENAI_IMAGE_API, api_url=DEFAULT_REMOTE_BASE_URL),
            new_entry("sd_webui_api", TYPE_LABELS[CONFIG_TYPE_SD_WEBUI_API], CONFIG_TYPE_SD_WEBUI_API, api_url=DEFAULT_LOCAL_IMAGE_BASE_URL, api_key="local"),
            new_entry("custom_image_api", TYPE_LABELS[CONFIG_TYPE_CUSTOM_IMAGE_API], CONFIG_TYPE_CUSTOM_IMAGE_API),
        ]
    if category_id == CATEGORY_COMPLETION:
        return [
            new_entry("completion_codex_cli", TYPE_LABELS[CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI], CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI),
            new_entry("completion_claude_cli", TYPE_LABELS[CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI], CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI),
            new_entry("completion_openai_api", TYPE_LABELS[CONFIG_TYPE_OPENAI_COMPLETION_API], CONFIG_TYPE_OPENAI_COMPLETION_API, api_url=DEFAULT_REMOTE_BASE_URL),
            new_entry("completion_custom_api", TYPE_LABELS[CONFIG_TYPE_CUSTOM_COMPLETION_API], CONFIG_TYPE_CUSTOM_COMPLETION_API),
        ]
    return [
        new_entry("codex_cli", TYPE_LABELS[CONFIG_TYPE_LOCAL_CODEX_CLI], CONFIG_TYPE_LOCAL_CODEX_CLI),
        new_entry("claude_cli", TYPE_LABELS[CONFIG_TYPE_LOCAL_CLAUDE_CLI], CONFIG_TYPE_LOCAL_CLAUDE_CLI),
        new_entry("default", "默认 OpenAI", CONFIG_TYPE_OPENAI_DEV_API, api_url=DEFAULT_REMOTE_BASE_URL),
        new_entry("local_ollama", "本地 Ollama", CONFIG_TYPE_CUSTOM_DEV_API, api_url=DEFAULT_LOCAL_LLM_BASE_URL, api_key="local", extra_json='{"model": "qwen2.5:14b"}'),
    ]


def entry_from_dict(raw: Any, fallback_id: str, fallback_type: str) -> APIEntry:
    data = raw if isinstance(raw, dict) else {}
    config_type = str(data.get("config_type") or fallback_type).strip()
    if config_type not in ALL_CONFIG_TYPES:
        config_type = fallback_type
    return APIEntry(
        id=safe_id(str(data.get("id") or fallback_id), fallback_id),
        label=str(data.get("label") or TYPE_LABELS.get(config_type, fallback_id)),
        config_type=config_type,
        api_url=str(data.get("api_url") or data.get("base_url") or ""),
        api_key=str(data.get("api_key") or ""),
        extra_json=extra_text(data.get("extra_json") or data.get("extra") or {}),
        codex_toml_path=str(data.get("codex_toml_path") or ""),
        codex_json_path=str(data.get("codex_json_path") or ""),
    )


def category_from_dict(raw: Any, category_id: str) -> APICategory:
    data = raw if isinstance(raw, dict) else {}
    types = types_for_category(category_id)
    entries = [entry_from_dict(item, f"{category_id}_{index}", types[0]) for index, item in enumerate(data.get("entries") or [], 1)]
    category = APICategory(category_id, entries, str(data.get("active_entry_id") or ""))
    ensure_entries_for_category(category)
    if category.active_entry_id and not category.get_entry(category.active_entry_id):
        category.active_entry_id = category.entries[0].id if category.entries else ""
    return category


def ensure_entries_for_category(category: APICategory) -> None:
    existing_types = {entry.config_type for entry in category.entries}
    existing_ids = {entry.id for entry in category.entries}
    for default in default_entries(category.category_id):
        if default.config_type in existing_types:
            continue
        entry_id = default.id
        suffix = 2
        while entry_id in existing_ids:
            entry_id = f"{default.id}_{suffix}"
            suffix += 1
        default.id = entry_id
        category.entries.append(default)
        existing_ids.add(entry_id)


def ensure_category_defaults(config: AIConfig) -> None:
    config.dev.category_id, config.image.category_id, config.completion.category_id = CATEGORY_DEV, CATEGORY_IMAGE, CATEGORY_COMPLETION
    for category in (config.dev, config.image, config.completion):
        ensure_entries_for_category(category)
    if not config.dev.active_entry_id or not config.dev.get_entry(config.dev.active_entry_id):
        config.dev.active_entry_id = "default" if config.dev.get_entry("default") else config.dev.entries[0].id
    if config.completion.active_entry_id and not config.completion.get_entry(config.completion.active_entry_id):
        config.completion.active_entry_id = config.completion.entries[0].id
    if not config.image.active_entry_id or not config.image.get_entry(
        config.image.active_entry_id
    ):
        config.image.active_entry_id = (
            config.image.entries[0].id if config.image.entries else ""
        )


def category_to_dict(category: APICategory) -> dict[str, Any]:
    return {"category_id": category.category_id, "active_entry_id": category.active_entry_id, "entries": [asdict(entry) for entry in category.entries]}


def entry_model(entry: APIEntry, fallback: str) -> str:
    data = extra_dict(entry.extra_json)
    return str(data.get("model") or data.get("default_model") or fallback)


def entry_provider(entry: APIEntry) -> str:
    return str(extra_dict(entry.extra_json).get("provider") or "openai")


def llm_config_from_entry(entry: APIEntry | None) -> tuple[str, LLMConfig]:
    if entry is None:
        return "none", LLMConfig(source="none")
    if entry.config_type in {CONFIG_TYPE_LOCAL_CODEX_CLI, CONFIG_TYPE_LOCAL_CODEX_COMPLETION_CLI}:
        return "codex", LLMConfig(source="cli", cli_path="codex", model=entry_model(entry, "gpt-5.5"))
    if entry.config_type in {CONFIG_TYPE_LOCAL_CLAUDE_CLI, CONFIG_TYPE_LOCAL_CLAUDE_COMPLETION_CLI}:
        return "claude", LLMConfig(source="cli", cli_path="claude", model=entry_model(entry, "claude-sonnet-4-6"))
    return "openai", LLMConfig(source="api", provider=entry_provider(entry), base_url=entry.api_url, api_key=entry.api_key, model=entry_model(entry, "gpt-5.5"))


def image_config_from_entry(entry: APIEntry | None) -> ImageConfig:
    if entry is None:
        return ImageConfig(enabled=False, source="none")
    if entry.config_type == CONFIG_TYPE_CODEX_CLI_IMAGE:
        return ImageConfig(enabled=True, source="cli_builtin", cli_path="codex")
    model = "sd-webui" if entry.config_type == CONFIG_TYPE_SD_WEBUI_API else "gpt-image-2"
    return ImageConfig(enabled=True, source="api", provider=entry_provider(entry), base_url=entry.api_url, api_key=entry.api_key, model=entry_model(entry, model))


def compat_profiles_from_entries(config: AIConfig) -> list[AIProfile]:
    image_cfg = image_config_from_entry(config.image.active_entry)
    profiles: list[AIProfile] = []
    for entry in config.dev.entries:
        adapter, llm = llm_config_from_entry(entry)
        profiles.append(AIProfile(entry.id, entry.label or TYPE_LABELS.get(entry.config_type, entry.id), adapter, llm, replace(image_cfg)))
    return profiles
