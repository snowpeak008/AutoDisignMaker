"""Full configuration loader — replaces the placeholder from sub-plan 03."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.paths import APP_CONFIG_FILE, PROJECT_SETTINGS_FILE, SETTINGS_DIR

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

try:
    import toml  # type: ignore
except ModuleNotFoundError:
    toml = None


DEFAULT_APP_CONFIG: dict[str, Any] = {
    "project": {"name": "AutoDesignMaker", "version": "1.0.0"},
    "model": {
        "provider": "openai",
        "base_url": "https://vip.auto-code.net/v1",
        "model": "gpt-5.5",
        "max_tokens": 350000,
        "temperature": 0.7,
        "timeout": 300,
    },
    "plugins": {"manifest_path": "pipeline/_registry.json", "auto_discover": True},
}

DEFAULT_PROJECT_SETTINGS: dict[str, Any] = {
    "unity_project_path": "",
    "editor_path": "",
    "development_path": "",
    "last_save_id": "",
    "last_active_stage": "",
    "default_export_format": "markdown",
    "recent_projects": [],
}


def _deep_merge(defaults: dict, override: dict) -> dict:
    merged = deepcopy(defaults)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        if tomllib is not None:
            return tomllib.loads(content)
        if toml is not None:
            return toml.loads(content)
    except Exception:
        pass
    return {}


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}


class ConfigLoader:
    def __init__(
        self,
        app_config_file: Path = APP_CONFIG_FILE,
        project_settings_file: Path = PROJECT_SETTINGS_FILE,
    ) -> None:
        self.app_config_file = app_config_file
        self.project_settings_file = project_settings_file
        self._app_config: dict[str, Any] = {}
        self._project_settings: dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        self._app_config = _deep_merge(DEFAULT_APP_CONFIG, _read_toml(self.app_config_file))
        self._project_settings = _deep_merge(DEFAULT_PROJECT_SETTINGS, _read_json_file(self.project_settings_file))
        self._loaded = True

    @property
    def app_config(self) -> dict[str, Any]:
        if not self._loaded:
            self.load()
        return self._app_config

    @property
    def project_settings(self) -> dict[str, Any]:
        if not self._loaded:
            self.load()
        return self._project_settings

    def get(self, key_path: str, default: Any = None) -> Any:
        current: Any = self.app_config
        for key in key_path.split("."):
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def get_project_setting(self, key: str, default: Any = None) -> Any:
        return self.project_settings.get(key, default)

    def set_project_setting(self, key: str, value: Any) -> None:
        self.project_settings[key] = value
        self.save_project_settings()

    def save_project_settings(self) -> None:
        self.project_settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.project_settings_file.write_text(
            json.dumps(self.project_settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )


_config_loader = ConfigLoader()


def load_config() -> ConfigLoader:
    if not _config_loader._loaded:
        _config_loader.load()
    return _config_loader


def get_config(key_path: str, default: Any = None) -> Any:
    return load_config().get(key_path, default)


# ── API config (from tools/config_loader.py) ─────────────────────────────────

_API_CONFIG_PATH = SETTINGS_DIR / "api_config.toml"


def normalize_openai_base_url(base_url: str) -> str:
    base = str(base_url).strip().rstrip("/")
    return base if not base or base.endswith("/v1") else f"{base}/v1"


@dataclass
class OpenAICompatibleCaller:
    model: str
    base_url: str
    api_key: str
    temperature: float = 0.0
    reasoning_effort: str | None = None

    def invoke(self, messages: "list[dict] | str") -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required.") from exc
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        model_name = self.model.split("/", 1)[-1]
        kwargs: dict = {"model": model_name, "messages": messages, "temperature": self.temperature}
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def __call__(self, messages: "list[dict] | str") -> str:
        return self.invoke(messages)


def get_api_config(provider_name: str = "llm") -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if _API_CONFIG_PATH.exists():
        cfg = _read_toml(_API_CONFIG_PATH).get(provider_name, {})

    env_prefix = provider_name.upper()
    api_key = cfg.get("api_key") or os.getenv(f"{env_prefix}_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = cfg.get("base_url") or os.getenv(f"{env_prefix}_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://vip.auto-code.net/v1")
    model = cfg.get("model") or cfg.get("default_model") or os.getenv(f"{env_prefix}_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5.5")
    provider = cfg.get("provider", "openai")
    if provider == "openai":
        base_url = normalize_openai_base_url(base_url)
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": f"{provider}/{model}",
        "default_model": model,
        "provider": provider,
        "reasoning_effort": cfg.get("reasoning_effort"),
    }


def build_llm(cfg: dict[str, Any], temperature: float = 0.0) -> OpenAICompatibleCaller:
    return OpenAICompatibleCaller(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=temperature,
        reasoning_effort=cfg.get("reasoning_effort"),
    )
