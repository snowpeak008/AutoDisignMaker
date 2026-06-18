#!/usr/bin/env python3
"""Preflight checks for actual Unity project development."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def project_settings_path(root: Path) -> Path:
    return root / "project_settings.json"


def preflight_report_path(root: Path) -> Path:
    return root / "outputs" / "preflight" / "actual_development_preflight.json"


def load_project_settings(root: Path) -> dict[str, Any]:
    raw = read_json(project_settings_path(root), {})
    if not isinstance(raw, dict):
        raw = {}
    return {
        "schema_version": 1,
        "development_path": str(raw.get("development_path") or "").strip(),
        "editor_path": str(raw.get("editor_path") or "").strip(),
    }


def _blocker(code: str, message: str, *, fix: str, field: str = "") -> dict[str, str]:
    return {
        "code": code,
        "field": field,
        "message": message,
        "fix": fix,
    }


def is_unity_editor_path(path_text: str) -> bool:
    if not path_text.strip():
        return False
    path = Path(path_text).expanduser()
    name = path.name.lower()
    stem = path.stem.lower()
    text = str(path).lower()
    if "unity hub" in text or "unityhub" in text:
        return False
    if path.suffix.lower() == ".app":
        return "unity" in name
    return name == "unity.exe" or stem == "unity" or re.search(r"(^|[/\\])unity([/\\]|$)", text) is not None


def unity_project_markers(development_path: Path) -> dict[str, bool]:
    return {
        "assets_dir": (development_path / "Assets").is_dir(),
        "project_settings_dir": (development_path / "ProjectSettings").is_dir(),
        "packages_manifest": (development_path / "Packages" / "manifest.json").is_file(),
    }


def unsupported_project_markers(development_path: Path) -> list[str]:
    markers: list[str] = []
    if (development_path / "project.godot").exists():
        markers.append("Godot project.godot")
    if list(development_path.glob("*.uproject")):
        markers.append("Unreal .uproject")
    if (development_path / "package.json").exists() and not (development_path / "Assets").exists():
        markers.append("Web/Node package.json")
    return markers


def run_actual_development_preflight(root: Path, *, write_report: bool = True) -> dict[str, Any]:
    root = Path(root)
    settings = load_project_settings(root)
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    raw_dev = settings["development_path"]
    raw_editor = settings["editor_path"]
    development_path = Path(raw_dev).expanduser() if raw_dev else None
    editor_path = Path(raw_editor).expanduser() if raw_editor else None

    if not raw_dev:
        blockers.append(_blocker(
            "DEV_PATH_MISSING",
            "实际开发地址未设置。",
            field="development_path",
            fix="打开项目设置，填写已由 Unity 创建好的项目目录。",
        ))
    elif development_path is not None and not development_path.exists():
        blockers.append(_blocker(
            "DEV_PATH_NOT_FOUND",
            f"实际开发地址不存在：{development_path}",
            field="development_path",
            fix="填写存在的 Unity 项目目录，或先用 Unity 创建初始工程。",
        ))
    elif development_path is not None and not development_path.is_dir():
        blockers.append(_blocker(
            "DEV_PATH_NOT_DIRECTORY",
            f"实际开发地址不是目录：{development_path}",
            field="development_path",
            fix="填写 Unity 项目目录。",
        ))

    if not raw_editor:
        blockers.append(_blocker(
            "UNITY_EDITOR_PATH_MISSING",
            "Unity Editor 路径未设置。",
            field="editor_path",
            fix="打开项目设置，填写 Unity Editor 可执行文件路径。",
        ))
    elif editor_path is not None and not editor_path.exists():
        blockers.append(_blocker(
            "UNITY_EDITOR_NOT_FOUND",
            f"Unity Editor 路径不存在：{editor_path}",
            field="editor_path",
            fix="填写存在的 Unity Editor 可执行文件路径。",
        ))
    elif editor_path is not None and not is_unity_editor_path(raw_editor):
        blockers.append(_blocker(
            "UNITY_EDITOR_NOT_RECOGNIZED",
            f"编辑器路径不像 Unity Editor：{editor_path}",
            field="editor_path",
            fix="填写 Unity.exe、Unity.app 或 Unity Editor 可执行文件路径，不要填写 Unity Hub、Cursor 或 VS Code。",
        ))

    markers = {"assets_dir": False, "project_settings_dir": False, "packages_manifest": False}
    unsupported_markers: list[str] = []
    if development_path is not None and development_path.exists() and development_path.is_dir():
        markers = unity_project_markers(development_path)
        unsupported_markers = unsupported_project_markers(development_path)
        if unsupported_markers and not all(markers.values()):
            blockers.append(_blocker(
                "UNSUPPORTED_PROJECT_TYPE",
                "实际开发地址包含暂不支持的项目标记：" + "；".join(unsupported_markers),
                field="development_path",
                fix="第一版只支持 Unity。请填写 Unity 初始工程目录。",
            ))
        if not all(markers.values()):
            missing = [name for name, exists in markers.items() if not exists]
            blockers.append(_blocker(
                "UNITY_PROJECT_MARKERS_MISSING",
                "实际开发地址不是完整 Unity 初始工程，缺少：" + "，".join(missing),
                field="development_path",
                fix="请先用 Unity Editor 或 Unity Hub 创建初始 Unity 工程，再填写该工程目录。",
            ))
        if unsupported_markers and all(markers.values()):
            blockers.append(_blocker(
                "PROJECT_TYPE_CONFLICT",
                "Unity 工程标记与其他项目类型标记同时存在：" + "；".join(unsupported_markers),
                field="development_path",
                fix="请清理冲突目录或重新选择实际开发地址。",
            ))

    report = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "passed" if not blockers else "blocked",
        "valid": not blockers,
        "settings_path": str(project_settings_path(root)),
        "development_path": raw_dev,
        "editor_path": raw_editor,
        "unity_editor_recognized": bool(raw_editor and is_unity_editor_path(raw_editor)),
        "unity_project_markers": markers,
        "unsupported_project_markers": unsupported_markers,
        "blockers": blockers,
        "warnings": warnings,
        "rules": [
            "Formal pipeline runs require user-provided development_path and Unity editor_path.",
            "The development path must be an existing Unity project created by the user.",
            "Preflight failure must not create a save or stage artifact.",
        ],
    }
    if write_report:
        write_json(preflight_report_path(root), report)
    return report


def assert_actual_development_preflight(root: Path, *, write_report: bool = True) -> dict[str, Any]:
    report = run_actual_development_preflight(root, write_report=write_report)
    if report["status"] != "passed":
        raise RuntimeError(
            "Actual development preflight blocked: "
            + "; ".join(item["message"] for item in report.get("blockers", []))
        )
    return report
