"""Codex task prompt builder."""

from __future__ import annotations

from core.adapters.base import ModelTask


def build_file_generation_task(
    *,
    task_id: str,
    goal: str,
    input_files: list[str],
    output_files: list[str],
    allowed_write_paths: list[str],
) -> ModelTask:
    prompt = "\n".join([
        goal,
        "",
        "Input files:",
        *[f"- {item}" for item in input_files],
        "",
        "Output files:",
        *[f"- {item}" for item in output_files],
        "",
        "Write only declared output files. Preserve existing unrelated files.",
    ])
    return ModelTask(
        task_id=task_id,
        prompt=prompt,
        input_files=input_files,
        output_files=output_files,
        allowed_write_paths=allowed_write_paths,
    )
