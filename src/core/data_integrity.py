"""Startup data integrity checks for AutoDesignMaker."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.paths import DESIGN_DATA_DIR, PLUGIN_MANIFEST_FILE, SCHEMAS_DIR, UCOS_DIR


def _non_empty_directory(path: Path, label: str, *, pattern: str = "*") -> list[str]:
    if not path.exists():
        return [f"{label} not found: {path}"]
    if not path.is_dir():
        return [f"{label} is not a directory: {path}"]
    if not any(path.glob(pattern)):
        return [f"{label} is empty: {path}"]
    return []


def validate_data_integrity() -> None:
    """Validate required runtime data before CLI or GUI startup."""

    errors: list[str] = []
    errors.extend(_non_empty_directory(DESIGN_DATA_DIR / "domains", "Design domains directory", pattern="*.json"))
    errors.extend(_non_empty_directory(SCHEMAS_DIR, "JSON schemas directory", pattern="*.json"))
    errors.extend(_non_empty_directory(UCOS_DIR / "knowledge", "UCOS knowledge directory"))

    if not PLUGIN_MANIFEST_FILE.exists():
        errors.append(f"Plugin manifest not found: {PLUGIN_MANIFEST_FILE}")
    else:
        try:
            manifest = json.loads(PLUGIN_MANIFEST_FILE.read_text(encoding="utf-8"))
            stages = manifest.get("plugins", {}).get("stages", {})
            if not isinstance(stages, dict) or not stages:
                errors.append(f"Plugin manifest has no stages: {PLUGIN_MANIFEST_FILE}")
        except json.JSONDecodeError as exc:
            errors.append(f"Plugin manifest is invalid JSON: {PLUGIN_MANIFEST_FILE}: {exc}")

    if errors:
        details = "\n".join(f"  - {error}" for error in errors)
        raise RuntimeError(f"Data integrity check failed:\n{details}")


__all__ = ["validate_data_integrity"]
