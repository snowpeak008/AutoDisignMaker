from copy import deepcopy

from design_tool.ai_prompt_packer import build_prompt_text
from design_tool.framework_memory import ensure_project_memory, prompt_snapshot_for_project
from design_tool.prompt_framework import compose_prompt_framework


SUMMARY_LIST_FIELDS = {
    "confirmedIntent",
    "openQuestions",
    "rejectedAssumptions",
    "lastUserCorrections",
}


def build_summary_correction_prompt(project_state, runtime_root, turn_id):
    memory_state = ensure_project_memory(project_state, runtime_root)
    prompt_snapshot = prompt_snapshot_for_project(project_state, runtime_root)
    prompt_framework = compose_prompt_framework(runtime_root)
    ai_state = project_state.get("aiInterview", {})
    current_summary = deepcopy(ai_state.get("summary", {}).get("v1", {}))
    recent_messages = ai_state.get("messages", [])[-20:]
    prompt_payload = {
        "turnId": turn_id,
        "task": "commercial_game_design_interview_summary_correction",
        "schemaMode": "summary",
        "promptFramework": {
            "snapshot": prompt_snapshot,
            "rules": prompt_framework.get("rules", []),
            "visibility": "hidden_to_user",
            "designOptionFrameworkMutation": "forbidden",
        },
        "projectName": project_state.get("projectName", ""),
        "profile": project_state.get("profile", {}),
        "projectMemoryId": memory_state.get("projectMemoryId", ""),
        "evaluationBatchId": memory_state.get("evaluationBatchId", ""),
        "currentSummary": current_summary,
        "recentMessages": recent_messages,
        "summaryRequirements": [
            "只修正 summary，不要新增设计框架项。",
            "保留 schemaVersion、confirmedIntent、openQuestions、rejectedAssumptions、nodeNotes、lastUserCorrections、mdaProgress、updatedAt。",
            "删除明显重复或互相矛盾的摘要项；不要把未确认内容写入 confirmedIntent。",
            "返回 mode=summary_correction 和 summary。",
        ],
    }
    return build_prompt_text(prompt_snapshot, prompt_payload)


def validate_summary_payload(payload):
    errors = []
    if not isinstance(payload, dict):
        return ["summary payload 不是 JSON 对象。"]
    if payload.get("mode") not in {"summary_correction", "maintenance", "error"}:
        errors.append(f"summary mode 非法：{payload.get('mode')}")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary 必须是对象。")
        return errors
    for field in SUMMARY_LIST_FIELDS:
        if not isinstance(summary.get(field, []), list):
            errors.append(f"summary.{field} 必须是数组。")
    if not isinstance(summary.get("nodeNotes", {}), dict):
        errors.append("summary.nodeNotes 必须是对象。")
    if not isinstance(summary.get("mdaProgress", {}), dict):
        errors.append("summary.mdaProgress 必须是对象。")
    return errors
