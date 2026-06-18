"""Configuration loading for AutoDesignMaker."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.core.paths import APP_CONFIG_FILE, PROJECT_SETTINGS_FILE

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    tomllib = None

try:
    import toml
except ModuleNotFoundError:  # pragma: no cover - optional fallback.
    toml = None


DEFAULT_APP_CONFIG: dict[str, Any] = {
    "project": {
        "name": "AutoDesignMaker",
        "version": "1.0.0",
        "description": "AI-powered game design and development automation tool",
    },
    "paths": {
        "workspace": "workspace",
        "data": "data",
        "design_data": "data/design",
        "ucos": "ucos",
        "memory": "memory",
    },
    "model": {
        "provider": "openai",
        "base_url": "https://vip.auto-code.net/v1",
        "model": "gpt-5.5",
        "max_tokens": 350000,
        "temperature": 0.7,
        "timeout": 300,
    },
    "unity": {
        "project_path": "",
        "editor_path": "",
    },
    "ui": {
        "theme": "clam",
        "font_family": "Microsoft YaHei UI",
        "font_size": 9,
        "window_width": 1560,
        "window_height": 940,
    },
    "dev": {
        "hot_reload": True,
        "debug": True,
        "log_level": "DEBUG",
    },
    "plugins": {
        "manifest_path": "src/plugins/plugin_manifest.json",
        "auto_discover": True,
    },
    "export": {
        "default_format": "markdown",
        "include_metadata": True,
    },
}

DEFAULT_PROJECT_SETTINGS: dict[str, Any] = {
    "unity_project_path": "",
    "editor_path": "",
    "development_path": "",
    "last_save_id": "",
    "last_active_stage": "",
    "default_export_format": "markdown",
    "recent_projects": [],
    "window_state": {
        "maximized": False,
        "x": 100,
        "y": 100,
    },
}


def _deep_merge(defaults: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
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
    if tomllib is not None:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    if toml is not None:
        return toml.loads(path.read_text(encoding="utf-8"))
    raise RuntimeError("TOML config requires Python 3.11+ or the optional 'toml' package.")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


class ConfigLoader:
    """Small config facade with dot-path lookup and project setting persistence."""

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
        self._project_settings = _deep_merge(
            DEFAULT_PROJECT_SETTINGS,
            _read_json(self.project_settings_file),
        )
        self._loaded = True

    def reload(self) -> None:
        self._loaded = False
        self.load()

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
            json.dumps(self.project_settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


_config_loader = ConfigLoader()


def load_config() -> ConfigLoader:
    if not _config_loader._loaded:
        _config_loader.load()
    return _config_loader


def get_config(key_path: str, default: Any = None) -> Any:
    return load_config().get(key_path, default)


def get_project_setting(key: str, default: Any = None) -> Any:
    return load_config().get_project_setting(key, default)


def set_project_setting(key: str, value: Any) -> None:
    load_config().set_project_setting(key, value)

