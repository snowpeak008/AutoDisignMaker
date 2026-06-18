#!/usr/bin/env python3
"""Project API configuration loader.

This module keeps the old public helpers but returns a local OpenAI-compatible
caller instead of constructing any external orchestration runtime object.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "api_config.md"


def normalize_openai_base_url(base_url: str) -> str:
    base = str(base_url).strip().rstrip("/")
    if not base:
        return base
    return base if base.endswith("/v1") else f"{base}/v1"


def openai_endpoint(base_url: str, endpoint: str) -> str:
    return f"{normalize_openai_base_url(base_url)}/{endpoint.lstrip('/')}"


def _load_config_document() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    raw = CONFIG_PATH.read_text(encoding="utf-8")
    from tools.md_parser import parse_md_output

    data = parse_md_output(raw, output_name="api_config")
    return data if isinstance(data, dict) else {}


def load_api_config() -> dict[str, Any]:
    data = _load_config_document()
    providers = data.get("providers")
    return providers if isinstance(providers, dict) else data


def get_api_config(provider_name: str) -> dict[str, Any]:
    config = load_api_config()
    provider_cfg = dict(config.get(provider_name, {}) or {})

    env_prefix = provider_name.upper()
    api_key = provider_cfg.get("api_key") or os.getenv(f"{env_prefix}_API_KEY")
    base_url = provider_cfg.get("base_url") or os.getenv(f"{env_prefix}_BASE_URL")
    model = provider_cfg.get("default_model") or os.getenv(f"{env_prefix}_MODEL")

    if not api_key:
        raise RuntimeError(f"Missing API key for provider {provider_name}.")
    if not base_url:
        raise RuntimeError(f"Missing base_url for provider {provider_name}.")
    if not model:
        raise RuntimeError(f"Missing default_model for provider {provider_name}.")

    provider = provider_cfg.get("provider", "openai")
    if provider == "openai":
        base_url = normalize_openai_base_url(base_url)
    else:
        base_url = str(base_url).strip().rstrip("/")
    chat_model = provider_cfg.get("models", {}).get("chat", model)
    return {
        "api_key": api_key,
        "base_url": base_url,
        "default_model": model,
        "models": provider_cfg.get("models", {}),
        "provider": provider,
        "model": f"{provider}/{chat_model}",
        "reasoning_effort": provider_cfg.get("reasoning_effort"),
    }


@dataclass
class OpenAICompatibleCaller:
    model: str
    base_url: str
    api_key: str
    temperature: float = 0.0
    reasoning_effort: str | None = None

    def invoke(self, messages: list[dict[str, str]] | str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for model calls.") from exc

        if isinstance(messages, str):
            payload = [{"role": "user", "content": messages}]
        else:
            payload = messages
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        model_name = self.model.split("/", 1)[-1]
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": payload,
            "temperature": self.temperature,
        }
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def __call__(self, messages: list[dict[str, str]] | str) -> str:
        return self.invoke(messages)


def build_llm(cfg: dict[str, Any], temperature: float = 0.0) -> OpenAICompatibleCaller:
    return OpenAICompatibleCaller(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=temperature,
        reasoning_effort=cfg.get("reasoning_effort"),
    )


def get_project_config() -> dict[str, Any]:
    data = _load_config_document()
    project = data.get("project", {})
    return project if isinstance(project, dict) else {}
