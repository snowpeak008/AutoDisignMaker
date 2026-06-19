"""Codex result parsing hooks."""

from __future__ import annotations


def summarize_result(text: str, limit: int = 2000) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "\n..."
