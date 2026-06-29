"""Codex CLI adapter."""

from __future__ import annotations

from pathlib import Path

from core.adapters.base import ModelAdapter, ModelResult, ModelTask
from core.adapters.codex.executor import run_codex_exec


class CodexAdapter(ModelAdapter):
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]
        self.cli_path = "codex"
        self.model = "gpt-5.5"

    def configure(self, **kwargs) -> "CodexAdapter":
        profile = kwargs.get("profile")
        llm = getattr(profile, "llm", None) if profile is not None else None
        self.cli_path = str(kwargs.get("cli_path") or getattr(llm, "cli_path", "") or "codex")
        self.model = str(kwargs.get("model") or getattr(llm, "model", "") or "gpt-5.5")
        return self

    def generate(self, task: ModelTask) -> ModelResult:
        cwd = Path(task.cwd).expanduser() if task.cwd else self.root
        return run_codex_exec(task, cwd=cwd, cli_path=self.cli_path)
