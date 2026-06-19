from core.context import StageContext, StageResult
from pipeline._design_base import DesignStagePlugin, load_design_data, summarize_design_data, write_stage_json


class Plugin(DesignStagePlugin):
    stage_number = 2
    stage_name = "Design Decisions"

    def execute(self, context: StageContext) -> StageResult:
        data = load_design_data()
        summary = summarize_design_data(data)
        domains = []
        for domain in summary["domains"]:
            status = "completed"
            if domain["nodeCount"] == 0 or domain["checklistCount"] == 0:
                status = "partial"
            domains.append({**domain, "status": status})

        payload = {
            "schema_version": 1,
            "stage_id": self.stage_id,
            "coverage": 1.0 if summary["validationErrorCount"] == 0 and domains else 0.0,
            "domain_count": summary["domainCount"],
            "node_count": summary["nodeCount"],
            "checklist_count": summary["checklistCount"],
            "option_group_count": summary["optionGroupCount"],
            "option_count": summary["optionCount"],
            "domains": domains,
        }
        output_path = write_stage_json(context, "design_domains.json", payload)
        summary_path = write_stage_json(
            context,
            "design_stage_summary.json",
            {
                "stageId": self.stage_id,
                "title": self.stage_name,
                "designDomains": output_path,
                **{key: value for key, value in summary.items() if key != "domains"},
            },
        )
        return StageResult(
            status="success",
            outputs={
                "designDomains": output_path,
                "designStageSummary": summary_path,
                "domainCount": summary["domainCount"],
                "coverage": payload["coverage"],
            },
        )
