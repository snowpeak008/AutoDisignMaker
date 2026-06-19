"""Local model adapter placeholder."""

from __future__ import annotations

from core.adapters.base import ModelAdapter, ModelResult, ModelTask


class LocalAdapter(ModelAdapter):
    def generate(self, task: ModelTask) -> ModelResult:
        return ModelResult(
            task_id=task.task_id,
            status="failed",
            errors=["LocalAdapter is not enabled"],
        )
