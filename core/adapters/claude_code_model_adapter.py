"""Claude Code CLI adapter for the pipeline model adapter interface."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.adapters.base import ModelAdapter, ModelResult, ModelTask
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs


def _claude_command() -> str:
    command = shutil.which("claude")
    if not command:
        raise FileNotFoundError("claude CLI was not found on PATH.")
    return command


class ClaudeCodeModelAdapter(ModelAdapter):
    """Pipeline adapter that executes tasks via the Claude Code CLI."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]

    def generate(self, task: ModelTask) -> ModelResult:
        try:
            command = _claude_command()
        except FileNotFoundError as exc:
            return ModelResult(task_id=task.task_id, status="failed", errors=[str(exc)])

        result = subprocess.run(
            [command, "--print", "-p", task.prompt],
            capture_output=True,
            text=True,
            cwd=str(self.root),
            timeout=600,
            **hidden_subprocess_kwargs(env=child_process_env()),
        )
        if result.returncode != 0:
            return ModelResult(
                task_id=task.task_id,
                status="failed",
                text=result.stdout,
                errors=[result.stderr or f"claude exited {result.returncode}"],
            )
        return ModelResult(task_id=task.task_id, status="success", text=result.stdout)
