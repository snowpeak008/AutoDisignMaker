"""Design stage plugins that bridge the migrated design engine into the pipeline."""

from __future__ import annotations

import json
from typing import Any

from src.core.context import StageContext, StageResult
from src.core.stage_plugin import StagePlugin


def write_stage_json(context: StageContext, filename: str, payload: dict[str, Any]) -> str:
    path = context.artifact_dir / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_design_data() -> dict[str, Any]:
    from design_tool.data_loader import load_project_data

    return load_project_data()


def summarize_design_data(data: dict[str, Any]) -> dict[str, Any]:
    domains = data.get("domains", [])
    if not isinstance(domains, list):
        domains = []

    node_count = 0
    checklist_count = 0
    option_group_count = 0
    option_count = 0
    domain_summaries: list[dict[str, Any]] = []
    for item in domains:
        if not isinstance(item, dict):
            continue
        domain = item.get("domain", {})
        nodes = item.get("nodes", [])
        if not isinstance(domain, dict):
            domain = {}
        if not isinstance(nodes, list):
            nodes = []
        domain_node_count = len(nodes)
        domain_checklist_count = 0
        domain_option_group_count = 0
        domain_option_count = 0
        for node in nodes:
            if not isinstance(node, dict):
                continue
            checklist = node.get("checklist", [])
            if not isinstance(checklist, list):
                continue
            domain_checklist_count += len(checklist)
            for entry in checklist:
                if not isinstance(entry, dict):
                    continue
                groups = entry.get("optionGroups", [])
                if not isinstance(groups, list):
                    continue
                domain_option_group_count += len(groups)
                for group in groups:
                    if isinstance(group, dict) and isinstance(group.get("options"), list):
                        domain_option_count += len(group["options"])
        node_count += domain_node_count
        checklist_count += domain_checklist_count
        option_group_count += domain_option_group_count
        option_count += domain_option_count
        domain_summaries.append(
            {
                "id": str(domain.get("id") or ""),
                "name": str(domain.get("name") or ""),
                "priority": str(domain.get("priority") or ""),
                "activation": str(domain.get("activation") or ""),
                "nodeCount": domain_node_count,
                "checklistCount": domain_checklist_count,
                "optionGroupCount": domain_option_group_count,
                "optionCount": domain_option_count,
            }
        )

    meta = data.get("_meta", {})
    if not isinstance(meta, dict):
        meta = {}
    return {
        "domainCount": len(domains),
        "nodeCount": node_count,
        "checklistCount": checklist_count,
        "optionGroupCount": option_group_count,
        "optionCount": option_count,
        "validationErrorCount": len(meta.get("validationErrors", [])),
        "validationWarningCount": len(meta.get("validationWarnings", [])),
        "dataSource": str(meta.get("dataSource") or ""),
        "domains": domain_summaries,
    }


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
        data = load_design_data()
        data_summary = summarize_design_data(data)
        summary: dict[str, Any] = {
            "stageId": self.stage_id,
            "title": self.stage_name,
            **{key: value for key, value in data_summary.items() if key != "domains"},
        }
        write_stage_json(context, "design_stage_summary.json", summary)
        return StageResult(status="success", outputs=summary)
