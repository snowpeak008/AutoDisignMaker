from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ucos.output.token_budget import enforce_budget


def build(root: str | Path | None = None) -> dict[str, Any]:
    project_root = Path(root) if root else Path.cwd()
    ucos_dir = project_root / "ucos"
    sections = {
        "working": _read_json(ucos_dir / "knowledge" / "working" / "context.json", {}),
        "identity": {
            "profile": _read_json(ucos_dir / "identity" / "profile.json", {}),
            "constraints": _read_json(ucos_dir / "identity" / "constraints.json", {}).get("forbidden_actions", []),
            "policy": _read_json(ucos_dir / "identity" / "policy.json", {}),
        },
        "active_skills": _read_json(ucos_dir / "capability" / "registry.json", {}).get("skills", [])[:5],
        "short_term": _load_entries(ucos_dir / "knowledge" / "short_term" / "entries", limit=7),
        "episodic": _load_entries(ucos_dir / "knowledge" / "episodic" / "episodes", limit=3),
        "semantic": _read_json(ucos_dir / "knowledge" / "semantic" / "facts" / "domain_devflow.json", {}),
    }
    return enforce_budget(sections)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_entries(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for item in sorted(path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        entries.append(_read_json(item, {}))
    return entries

