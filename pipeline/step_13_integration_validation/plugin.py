from core.stage_plugin import StagePlugin
from core.context import StageContext, StageResult
from core.config.loader import get_config
from core.runtime.pipeline_state import load_pipeline_state
from core.source.groups import SourceGroup
from core.source.importer import run_import_step
from core.engines.generation import apply_development_plan_outputs


def _completed_with_review_blocker(ctx: StageContext) -> StageResult | None:
    state = load_pipeline_state(ctx.project_root)
    steps = state.get("steps", {}) if isinstance(state, dict) else {}
    for step_num in (11, 12):
        step_state = steps.get(str(step_num), {})
        if step_state.get("status") != "completed_with_review":
            continue
        continue_ok = get_config(
            "pipeline.unattended_execution.continue_after_completed_with_review",
            False,
        )
        if continue_ok:
            continue
        message = f"Step {step_num} has unreviewed items. Handle correction_queue first."
        return StageResult(
            status="blocked",
            outputs={
                "stage_id": "13",
                "blocked_step": step_num,
                "message": message,
            },
            errors=[message],
        )
    return None


class Plugin(StagePlugin):
    stage_id = "13"
    _source_groups = [SourceGroup("integration_validation", ("devflow_Integration_*",), "latest", False, ("Integration",))]

    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.test_mode:
            return StageResult(status='success', outputs={'stage_id': self.stage_id, 'mode': 'test'})
        blocker = _completed_with_review_blocker(ctx)
        if blocker is not None:
            return blocker
        report = run_import_step(int(self.stage_id), self._source_groups, context=ctx)
        result = apply_development_plan_outputs(int(self.stage_id), report)
        if isinstance(result, dict):
            status = result.get('status', 'success')
            return StageResult(status=status, outputs=result)
        return result
