"""Codex CLI execution wrapper."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from adapters.base import ModelResult, ModelTask
from codex.file_guard import validate_allowed_outputs
from tools.process_utils import child_process_env, hidden_subprocess_kwargs


def _codex_command() -> str:
    command = shutil.which("codex") or shutil.which("codex.cmd")
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
            "workspace-write",
            "--skip-git-repo-check",
            "-",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=task.timeout_seconds,
        **hidden_subprocess_kwargs(stdin=None, env=child_process_env()),
    )
    errors = []
    if result.returncode != 0:
        errors.append(result.stderr.strip() or f"codex exited {result.returncode}")
    return ModelResult(
        task_id=task.task_id,
        status="success" if not errors else "failed",
        text=result.stdout,
        errors=errors,
    )
