"""Preflight checks for actual Unity project development."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT


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
    return {
        "schema_version": 1,
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
    return name == "unity.exe" or path.stem.lower() == "unity" or re.search(r"(^|[/\\])unity([/\\]|$)", text) is not None


def unity_project_markers(development_path: Path) -> dict[str, bool]:
    return {
        "assets_dir": (development_path / "Assets").is_dir(),
        "project_settings_dir": (development_path / "ProjectSettings").is_dir(),
        "packages_manifest": (development_path / "Packages" / "manifest.json").is_file(),
    }


def run_actual_development_preflight(root: Path, *, write_report: bool = False) -> dict[str, Any]:
    settings = load_project_settings(root)
    blockers: list[dict[str, str]] = []
    warnings: list[str] = []
    development_path_text = settings.get("development_path", "")
    editor_path_text = settings.get("editor_path", "")

    if not development_path_text:
        blockers.append({"code": "missing_development_path", "field": "development_path",
                         "message": "development_path is not set.",
                         "fix": "Set development_path in settings/project_settings.json"})
    else:
        dev_path = Path(development_path_text).expanduser()
        if not dev_path.exists():
            blockers.append({"code": "development_path_not_found", "field": "development_path",
                             "message": f"development_path does not exist: {dev_path}",
                             "fix": "Update development_path in settings/project_settings.json"})

    if not editor_path_text:
        warnings.append("editor_path is not set.")
    elif not is_unity_editor_path(editor_path_text):
        warnings.append(f"editor_path may not point to Unity.exe: {editor_path_text}")

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


def assert_actual_development_preflight(root: Path, *, write_report: bool = False) -> None:
    report = run_actual_development_preflight(root, write_report=write_report)
    if report.get("status") != "passed":
        raise RuntimeError(f"Development preflight blocked: {report.get('blockers')}")
