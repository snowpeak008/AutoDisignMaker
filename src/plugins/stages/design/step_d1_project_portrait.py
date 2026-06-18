from src.core.config_loader import load_config
from src.core.context import StageContext, StageResult
from src.plugins.stages.design.base import DesignStagePlugin, load_design_data, summarize_design_data, write_stage_json


class StepD1Plugin(DesignStagePlugin):
    stage_number = 1
    stage_name = "Project Portrait"

    def execute(self, context: StageContext) -> StageResult:
        data = load_design_data()
        summary = summarize_design_data(data)
        config = load_config()
        project_settings = config.project_settings
        app_config = config.app_config
        portrait = {
            "schema_version": 1,
            "stage_id": self.stage_id,
            "project_name": app_config.get("project", {}).get("name", "AutoDesignMaker"),
            "project_version": app_config.get("project", {}).get("version", ""),
            "business_model": "internal production tool",
            "platform": ["Windows", "Python CLI", "Tkinter GUI"],
            "target_audience": "game designers, technical designers, and Unity developers",
            "development_path": project_settings.get("development_path", ""),
            "unity_editor_path": project_settings.get("editor_path", ""),
            "design_domain_count": summary["domainCount"],
            "design_node_count": summary["nodeCount"],
            "checklist_count": summary["checklistCount"],
            "option_group_count": summary["optionGroupCount"],
            "option_count": summary["optionCount"],
            "validation_error_count": summary["validationErrorCount"],
            "validation_warning_count": summary["validationWarningCount"],
            "data_source": summary["dataSource"],
        }
        output_path = write_stage_json(context, "design_portrait.json", portrait)
        summary_path = write_stage_json(
            context,
            "design_stage_summary.json",
            {
                "stageId": self.stage_id,
                "title": self.stage_name,
                "portrait": output_path,
                **{key: value for key, value in summary.items() if key != "domains"},
            },
        )
        return StageResult(
            status="success",
            outputs={
                "designPortrait": output_path,
                "designStageSummary": summary_path,
                "fieldCount": len(portrait),
                **{key: value for key, value in summary.items() if key != "domains"},
            },
        )
