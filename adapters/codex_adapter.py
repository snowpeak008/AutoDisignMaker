"""Codex CLI adapter."""

from __future__ import annotations

from pathlib import Path

from adapters.base import ModelAdapter, ModelResult, ModelTask
from codex.executor import run_codex_exec


class CodexAdapter(ModelAdapter):
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parent.parent

    def generate(self, task: ModelTask) -> ModelResult:
        return run_codex_exec(task, cwd=self.root)
