"""Design stage plugins that bridge the migrated design engine into the pipeline."""

from __future__ import annotations

import json
from typing import Any

from src.core.context import StageContext, StageResult
from src.core.stage_plugin import StagePlugin


class DesignStagePlugin(StagePlugin):
    stage_number = 0
    stage_name = "design"

    @property
    def stage_id(self) -> str:
        return f"D{self.stage_number}"

    @property
    def title(self) -> str:
        return self.stage_name

    def execute(self, context: StageContext) -> StageResult:
        from design_tool.data_loader import load_project_data

        data = load_project_data()
        artifact_dir = context.artifact_dir
        summary: dict[str, Any] = {
            "stageId": self.stage_id,
            "title": self.stage_name,
            "domainCount": len(data.get("domains", [])),
            "validationErrorCount": len(data.get("_meta", {}).get("validationErrors", [])),
            "validationWarningCount": len(data.get("_meta", {}).get("validationWarnings", [])),
            "dataSource": data.get("_meta", {}).get("dataSource", ""),
        }
        (artifact_dir / "design_stage_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return StageResult(status="success", outputs=summary)

