from core.design.ai_interview import (
    CANDIDATE_NODE_LIMIT,
    compact_project_summary,
    conversation_summary,
    framework_context,
    mda_progress_for_count,
    project_digest,
    recent_messages,
)
from core.design.ai_prompt_packer import build_prompt_text, stable_hash
from core.design.ai_route_planner import candidate_node_ids, text_tokens
from core.design.framework_memory import ensure_project_memory, prompt_snapshot_for_project
from core.design.prompt_framework import compose_prompt_framework


def explicit_option_signal(engine, user_text):
    tokens = text_tokens(user_text)
    if not tokens:
        return False
    text = str(user_text or "").lower()
    for node in engine.nodes:
        for item in node.get("checklist", []):
            for group in item.get("optionGroups", []):
                for option in group.get("options", []):
                    label = str(option.get("label", "")).strip().lower()
                    option_id = str(option.get("id", "")).strip().lower()
                    if label and len(label) >= 2 and label in text:
                        return True
                    if option_id and option_id in tokens:
                        return True
    return False


def readiness_near(ai_state, window=2, interval=10):
    try:
        count = int(ai_state.get("questionGroupCount", 0) or 0)
    except (TypeError, ValueError):
        return False
    if count <= 0:
        return False
    remaining = interval - (count % interval)
    return remaining <= window or remaining == interval


def should_schedule_mapping(engine, project_state, user_text, force_output=False):
    if force_output:
        return False
    ai_state = project_state.get("aiInterview", {})
    return explicit_option_signal(engine, user_text) or readiness_near(ai_state)


def build_mapping_prompt(engine, project_state, user_text, runtime_root, turn_id):
    memory_state = ensure_project_memory(project_state, runtime_root)
    prompt_snapshot = prompt_snapshot_for_project(project_state, runtime_root)
    prompt_framework = compose_prompt_framework(runtime_root)
    ai_state = project_state.get("aiInterview", {})
    ai_state.setdefault("summary", {})
    conversation_summary(ai_state)["mdaProgress"] = mda_progress_for_count(ai_state.get("questionGroupCount", 0))
    candidate_ids = candidate_node_ids(engine, project_state, ai_state, user_text, limit=CANDIDATE_NODE_LIMIT)
    prompt_payload = {
        "turnId": turn_id,
        "task": "commercial_game_design_background_mapping",
        "schemaMode": "mapping",
        "promptFramework": {
            "snapshot": prompt_snapshot,
            "rules": prompt_framework.get("rules", []),
            "visibility": "hidden_to_user",
            "designOptionFrameworkMutation": "forbidden",
        },
        "projectSummary": compact_project_summary(engine, project_state),
        "projectDigest": project_digest(engine, project_state, minimal=True),
        "conversationSummary": conversation_summary(ai_state),
        "questionGroupCount": ai_state.get("questionGroupCount", 0),
        "evaluationBatchId": memory_state.get("evaluationBatchId", ""),
        "projectMemoryId": memory_state.get("projectMemoryId", ""),
        "recentMessages": recent_messages(ai_state, 6),
        "frameworkContext": framework_context(
            engine,
            project_state,
            include_full=False,
            candidate_ids=candidate_ids,
            node_limit=CANDIDATE_NODE_LIMIT,
        ),
        "userMessage": str(user_text or ""),
        "mappingRequirements": [
            "只返回 mode=mapping 和 inferences。",
            "只能映射到 frameworkContext 中出现的现有 nodeId/itemId/groupId/optionIds。",
            "证据不足时返回空 inferences，不要猜测。",
            "0.75 及以上才可作为高置信；多义时降低置信度。",
        ],
    }
    return build_prompt_text(prompt_snapshot, prompt_payload)


def project_state_hash(engine, project_state):
    return stable_hash(project_digest(engine, project_state, minimal=True))


def validate_mapping_payload(engine, payload):
    errors = []
    if not isinstance(payload, dict):
        return ["mapping payload 不是 JSON 对象。"]
    if payload.get("mode") not in {"mapping", "maintenance", "error"}:
        errors.append(f"mapping mode 非法：{payload.get('mode')}")
    inferences = payload.get("inferences", [])
    if not isinstance(inferences, list):
        errors.append("mapping inferences 必须是数组。")
        return errors
    for inference in inferences:
        if not isinstance(inference, dict):
            errors.append("mapping inference 必须是对象。")
            continue
        node_id = inference.get("nodeId", "")
        item_id = inference.get("itemId", "")
        group_id = inference.get("groupId", "")
        node = engine.node_by_id.get(node_id)
        if not node:
            errors.append(f"mapping 包含未知节点：{node_id}")
            continue
        item = engine.item_by_id(node_id, item_id)
        if not item:
            errors.append(f"mapping 包含未知 checklist：{node_id}/{item_id}")
            continue
        group = engine.group_by_id(node_id, item_id, group_id)
        if not group:
            errors.append(f"mapping 包含未知 L4 组：{node_id}/{item_id}/{group_id}")
            continue
        allowed = {option.get("id") for option in group.get("options", [])}
        invalid = [option_id for option_id in inference.get("optionIds", []) if option_id not in allowed]
        if invalid:
            errors.append(f"mapping 包含未知选项：{node_id}/{item_id}/{group_id}: {', '.join(invalid[:6])}")
    return errors
