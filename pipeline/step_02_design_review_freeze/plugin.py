from core.stage_plugin import StagePlugin
from core.context import StageContext, StageResult
from core.source.groups import SourceGroup
from core.source.importer import run_import_step
from core.engines.generation import apply_development_plan_outputs


class Plugin(StagePlugin):
    stage_id = "02"
    _source_groups = [
        SourceGroup("2a_subsystem_design", ("devflow_SubsystemDesign_*",), "latest", False, ("SubsystemDesign",)),
        SourceGroup("2b_ai_design_script", ("devflow_AIDesignScript_*",), "latest", False, ("AIDesignScript",)),
        SourceGroup("2c_design_package", ("devflow_Design_*",), "latest", False, ("Design",)),
        SourceGroup("2c_development_design", ("devflow_DevelopmentDesign_*",), "latest", False, ("DevelopmentDesign",)),
    ]

    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.test_mode:
            return StageResult(status='success', outputs={'stage_id': self.stage_id, 'mode': 'test'})
        report = run_import_step(int(self.stage_id), self._source_groups, context=ctx)
        result = apply_development_plan_outputs(int(self.stage_id), report)
        if isinstance(result, dict):
            status = result.get('status', 'success')
            return StageResult(status=status, outputs=result)
        return result
