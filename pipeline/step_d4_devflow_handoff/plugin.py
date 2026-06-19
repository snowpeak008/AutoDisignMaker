from core.context import StageContext, StageResult
from core.design.export_adapter import export_concept_package
from pipeline._design_base import DesignStagePlugin


class Plugin(DesignStagePlugin):
    stage_number = 4
    stage_name = "DevFlow Handoff"

    def execute(self, context: StageContext) -> StageResult:
        result = super().execute(context)
        package = export_concept_package()
        result.outputs["conceptPackage"] = package
        return result
