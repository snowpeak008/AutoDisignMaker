from __future__ import annotations

from typing import Any


def format_context(context: dict[str, Any]) -> str:
    working = context.get("working", {})
    identity = context.get("identity", {}).get("profile", {})
    lines = [
        "# UCOS Session Summary",
        f"- domain: {working.get('domain', '')}",
        f"- active_save: {working.get('active_save_name', '')} ({working.get('active_save_id', '')})",
        f"- progress: {working.get('pipeline_progress', {})}",
        f"- role: {identity.get('role', '')}",
        f"- token_estimate: {context.get('token_estimate', 0)}",
    ]
    return "\n".join(lines) + "\n"

