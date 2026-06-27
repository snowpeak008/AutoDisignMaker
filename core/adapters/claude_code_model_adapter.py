"""Claude Code CLI adapter for the pipeline model adapter interface."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.adapters.base import ModelAdapter, ModelResult, ModelTask
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs


def _claude_command(cli_path: str = "claude") -> str:
    command = shutil.which(cli_path)
    if not command and cli_path != "claude":
        custom_path = Path(cli_path).expanduser()
        if custom_path.exists():
            command = str(custom_path)
    if not command:
        raise FileNotFoundError(f"{cli_path} CLI was not found on PATH.")
    return command


class ClaudeCodeModelAdapter(ModelAdapter):
    """Pipeline adapter that executes tasks via the Claude Code CLI."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]
        self.cli_path = "claude"
        self.model = "claude-sonnet-4-6"

    def configure(self, **kwargs) -> "ClaudeCodeModelAdapter":
        profile = kwargs.get("profile")
        llm = getattr(profile, "llm", None) if profile is not None else None
        self.cli_path = str(kwargs.get("cli_path") or getattr(llm, "cli_path", "") or "claude")
        self.model = str(kwargs.get("model") or getattr(llm, "model", "") or "claude-sonnet-4-6")
        return self

    def generate(self, task: ModelTask) -> ModelResult:
        try:
            command = (
                _claude_command()
                if self.cli_path == "claude"
                else _claude_command(self.cli_path)
            )
        except FileNotFoundError as exc:
            return ModelResult(task_id=task.task_id, status="failed", errors=[str(exc)])

        result = subprocess.run(
            [command, "--print", "-p", task.prompt],
            capture_output=True,
            text=True,
            cwd=str(self.root),
            timeout=task.timeout_seconds,
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
