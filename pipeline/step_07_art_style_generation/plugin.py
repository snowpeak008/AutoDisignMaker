from __future__ import annotations

from core.context import StageContext, StageResult
from core.engines.generation import apply_development_plan_outputs
from core.source.importer import run_import_step
from core.stage_plugin import StagePlugin


class Plugin(StagePlugin):
    stage_id = "07"
    _source_groups = []

    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.test_mode:
            return StageResult(
                status="success", outputs={"stage_id": self.stage_id, "mode": "test"}
            )
        report = run_import_step(int(self.stage_id), self._source_groups, context=ctx)
        result = apply_development_plan_outputs(int(self.stage_id), report)
        if isinstance(result, dict):
            status = result.get("status", "success")
            return StageResult(status=status, outputs=result)
        return result
