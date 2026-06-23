"""Preflight checks for actual project development."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT


SUPPORTED_ENGINES = ("unity", "unreal", "godot", "custom")

ENGINE_LABELS: dict[str, str] = {
    "unity": "Unity",
    "unreal": "Unreal Engine",
    "godot": "Godot",
    "custom": "自定义",
}

ENGINE_PATH_LABELS: dict[str, tuple[str, str]] = {
    # engine -> (project_path_label, editor_path_label)
    "unity": ("Unity 项目路径（development_path）", "Unity Editor 路径（editor_path）"),
    "unreal": (
        "Unreal 项目目录（development_path）",
        "UnrealEditor 路径（editor_path）",
    ),
    "godot": ("Godot 项目目录（development_path）", "Godot 可执行文件（editor_path）"),
    "custom": (
        "项目路径（development_path，可选）",
        "引擎可执行文件路径（editor_path，可选）",
    ),
}


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
    from core.paths import SETTINGS_DIR

    return SETTINGS_DIR / "project_settings.json"


def preflight_report_path(root: Path) -> Path:
    from core.paths import SANDBOX_DIR

    return SANDBOX_DIR / "outputs" / "preflight" / "actual_development_preflight.json"


def load_project_settings(root: Path) -> dict[str, Any]:
    raw = read_json(project_settings_path(root), {})
    if not isinstance(raw, dict):
        raw = {}
    engine = str(raw.get("project_engine") or "unity").strip().lower()
    if engine not in SUPPORTED_ENGINES:
        engine = "unity"
    adapter = str(raw.get("pipeline_adapter") or "none").strip().lower()
    return {
        "schema_version": 1,
        "project_engine": engine,
        "pipeline_adapter": adapter,
        "custom_engine_name": str(raw.get("custom_engine_name") or "").strip(),
        "development_path": str(raw.get("development_path") or "").strip(),
        "editor_path": str(raw.get("editor_path") or "").strip(),
    }


def is_unity_editor_path(path_text: str) -> bool:
    if not path_text.strip():
        return False
    path = Path(path_text).expanduser()
    name = path.name.lower()
    text = str(path).lower()
    if "unity hub" in text or "unityhub" in text:
        return False
    if path.suffix.lower() == ".app":
        return "unity" in name
    return (
        name == "unity.exe"
        or path.stem.lower() == "unity"
        or re.search(r"(^|[/\\])unity([/\\]|$)", text) is not None
    )


def unity_project_markers(development_path: Path) -> dict[str, bool]:
    return {
        "assets_dir": (development_path / "Assets").is_dir(),
        "project_settings_dir": (development_path / "ProjectSettings").is_dir(),
        "packages_manifest": (
            development_path / "Packages" / "manifest.json"
        ).is_file(),
    }


def run_actual_development_preflight(
    root: Path, *, write_report: bool = False
) -> dict[str, Any]:
    settings = load_project_settings(root)
    engine = settings.get("project_engine", "unity")
    blockers: list[dict[str, str]] = []
    warnings: list[str] = []
    development_path_text = settings.get("development_path", "")
    editor_path_text = settings.get("editor_path", "")

    if engine == "custom":
        # 自定义引擎：development_path 可选，仅 warning
        if development_path_text:
            dev_path = Path(development_path_text).expanduser()
            if not dev_path.exists():
                warnings.append(f"development_path does not exist: {dev_path}")
    else:
        if not development_path_text:
            blockers.append(
                {
                    "code": "missing_development_path",
                    "field": "development_path",
                    "message": "development_path is not set.",
                    "fix": "Set development_path in settings/project_settings.json",
                }
            )
        else:
            dev_path = Path(development_path_text).expanduser()
            if not dev_path.exists():
                blockers.append(
                    {
                        "code": "development_path_not_found",
                        "field": "development_path",
                        "message": f"development_path does not exist: {dev_path}",
                        "fix": "Update development_path in settings/project_settings.json",
                    }
                )
            elif engine == "unity":
                markers = unity_project_markers(dev_path)
                if not markers.get("assets_dir"):
                    warnings.append("Unity project missing Assets/ directory.")

    if engine == "unity":
        if not editor_path_text:
            warnings.append("editor_path is not set.")
        elif not is_unity_editor_path(editor_path_text):
            warnings.append(
                f"editor_path may not point to Unity.exe: {editor_path_text}"
            )
    elif engine in ("unreal", "godot") and not editor_path_text:
        warnings.append(
            f"editor_path is not set for {ENGINE_LABELS.get(engine, engine)}."
        )

    report = {
        "schema_version": 1,
        "timestamp": now_iso(),
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "settings": settings,
    }
    if write_report:
        write_json(preflight_report_path(root), report)
    return report


def assert_actual_development_preflight(
    root: Path, *, write_report: bool = False
) -> None:
    report = run_actual_development_preflight(root, write_report=write_report)
    if report.get("status") != "passed":
        raise RuntimeError(f"Development preflight blocked: {report.get('blockers')}")
