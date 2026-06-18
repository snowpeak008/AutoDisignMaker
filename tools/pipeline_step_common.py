#!/usr/bin/env python3
"""Shared utilities for pipeline steps 3-12.

These helpers keep step scripts in one implementation style: Python orchestration,
Markdown for human-readable artifacts, and JSON for machine-readable contracts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


STEP_OUTPUT_STYLE_RULES = """
Pipeline output style rules for steps 3-12:
- The orchestration code is Python only.
- Human-readable artifacts use Markdown prose.
- Machine-readable artifacts use JSON data, not JSON-shaped pseudo-code.
- Do not mix implementation snippets in multiple languages in the same artifact.
- Do not emit Python, C++, C#, or shell code unless the current step explicitly asks for source code.
- When implementation code is required by a downstream plan, use only the target language and paths declared by that plan.
- Keep examples as data examples, configuration examples, or prose; avoid code fences for unrelated languages.
""".strip()


def configure_utf8_stdio() -> None:
    """Make Windows console output consistent for Chinese pipeline logs."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def read_text_file(path: Path, default: str = "") -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return default


def require_text_file(path: Path, label: str) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path.read_text(encoding="utf-8")


def write_text_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json_file(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def json_markdown_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def write_markdown_json(path: Path, title: str, data: Any) -> Path:
    text = f"# {title}\n\n{json_markdown_block(data)}\n"
    return write_text_file(path, text)


def append_output_style_rules(text: str) -> str:
    if STEP_OUTPUT_STYLE_RULES in text:
        return text
    return text.rstrip() + "\n\n# PIPELINE OUTPUT STYLE RULES\n" + STEP_OUTPUT_STYLE_RULES + "\n"
