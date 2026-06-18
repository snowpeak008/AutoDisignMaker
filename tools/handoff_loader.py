#!/usr/bin/env python3
"""Load structured handoff contracts with Markdown fallback support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.folder_manager import find_latest


def read_structured(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def find_design_handoff(design_doc_path: Path | None = None) -> Path | None:
    if design_doc_path:
        base = design_doc_path if design_doc_path.is_dir() else design_doc_path.parent
        candidate = base / "design_handoff.json"
        if candidate.exists():
            return candidate

    latest_design = find_latest("Design")
    if latest_design:
        candidate = latest_design / "design_handoff.json"
        if candidate.exists():
            return candidate
    return None


def load_design_handoff(design_doc_path: Path | None = None) -> tuple[Path | None, dict[str, Any]]:
    path = find_design_handoff(design_doc_path)
    if not path:
        return None, {}
    return path, read_structured(path)


def load_design_sources(design_doc_path: Path) -> dict[str, Any]:
    """Return structured design input plus Markdown fallback text."""
    handoff_path, handoff = load_design_handoff(design_doc_path)
    markdown = ""
    if design_doc_path.exists() and design_doc_path.is_file():
        markdown = design_doc_path.read_text(encoding="utf-8")
    return {
        "handoff_path": str(handoff_path).replace("\\", "/") if handoff_path else "",
        "handoff": handoff,
        "markdown_path": str(design_doc_path).replace("\\", "/"),
        "markdown": markdown,
    }
