from src.core.context import StageContext, StageResult
from src.plugins.adapters.design_export_adapter import export_concept_package
from src.plugins.stages.design.base import DesignStagePlugin


class StepD4Plugin(DesignStagePlugin):
    stage_number = 4
    stage_name = "DevFlow Handoff"

    def execute(self, context: StageContext) -> StageResult:
        result = super().execute(context)
        package = export_concept_package()
        result.outputs["conceptPackage"] = package
        return result
