"""Adapter registry."""

from __future__ import annotations

from core.adapters.base import ModelAdapter
from core.adapters.claude_code_model_adapter import ClaudeCodeModelAdapter
from core.adapters.codex_adapter import CodexAdapter
from core.adapters.local_adapter import LocalAdapter
from core.adapters.openai_adapter import OpenAIAdapter

SUPPORTED_ADAPTERS: dict[str, str] = {
    "none":   "禁用 AI",
    "codex":  "Codex CLI",
    "claude": "Claude Code CLI",
    "openai": "OpenAI API",
    "local":  "Local（占位）",
}


def get_adapter(name: str, profile=None) -> ModelAdapter:
    if name == "none":
        adapter: ModelAdapter = LocalAdapter()
    elif name == "codex":
        adapter = CodexAdapter()
    elif name == "claude":
        adapter = ClaudeCodeModelAdapter()
    elif name == "openai":
        adapter = OpenAIAdapter()
    elif name == "local":
        adapter = LocalAdapter()
    else:
        raise ValueError(f"unknown adapter: {name}")
    if profile is not None:
        adapter.configure(profile=profile)
    return adapter
