"""Review pipeline hooks."""

from __future__ import annotations

from pathlib import Path


class Reviewer:
    """Deterministic review placeholder.

    AI reviewer adapters can be plugged in later. The first no-CrewAI pass keeps
    this deterministic so Stage 3 can finish without model calls.
    """

    def review(self, artifact_id: str, path: Path) -> list[str]:
        if not path.exists():
            return [f"{artifact_id}: output is missing"]
        return []
