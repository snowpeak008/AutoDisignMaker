"""Adapter registry."""

from __future__ import annotations

from core.adapters.base import ModelAdapter
from core.adapters.codex_adapter import CodexAdapter
from core.adapters.local_adapter import LocalAdapter
from core.adapters.openai_adapter import OpenAIAdapter


def get_adapter(name: str) -> ModelAdapter:
    if name == "codex":
        return CodexAdapter()
    if name == "openai":
        return OpenAIAdapter()
    if name == "local":
        return LocalAdapter()
    raise ValueError(f"unknown adapter: {name}")
