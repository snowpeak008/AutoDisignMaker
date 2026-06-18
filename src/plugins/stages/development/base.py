"""Development stage plugins that delegate to the migrated DevFlow orchestrator."""

from __future__ import annotations

from src.core.context import StageContext, StageResult
from src.core.stage_plugin import StagePlugin


class DevelopmentStagePlugin(StagePlugin):
    stage_number = 0
    stage_name = "development"

    @property
    def stage_id(self) -> str:
        return f"{self.stage_number:02d}"

    @property
    def title(self) -> str:
        return self.stage_name

    def execute(self, context: StageContext) -> StageResult:
        if context.test_mode:
            return StageResult(
                status="success",
                outputs={"stageId": self.stage_id, "mode": "test"},
                message="Development stage test-mode validation passed.",
            )

        from orchestrator import run_range

        exit_code = run_range(
            self.stage_number,
            self.stage_number,
            auto_approve=True,
            skip_actual_dev_preflight=bool(context.metadata.get("skip_actual_dev_preflight", False)),
        )
        status = "success" if exit_code == 0 else "failed"
        return StageResult(status=status, outputs={"exitCode": exit_code})

