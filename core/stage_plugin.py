"""Base interface for all design and development stage plugins.

Migrated from src/core/stage_plugin.py — no logic changes.
All step plugins (D1-D4 + step_00+) must subclass StagePlugin.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.context import StageContext, StageResult


class StagePlugin(ABC):
    @property
    @abstractmethod
    def stage_id(self) -> str:
        """Stable stage identifier, for example 'D1' or '00'."""

    @property
    def title(self) -> str:
        return self.stage_id

    def validate_inputs(self, context: StageContext) -> list[str]:
        """Return a list of error messages if inputs are invalid."""
        return []

    @abstractmethod
    def execute(self, context: StageContext) -> StageResult:
        """Execute the stage and return a result."""

    def validate_outputs(self, context: StageContext) -> list[str]:
        """Return a list of error messages if outputs are invalid."""
        return []

    def run(self, context: StageContext) -> StageResult:
        """Full lifecycle: validate_inputs → execute → validate_outputs."""
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


__all__ = ["StagePlugin"]
