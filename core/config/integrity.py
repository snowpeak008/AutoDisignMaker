"""Startup data integrity checks."""

from __future__ import annotations

import json
from pathlib import Path

from core.paths import KNOWLEDGE_DIR, PLUGIN_MANIFEST_FILE, PROJECT_ROOT, SCHEMAS_DIR

DESIGN_DATA_DIR = KNOWLEDGE_DIR / "design_data"
UCOS_DIR = PROJECT_ROOT / "ucos"


def _non_empty_directory(path: Path, label: str, *, pattern: str = "*") -> list[str]:
    if not path.exists():
        return [f"{label} not found: {path}"]
    if not path.is_dir():
        return [f"{label} is not a directory: {path}"]
    if not any(path.glob(pattern)):
        return [f"{label} is empty: {path}"]
    return []


def validate_data_integrity() -> None:
    errors: list[str] = []
    # design data check — skip if not yet migrated
    design_domains = DESIGN_DATA_DIR / "domains"
    if design_domains.exists():
        errors.extend(_non_empty_directory(design_domains, "Design domains directory", pattern="*.json"))
    if SCHEMAS_DIR.exists():
        errors.extend(_non_empty_directory(SCHEMAS_DIR, "JSON schemas directory", pattern="*.json"))
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
        details = "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(f"Data integrity check failed:\n{details}")
