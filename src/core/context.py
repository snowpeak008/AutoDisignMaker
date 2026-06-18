"""Shared stage execution data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from src.core.paths import PROJECT_ROOT, get_stage_artifact_dir

StageStatus = Literal["success", "failed", "skipped", "blocked"]


@dataclass
class StageContext:
    stage_id: str
    project_root: Path = PROJECT_ROOT
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
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

