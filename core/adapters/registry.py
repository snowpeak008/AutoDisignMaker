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


def get_adapter(name: str) -> ModelAdapter:
    if name == "none":
        return LocalAdapter()
    if name == "codex":
        return CodexAdapter()
    if name == "claude":
        return ClaudeCodeModelAdapter()
    if name == "openai":
        return OpenAIAdapter()
    if name == "local":
        return LocalAdapter()
    raise ValueError(f"unknown adapter: {name}")
