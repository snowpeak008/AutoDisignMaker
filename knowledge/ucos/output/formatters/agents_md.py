from __future__ import annotations

from typing import Any


def format_context(context: dict[str, Any]) -> str:
    profile = context.get("identity", {}).get("profile", {})
    constraints = context.get("identity", {}).get("constraints", [])
    working = context.get("working", {})
    lines = [
        "# UCOS Entry",
        "",
        "## Current State",
        f"- Domain: {working.get('domain', '')}",
        f"- Active Save: {working.get('active_save_name', '')}",
        f"- Progress: {working.get('pipeline_progress', {})}",
        "",
        "## Identity",
        f"- Role: {profile.get('role', '')}",
        f"- Principles: {', '.join(profile.get('principles', []))}",
        "",
        "## Constraints",
    ]
    for item in constraints:
        lines.append(f"- {item.get('action')}: {', '.join(item.get('targets', []))}")
    return "\n".join(lines) + "\n"

