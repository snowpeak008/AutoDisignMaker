#!/usr/bin/env python3
"""Shared helpers for index-driven planning and execution stages."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.structured_md import read_structured_or_text, write_data


def first_existing(directory: Path, *names: str) -> Path | None:
    for name in names:
        path = directory / name
        if path.exists():
            return path
    return None


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                loaded = json.loads(text)
                return as_list(loaded)
            except Exception:
                pass
        return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]
    return [str(value).strip()]


def normalize_id(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", text)
    return safe.strip(".-") or fallback


def _extract_markdown_value(text: str, *keys: str) -> str:
    escaped = "|".join(re.escape(key) for key in keys)
    patterns = [
        rf"(?im)^-\s+\*\*(?:{escaped})\*\*\s*:\s*(.+)$",
        rf"(?im)^-\s*(?:{escaped})\s*[：:]\s*(.+)$",
        rf"(?im)^\s*(?:{escaped})\s*[：:]\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _extract_markdown_list(text: str, *keys: str) -> list[str]:
    value = _extract_markdown_value(text, *keys)
    if value and value not in {"-", "无", "none", "None"}:
        return as_list(value)

    escaped = "|".join(re.escape(key) for key in keys)
    header_re = re.compile(
        rf"(?im)^-\s+\*\*(?:{escaped})\*\*\s*:\s*$|^-\s*(?:{escaped})\s*[：:]\s*$|^##+\s*(?:{escaped})\s*$"
    )
    match = header_re.search(text)
    if not match:
        return []

    lines: list[str] = []
    for line in text[match.end():].splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("#"):
            break
        item_match = re.match(r"^-\s+(.+)$", stripped)
        if item_match:
            value = item_match.group(1).strip()
            if not value.startswith("**"):
                lines.append(value)
            continue
        if lines:
            break
    return lines


def parse_plan_markdown(path: Path, *, kind: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fallback_id = path.stem
    if kind == "program":
        item_id = (
            _extract_markdown_value(text, "plan_id", "PlanID", "计划ID")
            or fallback_id
        )
        return {
            "plan_id": normalize_id(item_id, fallback_id),
            "title": _extract_markdown_value(text, "title", "Title", "标题") or path.stem,
            "system_id": _extract_markdown_value(text, "system_id", "SystemID", "系统ID"),
            "level": _extract_markdown_value(text, "level", "Level", "档位"),
            "dependencies": _extract_markdown_list(text, "dependencies", "Dependencies", "依赖"),
            "target_path": _extract_markdown_value(text, "target_path", "TargetPath", "目标路径"),
            "output_files": _extract_markdown_list(text, "output_files", "OutputFiles", "输出文件"),
            "touched_paths": _extract_markdown_list(text, "touched_paths", "TouchedPaths", "触碰路径"),
            "art_asset_refs": _extract_markdown_list(text, "art_asset_refs", "ArtAssetRefs", "美术资产引用"),
            "plan_file": path.name,
        }

    item_id = (
        _extract_markdown_value(text, "task_id", "TaskID", "计划ID", "任务ID")
        or fallback_id
    )
    return {
        "task_id": normalize_id(item_id, fallback_id),
        "asset_id": _extract_markdown_value(text, "asset_id", "AssetID", "资产ID") or item_id,
        "title": _extract_markdown_value(text, "title", "Title", "标题") or path.stem,
        "category": _extract_markdown_value(text, "category", "Category", "类别"),
        "level": _extract_markdown_value(text, "level", "Level", "档位"),
        "mode": _extract_markdown_value(text, "mode", "Mode", "生成模式"),
        "dependencies": _extract_markdown_list(text, "dependencies", "Dependencies", "依赖"),
        "target_path": _extract_markdown_value(text, "target_path", "TargetPath", "目标路径"),
        "output_files": _extract_markdown_list(text, "output_files", "OutputFiles", "输出文件"),
        "source_files": _extract_markdown_list(text, "source_files", "SourceFiles", "源文件"),
        "task_file": path.name,
    }


def read_index(directory: Path, *, kind: str) -> dict[str, Any] | None:
    name = "program_plan_index" if kind == "program" else "art_plan_index"
    path = first_existing(
        directory,
        f"{name}.md",
        f"{name}.json",
        f"{name}.yaml",
        f"{name}.yml",
    )
    if not path:
        return None
    data = read_structured_or_text(path)
    if not isinstance(data, dict):
        return None
    return data


def write_index(directory: Path, *, kind: str, data: dict[str, Any]) -> Path:
    name = "program_plan_index.md" if kind == "program" else "art_plan_index.md"
    title = "Program Plan Index" if kind == "program" else "Art Plan Index"
    path = directory / name
    write_data(path, data, title=title)
    return path


def derive_index_from_plan_files(directory: Path, *, kind: str) -> dict[str, Any]:
    records = []
    for path in sorted(directory.glob("*.md")):
        if path.name in {
            "开发顺序.md",
            "program_structure_spec.md",
            "art_structure_spec.md",
            "program_plan_index.md",
            "art_plan_index.md",
            "crew_raw_output.txt",
        }:
            continue
        if path.name.startswith(("PLAN-", "ART-")):
            records.append(parse_plan_markdown(path, kind=kind))

    if kind == "program":
        return {"plans": records, "parallel_groups": read_parallel_groups(directory)}
    return {"tasks": records}


def read_parallel_groups(directory: Path) -> list[list[str]]:
    path = first_existing(
        directory,
        "parallel_groups.json",
        "parallel_groups.md",
        "parallel_groups.yaml",
        "parallel_groups.yml",
    )
    if not path:
        return []
    data = read_structured_or_text(path)
    if isinstance(data, dict):
        data = data.get("parallel_groups") or data.get("ParallelGroups") or data.get("groups") or []
    return [as_list(group) for group in data] if isinstance(data, list) else []


def load_or_derive_index(directory: Path, *, kind: str) -> dict[str, Any]:
    index = read_index(directory, kind=kind)
    if index is not None:
        return index
    return derive_index_from_plan_files(directory, kind=kind)


def load_execution_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": {}, "created_at": datetime.now().isoformat(timespec="seconds")}
    data = read_structured_or_text(path)
    if isinstance(data, dict):
        data.setdefault("items", {})
        return data
    return {"items": {}, "created_at": datetime.now().isoformat(timespec="seconds")}


def save_execution_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_data(path, state, title="Execution State")


def update_execution_item(path: Path, item_id: str, **fields: Any) -> None:
    state = load_execution_state(path)
    items = state.setdefault("items", {})
    current = dict(items.get(item_id, {}))
    current.update(fields)
    current["updated_at"] = datetime.now().isoformat(timespec="seconds")
    items[item_id] = current
    save_execution_state(path, state)
