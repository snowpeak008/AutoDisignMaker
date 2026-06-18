"""Shared pipeline contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


Validator = Callable[[Path], list[str]]


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    path: Path
    dependencies: tuple[str, ...] = ()
    validator_name: str = ""
    reviewer_name: str = ""
    producer_name: str = ""
    generated_by_ai: bool = False


@dataclass
class ArtifactState:
    artifact_id: str
    status: str = "pending"
    path: str = ""
    errors: list[str] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class StageResult:
    stage: int
    status: str
    message: str = ""
    outputs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
