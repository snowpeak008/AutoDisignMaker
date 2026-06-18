"""Base interface for design and development stage plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.context import StageContext, StageResult


class StagePlugin(ABC):
    @property
    @abstractmethod
    def stage_id(self) -> str:
        """Stable stage identifier, for example `D1` or `00`."""

    @property
    def title(self) -> str:
        return self.stage_id

    def validate_inputs(self, context: StageContext) -> list[str]:
        return []

    @abstractmethod
    def execute(self, context: StageContext) -> StageResult:
        """Execute the stage."""

    def validate_outputs(self, context: StageContext) -> list[str]:
        return []

    def run(self, context: StageContext) -> StageResult:
        input_errors = self.validate_inputs(context)
        if input_errors:
            return StageResult(status="failed", errors=input_errors)
        result = self.execute(context)
        context.outputs.update(result.outputs)
        output_errors = self.validate_outputs(context)
        if output_errors:
            result.errors.extend(output_errors)
            result.status = "failed"
        return result

