"""Shared stage execution data structures.

Migrated from src/core/context.py with additions:
- knowledge: dict[str, str]  — knowledge_refs content injected before execution
- skills: dict[str, Any]     — skill definitions available to the stage
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from core.paths import PROJECT_ROOT, get_stage_artifact_dir

StageStatus = Literal["success", "failed", "skipped", "blocked"]


@dataclass
class StageContext:
    stage_id: str
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, str] = field(default_factory=dict)   # knowledge_refs content
    skills: dict[str, Any] = field(default_factory=dict)       # available skill defs
    test_mode: bool = False

    @property
    def artifact_dir(self) -> Path:
        return get_stage_artifact_dir(self.stage_id)


@dataclass
class StageResult:
    status: StageStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "success"


__all__ = ["StageStatus", "StageContext", "StageResult"]
