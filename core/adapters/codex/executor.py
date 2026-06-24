"""Codex CLI execution wrapper."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from core.adapters.base import ModelResult, ModelTask
from core.adapters.codex.file_guard import validate_allowed_outputs
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs


def _codex_command() -> str:
    command = (
        shutil.which("codex.cmd") or shutil.which("codex.exe") or shutil.which("codex")
    )
    if not command:
        raise FileNotFoundError("codex CLI was not found on PATH.")
    return command


def run_codex_exec(task: ModelTask, cwd: Path) -> ModelResult:
    errors = validate_allowed_outputs(task.output_files, task.allowed_write_paths)
    if errors:
        return ModelResult(task_id=task.task_id, status="failed", errors=errors)

    prompt = task.prompt
    result = subprocess.run(
        [
            _codex_command(),
            "exec",
            "--cd",
            str(cwd),
            "--sandbox",
            task.sandbox,
            "--skip-git-repo-check",
            "-",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=task.timeout_seconds,
        **hidden_subprocess_kwargs(env=child_process_env()),
    )
    if result.returncode != 0:
        return ModelResult(
            task_id=task.task_id,
            status="failed",
            text=result.stdout,
            errors=[result.stderr or f"codex exited {result.returncode}"],
        )
    return ModelResult(task_id=task.task_id, status="success", text=result.stdout)
