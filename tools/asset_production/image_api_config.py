#!/usr/bin/env python3
"""Image API provider configuration helpers.

The project may use several image providers, but only the active provider is
called by tests. Secrets are read from api_config.toml or environment variables
and are never included in reports without masking.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from core.config.loader import _load_config_document, normalize_openai_base_url


@dataclass(frozen=True)
class ImageApiSettings:
    name: str
    provider: str
    mode: str
    api_key: str
    base_url: str
    image_model: str
    response_model: str | None = None
    endpoint: str | None = None
    enabled: bool = True

    @property
    def masked_api_key(self) -> str:
        return mask_secret(self.api_key)


def mask_secret(value: str | None) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:3]}...{text[-4:]}"


def _providers_root() -> dict[str, Any]:
    document = _load_config_document()
    providers = document.get("providers")
    return providers if isinstance(providers, dict) else document


def _legacy_image_config_as_relay(providers: dict[str, Any]) -> dict[str, Any]:
    inherit_from = "image2"
    image2 = providers.get("image2")
    if not isinstance(image2, dict):
        inherit_from = "image"
        image2 = providers.get("image")
    if not isinstance(image2, dict):
        inherit_from = "llm"
        image2 = providers.get("llm")
    if not isinstance(image2, dict):
        return {}
    if inherit_from == "llm":
        image_model = (
            image2.get("image_model")
            or image2.get("default_image_model")
            or "gpt-image-2"
        )
        response_model = image2.get("response_model") or image2.get("model") or "gpt-5.5"
    else:
        image_model = (
            image2.get("image_model")
            or image2.get("default_model")
            or image2.get("model")
            or "gpt-image-2"
        )
        response_model = image2.get("response_model") or "gpt-5.5"
    return {
        "active": "relay",
        "relay": {
            "provider": "openai_responses",
            "mode": "responses_image_tool",
            "inherit_from": inherit_from,
            "endpoint": "responses",
            "image_model": image_model,
            "response_model": response_model,
            "enabled": True,
        },
    }


def load_image_api_configs() -> dict[str, Any]:
    providers = _providers_root()
    configured = providers.get("image_apis")
    if isinstance(configured, dict):
        return configured
    return _legacy_image_config_as_relay(providers)


def load_image_api_settings(provider_name: str | None = None) -> ImageApiSettings:
    providers = _providers_root()
    image_apis = load_image_api_configs()
    active = str(provider_name or image_apis.get("active") or "relay")
    provider_cfg = image_apis.get(active)
    if not isinstance(provider_cfg, dict):
        raise RuntimeError(f"Image API provider is not configured: {active}")

    cfg = dict(provider_cfg)
    inherit_name = cfg.get("inherit_from")
    if inherit_name:
        merged: dict[str, Any] = {}
        llm_cfg = providers.get("llm")
        if inherit_name != "llm" and isinstance(llm_cfg, dict):
            merged.update(llm_cfg)
        inherited = providers.get(str(inherit_name))
        if isinstance(inherited, dict):
            merged.update(inherited)
        merged.update(cfg)
        cfg = merged

    env_prefix = f"IMAGE_{active.upper()}"
    api_key_env = str(cfg.get("api_key_env") or f"{env_prefix}_API_KEY")
    api_key = str(cfg.get("api_key") or os.getenv(api_key_env) or "")
    base_url = str(cfg.get("base_url") or os.getenv(f"{env_prefix}_BASE_URL") or "")
    image_model = str(
        cfg.get("image_model")
        or cfg.get("default_model")
        or os.getenv(f"{env_prefix}_MODEL")
        or ""
    )
    response_model = cfg.get("response_model") or os.getenv(f"{env_prefix}_RESPONSE_MODEL")
    provider_type = str(cfg.get("provider") or "openai_responses")
    mode = str(cfg.get("mode") or "responses_image_tool")
    endpoint = str(cfg.get("endpoint") or ("responses" if mode == "responses_image_tool" else "images/generations"))
    enabled = bool(cfg.get("enabled", True))

    if not api_key:
        raise RuntimeError(f"Missing image API key for provider {active}. Expected api_key or {api_key_env}.")
    if not base_url:
        raise RuntimeError(f"Missing image API base_url for provider {active}.")
    if not image_model:
        raise RuntimeError(f"Missing image model for provider {active}.")

    if provider_type.startswith("openai") or mode.startswith("responses") or mode.startswith("images"):
        base_url = normalize_openai_base_url(base_url)
    else:
        base_url = base_url.rstrip("/")

    return ImageApiSettings(
        name=active,
        provider=provider_type,
        mode=mode,
        api_key=api_key,
        base_url=base_url,
        image_model=image_model,
        response_model=str(response_model) if response_model else None,
        endpoint=endpoint,
        enabled=enabled,
    )
