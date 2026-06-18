#!/usr/bin/env python3
"""Structured data helpers for Markdown files.

Project convention:
- Files stay as .md.
- Machine-readable structured payloads use fenced JSON blocks.
- Human-facing content uses ordinary Markdown headings, lists, and tables.
- Fenced YAML can still be read for archived pipeline artifacts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools import yaml_compat as yaml


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(?P<body>.*?)\n```", re.DOTALL)
_DATA_FENCE_RE = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<body>.*?)(?:\n)?```", re.DOTALL)


def dumps_data(data: Any, *, indent: int = 2) -> str:
    return json.dumps(data, ensure_ascii=False, indent=indent)


def loads_data(text: str) -> Any:
    content = text.strip()
    match = _JSON_FENCE_RE.search(content)
    if match:
        content = match.group("body").strip()
        return json.loads(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    for match in _DATA_FENCE_RE.finditer(content):
        lang = match.group("lang").strip().lower().split()
        lang = lang[0] if lang else ""
        body = match.group("body").strip()
        if lang in {"yaml", "yml"}:
            return yaml.safe_load(body)

    if re.match(r"^[A-Za-z0-9_\"'-]+\s*:", content):
        return yaml.safe_load(content)

    raise json.JSONDecodeError("No JSON payload found", content, 0)


def read_data(path: Path) -> Any:
    return loads_data(path.read_text(encoding="utf-8"))


def write_data(path: Path, data: Any, *, title: str = "Data") -> None:
    path.write_text(
        f"# {title}\n\n```json\n{dumps_data(data)}\n```\n",
        encoding="utf-8",
    )


def data_to_markdown(data: Any, *, level: int = 2) -> str:
    lines: list[str] = []

    def emit(value: Any, depth: int, label: str | None = None) -> None:
        heading = "#" * min(max(depth, 2), 6)
        if label:
            lines.append(f"{heading} {label}")
        if isinstance(value, dict):
            if not value:
                lines.append("- none")
                return
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    emit(child, depth + 1, str(key))
                else:
                    lines.append(f"- **{key}**: {child}")
            return
        if isinstance(value, list):
            if not value:
                lines.append("- none")
                return
            for idx, item in enumerate(value, 1):
                if isinstance(item, dict):
                    emit(item, depth + 1, f"Item {idx}")
                elif isinstance(item, list):
                    emit(item, depth + 1, f"Item {idx}")
                else:
                    lines.append(f"- {item}")
            return
        lines.append(str(value))

    emit(data, level)
    return "\n".join(lines).strip()


def data_to_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    return dumps_data(data)


def read_structured_or_text(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return loads_data(text)
    except Exception:
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(text)
        from tools.md_parser import parse_md_output

        return parse_md_output(text, output_name=str(path))
