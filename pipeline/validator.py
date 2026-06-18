"""Validator registry and common validators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


ValidatorFunc = Callable[[Path], list[str]]


class ValidatorRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ValidatorFunc] = {}

    def register(self, name: str, func: ValidatorFunc) -> None:
        self._items[name] = func

    def validate(self, name: str, path: Path) -> list[str]:
        if not name:
            return ["artifact has no validator"]
        if name not in self._items:
            return [f"unknown validator: {name}"]
        return self._items[name](path)


def validate_existing_nonempty(path: Path) -> list[str]:
    if not path.exists():
        return [f"missing file: {path}"]
    if path.stat().st_size == 0:
        return [f"empty file: {path}"]
    return []


def validate_json_object(path: Path) -> list[str]:
    errors = validate_existing_nonempty(path)
    if errors:
        return errors
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid json: {exc}"]
    if not isinstance(data, dict):
        return ["json root must be object"]
    return []


def validate_markdown_with_heading(path: Path) -> list[str]:
    errors = validate_existing_nonempty(path)
    if errors:
        return errors
    text = path.read_text(encoding="utf-8")
    if "#" not in text:
        return ["markdown file has no heading"]
    return []
