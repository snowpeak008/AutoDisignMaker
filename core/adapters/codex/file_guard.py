"""Declared output path guard for Codex tasks."""

from __future__ import annotations

from pathlib import Path


def validate_allowed_outputs(output_files: list[str], allowed_write_paths: list[str]) -> list[str]:
    if not output_files:
        return []
    if not allowed_write_paths:
        return ["output_files declared but allowed_write_paths is empty"]
    allowed = [Path(item).as_posix().rstrip("/") for item in allowed_write_paths]
    errors: list[str] = []
    for output in output_files:
        normalized = Path(output).as_posix()
        if not any(normalized == item or normalized.startswith(item + "/") for item in allowed):
            errors.append(f"output outside allowed paths: {output}")
    return errors
