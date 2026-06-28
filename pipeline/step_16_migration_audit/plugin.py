from core.stage_plugin import StagePlugin
from core.context import StageContext, StageResult


class Plugin(StagePlugin):
    stage_id = "16"

    def execute(self, ctx: StageContext) -> StageResult:
        from core.source.importer import run_audit_step
        return run_audit_step(ctx)
