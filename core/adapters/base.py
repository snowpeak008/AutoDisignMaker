"""Shared model adapter interface."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelTask:
    task_id: str
    prompt: str
    input_files: list[str] = field(default_factory=list)
    output_files: list[str] = field(default_factory=list)
    allowed_write_paths: list[str] = field(default_factory=list)
    timeout_seconds: int = 1800
    sandbox: str = "workspace-write"


@dataclass
class ModelResult:
    task_id: str
    status: str
    text: str = ""
    errors: list[str] = field(default_factory=list)


class ModelAdapter:
    def configure(self, **kwargs) -> "ModelAdapter":
        return self

    def generate(self, task: ModelTask) -> ModelResult:
        raise NotImplementedError
