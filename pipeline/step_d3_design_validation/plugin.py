from core.context import StageContext, StageResult
from pipeline._design_base import DesignStagePlugin, load_design_data, summarize_design_data, write_stage_json


class Plugin(DesignStagePlugin):
    stage_number = 3
    stage_name = "Design Validation"

    def execute(self, context: StageContext) -> StageResult:
        data = load_design_data()
        summary = summarize_design_data(data)
        meta = data.get("_meta", {})
        if not isinstance(meta, dict):
            meta = {}

        conflicts = []
        incomplete_domains = [
            domain
            for domain in summary["domains"]
            if domain["nodeCount"] == 0 or domain["checklistCount"] == 0 or domain["optionGroupCount"] == 0
        ]
        if incomplete_domains:
            conflicts.append(
                {
                    "id": "D3-INCOMPLETE-DOMAINS",
                    "severity": "warning",
                    "message": "One or more domains have no nodes, checklist entries, or option groups.",
                    "domainIds": [domain["id"] for domain in incomplete_domains],
                }
            )

        validation_errors = list(meta.get("validationErrors", []))
        validation_warnings = list(meta.get("validationWarnings", []))
        coverage = {
            "domains": summary["domainCount"],
            "nodes": summary["nodeCount"],
            "checklist": summary["checklistCount"],
            "optionGroups": summary["optionGroupCount"],
            "options": summary["optionCount"],
            "domainsWithChecklist": summary["domainCount"] - len(incomplete_domains),
            "coverageRatio": 1.0 if summary["domainCount"] and not incomplete_domains else 0.0,
        }
        report = {
            "schema_version": 1,
            "stage_id": self.stage_id,
            "status": "passed" if not validation_errors and not conflicts else "blocked",
            "valid": not validation_errors and not conflicts,
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
            "conflicts": conflicts,
            "coverage": coverage,
            "data_source": summary["dataSource"],
        }
        output_path = write_stage_json(context, "design_validation_report.json", report)
        summary_path = write_stage_json(
            context,
            "design_stage_summary.json",
            {
                "stageId": self.stage_id,
                "title": self.stage_name,
                "designValidationReport": output_path,
                **{key: value for key, value in summary.items() if key != "domains"},
            },
        )
        status = "success" if report["valid"] else "failed"
        return StageResult(
            status=status,
            outputs={
                "designValidationReport": output_path,
                "designStageSummary": summary_path,
                "valid": report["valid"],
                "coverage": coverage,
                "conflictCount": len(conflicts),
                "validationErrorCount": len(validation_errors),
                "validationWarningCount": len(validation_warnings),
            },
            errors=[str(error) for error in validation_errors],
            warnings=[item["message"] for item in conflicts] + [str(item) for item in validation_warnings],
        )
