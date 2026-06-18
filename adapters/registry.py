"""Adapter registry."""

from __future__ import annotations

from adapters.base import ModelAdapter
from adapters.codex_adapter import CodexAdapter
from adapters.local_adapter import LocalAdapter
from adapters.openai_adapter import OpenAIAdapter


def get_adapter(name: str) -> ModelAdapter:
    if name == "codex":
        return CodexAdapter()
    if name == "openai":
        return OpenAIAdapter()
    if name == "local":
        return LocalAdapter()
    raise ValueError(f"unknown adapter: {name}")
