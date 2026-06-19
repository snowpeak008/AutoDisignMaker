#!/usr/bin/env python3
"""LLM output validation helpers."""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Iterable


REJECT_PHRASES = [
    "抱歉",
    "我不能",
    "我无法",
    "对不起",
    "i cannot",
    "i apologize",
    "i'm unable",
    "i am unable",
    "sorry",
    "as an ai",
    "i can't",
    "i cannot fulfill",
]

_FENCE_RE = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<body>.*?)(?:\n)?```", re.DOTALL)


class AgentOutputValidationError(ValueError):
    pass


def _validate_text_content(text: str, output_name: str) -> str:
    if text is None or not str(text).strip():
        raise AgentOutputValidationError(f"{output_name} is empty.")

    content = str(text).strip()
    content_lower = content.lower()
    for phrase in REJECT_PHRASES:
        if phrase in content_lower:
            raise AgentOutputValidationError(f"{output_name} contains rejection phrase: {phrase}")
    return content


def extract_fenced_text(text: str, *, lang: str | None = None,
                        last_block: bool = False,
                        output_name: str = "Agent output") -> str:
    content = _validate_text_content(text, output_name)
    blocks: list[tuple[str, str]] = []

    for match in _FENCE_RE.finditer(content):
        block_lang = match.group("lang").strip().lower().split()
        block_lang = block_lang[0] if block_lang else ""
        body = match.group("body").strip()
        if lang is None or block_lang == lang.lower():
            blocks.append((block_lang, body))

    if blocks:
        return blocks[-1][1] if last_block else blocks[0][1]
    return content


def parse_json_output(
    text: str,
    *,
    output_name: str = "Agent output",
    required_keys: Iterable[str] | None = None,
    allowed_types: tuple[type, ...] = (dict, list),
    last_block: bool = False,
    require_mapping: bool = False,
) -> Any:
    if require_mapping:
        allowed_types = (dict,)

    raw = extract_fenced_text(text, lang="json", last_block=last_block, output_name=output_name)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        fallback_raw = extract_fenced_text(text, lang=None, last_block=last_block, output_name=output_name)
        if fallback_raw != raw:
            try:
                parsed = json.loads(fallback_raw)
            except json.JSONDecodeError:
                raise AgentOutputValidationError(f"{output_name} is not valid JSON: {exc}") from exc
        else:
            raise AgentOutputValidationError(f"{output_name} is not valid JSON: {exc}") from exc

    if allowed_types and not isinstance(parsed, allowed_types):
        expected = ", ".join(t.__name__ for t in allowed_types)
        raise AgentOutputValidationError(
            f"{output_name} must parse as {expected}, got {type(parsed).__name__}."
        )

    if required_keys:
        if not isinstance(parsed, dict):
            raise AgentOutputValidationError(f"{output_name} must be an object with keys {list(required_keys)}.")
        missing = [key for key in required_keys if key not in parsed]
        if missing:
            raise AgentOutputValidationError(f"{output_name} missing required fields: {', '.join(missing)}")

    return parsed


def get_crew_task_output(result: Any, task_index: int, output_name: str | None = None) -> str:
    tasks_output = getattr(result, "tasks_output", None)
    if not tasks_output:
        raise AgentOutputValidationError("Crew result has no tasks_output.")

    try:
        task_output = tasks_output[task_index]
    except IndexError as exc:
        raise AgentOutputValidationError(f"Crew result missing task output index {task_index}.") from exc

    raw = getattr(task_output, "raw", None)
    if raw is None:
        raw = getattr(task_output, "output", None)
    if raw is None:
        raw = str(task_output)

    return _validate_text_content(raw, output_name or f"Task {task_index} output")


def validate_agent_output(text: str, expected_format: str = "markdown") -> None:
    try:
        _validate_text_content(text, "Agent output")
    except AgentOutputValidationError as exc:
        print("=" * 60)
        print(f"Output validation failed: {exc}")
        print("Check the previous artifact or rerun the current step.")
        print("=" * 60)
        sys.exit(1)

    if expected_format in {"markdown", "text"}:
        return

    if expected_format == "json":
        try:
            parse_json_output(text)
        except AgentOutputValidationError as exc:
            print("=" * 60)
            print(f"JSON validation failed: {exc}")
            print("=" * 60)
            sys.exit(1)
        return

    raise ValueError(f"Unsupported expected format: {expected_format}")
