import json
import os
import re
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from core.design.ai_prompt_packer import (
    build_prompt_text,
    compact_json,
    prompt_replay_fields,
    prompt_section_sizes,
    stable_hash,
)
from core.design.ai_memory_retriever import retrieved_memory_context
from core.design.ai_route_planner import candidate_node_ids as route_candidate_node_ids
from core.design.data_loader import runtime_project_root
from core.design.framework_memory import ensure_project_memory, prompt_snapshot_for_project
from core.design.prompt_framework import compose_prompt_framework


AI_INTERVIEW_SCHEMA_VERSION = "1.0"
HIGH_CONFIDENCE_THRESHOLD = 0.75
CLARIFICATION_CONFIDENCE_THRESHOLD = 0.45
QUESTION_GROUP_CHECK_INTERVAL = 10
MAX_QUESTION_GROUP_SIZE = 4
RECENT_MESSAGE_LIMIT_TURN = 6
RECENT_MESSAGE_LIMIT_FULL = 12
CANDIDATE_NODE_LIMIT = 5
CANDIDATE_NODE_MIN_LIMIT = 3
PROMPT_CHAR_BUDGET_TURN = 16000
OUTPUT_PARTITION_PROMPT_BUDGET = 130000
OUTPUT_PARTITION_CANDIDATE_COUNTS = (4, 8, 16)
SUMMARY_SCHEMA_VERSION = "1.0"

MDA_STAGES = [
    ("aesthetics", "体验目标"),
    ("dynamics", "玩家动态"),
    ("mechanics", "机制抓手"),
    ("constraints", "边界约束"),
    ("evidence", "验收信号"),
]

CONCRETE_ROLE_CLASSES = {"system_concrete", "content_concrete"}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def new_memory_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def empty_conversation_summary_v1():
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "confirmedIntent": [],
        "openQuestions": [],
        "rejectedAssumptions": [],
        "nodeNotes": {},
        "lastUserCorrections": [],
        "mdaProgress": {stage_id: "pending" for stage_id, _ in MDA_STAGES},
        "updatedAt": now_iso(),
    }


def empty_ai_interview_state():
    return {
        "schemaVersion": AI_INTERVIEW_SCHEMA_VERSION,
        "codexSessionId": "",
        "sessionTurnCount": 0,
        "status": "idle",
        "activeTurnId": "",
        "runStartedAt": "",
        "backendStage": "idle",
        "backendStartedAt": "",
        "lastBackendDurationSeconds": 0.0,
        "lastFirstEventSeconds": None,
        "questionGroupCount": 0,
        "lastReadinessCheckGroup": 0,
        "currentQuestionText": "",
        "currentQuestionTurnId": "",
        "currentQuestionCount": 0,
        "awaitingUserAnswer": False,
        "interviewArchiveId": "",
        "autoArchivePath": "",
        "lastManualArchivePath": "",
        "lastArchivedAt": "",
        "routeOverview": {
            "currentMdaStage": MDA_STAGES[0][1],
            "expectedDomains": [],
            "completedNodes": [],
            "clarificationTargets": [],
            "lowApplicabilityCandidates": [],
        },
        "messages": [],
        "summary": {
            "v1": empty_conversation_summary_v1(),
        },
        "inferences": [],
        "recentQuestionTargets": [],
        "applicabilityScores": {},
        "frameworkMemory": {
            "projectMemoryId": new_memory_id("project"),
            "evaluationBatchId": "",
            "batchStatus": "idle",
            "promptVersionSnapshot": {},
            "lastCompletedBatchId": "",
            "reviewChains": {},
            "updatedAt": now_iso(),
        },
        "outputHistory": [],
        "optionDifferences": [],
        "lastError": "",
        "updatedAt": now_iso(),
    }


def normalize_ai_interview_state(value):
    state = deepcopy(value) if isinstance(value, dict) else {}
    base = empty_ai_interview_state()
    for key, default_value in base.items():
        state.setdefault(key, deepcopy(default_value))
    if not isinstance(state.get("messages"), list):
        state["messages"] = []
    if not isinstance(state.get("summary"), dict):
        state["summary"] = deepcopy(base["summary"])
    summary = state["summary"].setdefault("v1", empty_conversation_summary_v1())
    if not isinstance(summary, dict):
        state["summary"]["v1"] = empty_conversation_summary_v1()
        summary = state["summary"]["v1"]
    default_summary = empty_conversation_summary_v1()
    for key, default_value in default_summary.items():
        summary.setdefault(key, deepcopy(default_value))
    if not isinstance(summary.get("confirmedIntent"), list):
        summary["confirmedIntent"] = []
    if not isinstance(summary.get("openQuestions"), list):
        summary["openQuestions"] = []
    if not isinstance(summary.get("rejectedAssumptions"), list):
        summary["rejectedAssumptions"] = []
    if not isinstance(summary.get("nodeNotes"), dict):
        summary["nodeNotes"] = {}
    if not isinstance(summary.get("lastUserCorrections"), list):
        summary["lastUserCorrections"] = []
    if not isinstance(summary.get("mdaProgress"), dict):
        summary["mdaProgress"] = deepcopy(default_summary["mdaProgress"])
    if not isinstance(state.get("inferences"), list):
        state["inferences"] = []
    if not isinstance(state.get("recentQuestionTargets"), list):
        state["recentQuestionTargets"] = []
    if not isinstance(state.get("applicabilityScores"), dict):
        state["applicabilityScores"] = {}
    if not isinstance(state.get("frameworkMemory"), dict):
        state["frameworkMemory"] = deepcopy(base["frameworkMemory"])
    memory = state["frameworkMemory"]
    if not memory.get("projectMemoryId"):
        memory["projectMemoryId"] = new_memory_id("project")
    memory.setdefault("evaluationBatchId", "")
    memory.setdefault("batchStatus", "idle")
    memory.setdefault("promptVersionSnapshot", {})
    memory.setdefault("lastCompletedBatchId", "")
    memory.setdefault("reviewChains", {})
    memory.setdefault("updatedAt", now_iso())
    if not isinstance(state.get("outputHistory"), list):
        state["outputHistory"] = []
    if not isinstance(state.get("optionDifferences"), list):
        state["optionDifferences"] = []
    try:
        state["questionGroupCount"] = int(state.get("questionGroupCount", 0) or 0)
    except (TypeError, ValueError):
        state["questionGroupCount"] = 0
    try:
        state["lastReadinessCheckGroup"] = int(state.get("lastReadinessCheckGroup", 0) or 0)
    except (TypeError, ValueError):
        state["lastReadinessCheckGroup"] = 0
    try:
        state["sessionTurnCount"] = int(state.get("sessionTurnCount", 0) or 0)
    except (TypeError, ValueError):
        state["sessionTurnCount"] = 0
    summary["mdaProgress"] = mda_progress_for_count(state["questionGroupCount"])
    state["schemaVersion"] = AI_INTERVIEW_SCHEMA_VERSION
    return state


def ensure_ai_interview(project_state):
    project_state["aiInterview"] = normalize_ai_interview_state(project_state.get("aiInterview"))
    return project_state["aiInterview"]


def mda_progress_for_count(group_count):
    try:
        group_count = int(group_count or 0)
    except (TypeError, ValueError):
        group_count = 0
    stage_count = len(MDA_STAGES)
    current_index = group_count % stage_count if stage_count else 0
    completed_cycle = group_count >= stage_count
    progress = {}
    for index, (stage_id, _) in enumerate(MDA_STAGES):
        if index == current_index:
            progress[stage_id] = "in_progress"
        elif completed_cycle or index < current_index:
            progress[stage_id] = "explored"
        else:
            progress[stage_id] = "pending"
    return progress


def conversation_summary(ai_state):
    if not isinstance(ai_state.get("summary"), dict):
        ai_state["summary"] = {"v1": empty_conversation_summary_v1()}
    summary = ai_state["summary"].setdefault("v1", empty_conversation_summary_v1())
    if not isinstance(summary, dict):
        summary = empty_conversation_summary_v1()
        ai_state["summary"]["v1"] = summary
    summary.setdefault("mdaProgress", mda_progress_for_count(ai_state.get("questionGroupCount", 0)))
    return summary


def short_text(value, limit=180):
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit]


def append_limited(items, item, limit):
    if not item:
        return
    items.append(item)
    if len(items) > limit:
        del items[:len(items) - limit]


def update_conversation_summary(project_state, payload=None, correction="", max_items=24):
    ai_state = ensure_ai_interview(project_state)
    summary = conversation_summary(ai_state)
    summary["mdaProgress"] = mda_progress_for_count(ai_state.get("questionGroupCount", 0))
    payload = payload if isinstance(payload, dict) else {}

    if correction:
        item = {
            "createdAt": now_iso(),
            "text": short_text(correction, 180),
        }
        append_limited(summary.setdefault("lastUserCorrections", []), item, 12)
        append_limited(summary.setdefault("rejectedAssumptions", []), item, 12)

    question_group = payload.get("questionGroup") if isinstance(payload.get("questionGroup"), dict) else None
    if question_group:
        target_ids = []
        for question in question_group.get("questions", []) or []:
            if isinstance(question, dict):
                target_ids.extend(str(item) for item in question.get("targetNodeIds", []) if item)
        open_item = {
            "createdAt": now_iso(),
            "purpose": short_text(question_group.get("purpose", ""), 120),
            "targetNodeIds": sorted(set(target_ids))[:8],
            "questions": [
                short_text(question.get("text", ""), 120)
                for question in question_group.get("questions", [])[:4]
                if isinstance(question, dict)
            ],
        }
        append_limited(summary.setdefault("openQuestions", []), open_item, 12)

    for inference in payload.get("inferences", []) or []:
        if not isinstance(inference, dict):
            continue
        try:
            confidence = float(inference.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        node_id = inference.get("nodeId", "")
        note = {
            "createdAt": now_iso(),
            "nodeId": node_id,
            "itemId": inference.get("itemId", ""),
            "groupId": inference.get("groupId", ""),
            "optionIds": list(inference.get("optionIds", []) or [])[:8],
            "confidence": round(confidence, 3),
            "reason": short_text(inference.get("reason", ""), 180),
            "notApplicable": bool(inference.get("notApplicable")),
        }
        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            append_limited(summary.setdefault("confirmedIntent", []), note, max_items)
        if node_id:
            node_notes = summary.setdefault("nodeNotes", {}).setdefault(node_id, [])
            append_limited(node_notes, note, 8)

    summary["updatedAt"] = now_iso()
    ai_state["updatedAt"] = now_iso()
    return summary


def ensure_ai_memory(project_state, runtime_root=None):
    root = runtime_root or runtime_project_root()
    return ensure_project_memory(project_state, root)


def add_message(ai_state, role, content, meta=None):
    message = {
        "role": role,
        "content": str(content or ""),
        "createdAt": now_iso(),
    }
    if meta:
        message["meta"] = deepcopy(meta)
    ai_state.setdefault("messages", []).append(message)
    ai_state["updatedAt"] = now_iso()
    return message


def text_tokens(value):
    text = str(value or "").lower()
    ascii_tokens = re.findall(r"[a-z0-9_]{2,}", text)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_tokens = []
    for chunk in cjk_chunks:
        cjk_tokens.extend(chunk[index:index + 2] for index in range(max(1, len(chunk) - 1)))
    return {token for token in ascii_tokens + cjk_tokens if token}


def selected_groups_for_node(node, node_state):
    selected_items = []
    checklist_options = node_state.get("checklistOptions", {})
    for item in node.get("checklist", []):
        item_id = item.get("id", "")
        item_options = checklist_options.get(item_id, {})
        groups = []
        for group in item.get("optionGroups", []):
            group_id = group.get("id", "")
            group_state = item_options.get(group_id, {})
            selected = list(group_state.get("selected", []) or [])
            if not selected:
                continue
            groups.append({
                "groupId": group_id,
                "selected": selected,
                "primary": group_state.get("primary", ""),
            })
        if node_state.get("checklist", {}).get(item_id) or groups:
            selected_items.append({
                "itemId": item_id,
                "label": item.get("label", item_id),
                "groups": groups,
            })
    return selected_items


def compact_node_state(engine, node, project_state, minimal=False):
    node_state = project_state.get("nodes", {}).get(node["id"], {})
    effective = engine.effective_node_state(node, project_state)
    selected_items = selected_groups_for_node(node, node_state)
    has_note = bool(node_state.get("designNote", "").strip())
    has_risk = bool(node_state.get("riskNote", "").strip())
    has_not_applicable = node_state.get("decisionState") == "not_applicable"
    design_entities = node_state.get("designEntities", [])
    has_entities = bool(design_entities)
    if (
        effective == "not_started"
        and not selected_items
        and not has_note
        and not has_risk
        and not has_not_applicable
        and not has_entities
    ):
        return None
    payload = {
        "nodeId": node["id"],
        "name": node.get("name", node["id"]),
        "domain": node.get("domain", ""),
        "roleClass": node.get("roleClass", ""),
        "decisionState": node_state.get("decisionState", "not_started"),
        "effectiveState": effective,
    }
    if selected_items:
        payload["selectedItems"] = selected_items[:4 if minimal else 8]
    if has_risk:
        payload["riskNote"] = short_text(node_state.get("riskNote", ""), 120 if minimal else 240)
    if has_not_applicable:
        payload["notApplicableReason"] = short_text(node_state.get("notApplicableReason", ""), 120 if minimal else 240)
    if has_note and not minimal:
        payload["designNote"] = short_text(node_state.get("designNote", ""), 240)
    if has_entities:
        payload["designEntities"] = [
            {
                "kind": entity.get("kind", ""),
                "schema": entity.get("schema", ""),
                "id": entity.get("id", ""),
                "label": entity.get("label", ""),
            }
            for entity in design_entities[:2 if minimal else 4]
            if isinstance(entity, dict)
        ]
    return payload


def project_digest(engine, project_state, minimal=False):
    ai_state = ensure_ai_interview(project_state)
    coverage = engine.project_coverage(project_state)
    l4 = engine.project_l4_progress(project_state)
    non_default_nodes = []
    for node in engine.nodes:
        compact = compact_node_state(engine, node, project_state, minimal=minimal)
        if compact:
            non_default_nodes.append(compact)
    clarification = ai_state.get("routeOverview", {}).get("clarificationTargets", [])
    applicability = []
    for node_id, entry in (ai_state.get("applicabilityScores", {}) or {}).items():
        try:
            evidence_count = int(entry.get("evidenceCount", 0) or 0)
            score = float(entry.get("score", 0.5))
        except (TypeError, ValueError):
            continue
        if evidence_count:
            applicability.append({
                "nodeId": node_id,
                "score": round(score, 3),
                "evidenceCount": evidence_count,
                "reason": short_text(entry.get("reason", ""), 120),
            })
    return {
        "projectName": project_state.get("projectName", ""),
        "profile": project_state.get("profile", {}),
        "coverage": coverage,
        "l4Progress": l4,
        "focusDomainIds": sorted(engine.profile_focus_domains(project_state)),
        "nonDefaultNodes": non_default_nodes[:8 if minimal else 16],
        "clarificationTargets": clarification[:6 if minimal else 12],
        "recentInferences": ai_state.get("inferences", [])[-4 if minimal else -8:],
        "applicabilityHighlights": applicability[:8 if minimal else 16],
    }


def recent_question_target_ids(ai_state, limit=3):
    target_ids = []
    for entry in ai_state.get("recentQuestionTargets", [])[-limit:]:
        if isinstance(entry, dict):
            target_ids.extend(str(item) for item in entry.get("nodeIds", []) if item)
        elif isinstance(entry, str):
            target_ids.append(entry)
    return set(target_ids)


def candidate_node_ids(engine, project_state, user_text, limit=CANDIDATE_NODE_LIMIT):
    ai_state = ensure_ai_interview(project_state)
    return route_candidate_node_ids(engine, project_state, ai_state, user_text, limit=limit)


def node_applicability_entry(ai_state, node_id):
    scores = ai_state.setdefault("applicabilityScores", {})
    entry = scores.setdefault(node_id, {
        "score": 0.5,
        "evidenceCount": 0,
        "reason": "",
        "updatedAt": now_iso(),
    })
    try:
        entry["score"] = float(entry.get("score", 0.5))
    except (TypeError, ValueError):
        entry["score"] = 0.5
    try:
        entry["evidenceCount"] = int(entry.get("evidenceCount", 0))
    except (TypeError, ValueError):
        entry["evidenceCount"] = 0
    return entry


def node_applicability_score(ai_state, node_id):
    return node_applicability_entry(ai_state, node_id).get("score", 0.5)


def update_applicability_scores(project_state, inferences):
    ai_state = ensure_ai_interview(project_state)
    for inference in inferences or []:
        if not isinstance(inference, dict):
            continue
        node_id = inference.get("nodeId", "")
        if not node_id:
            continue
        entry = node_applicability_entry(ai_state, node_id)
        score = inference.get("applicabilityScore")
        if score is None:
            try:
                confidence = float(inference.get("confidence", 0) or 0)
            except (TypeError, ValueError):
                confidence = 0
            if inference.get("notApplicable"):
                score = max(0.0, 1.0 - confidence)
            elif inference.get("optionIds"):
                score = max(entry["score"], confidence)
            else:
                continue
        try:
            score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            continue
        evidence_count = entry.get("evidenceCount", 0) + 1
        entry["score"] = round(((entry["score"] * entry.get("evidenceCount", 0)) + score) / evidence_count, 3)
        entry["evidenceCount"] = evidence_count
        entry["reason"] = inference.get("applicabilityReason") or inference.get("reason", entry.get("reason", ""))
        entry["updatedAt"] = now_iso()
    ai_state["updatedAt"] = now_iso()


def update_route_overview(engine, project_state):
    ai_state = ensure_ai_interview(project_state)
    stage_index = ai_state.get("questionGroupCount", 0) % len(MDA_STAGES)
    current_stage = MDA_STAGES[stage_index][1]
    focus_ids = sorted(engine.profile_focus_domains(project_state))
    if not focus_ids:
        focus_ids = [domain_doc["domain"]["id"] for domain_doc in engine.domains[:4]]
    focus_names = [
        engine.domain_by_id[domain_id]["domain"]["name"]
        for domain_id in focus_ids
        if domain_id in engine.domain_by_id
    ]
    completed = []
    low_applicability = []
    clarification = []
    for node in engine.nodes:
        node_state = project_state.get("nodes", {}).get(node["id"], {})
        effective = engine.effective_node_state(node, project_state)
        score_entry = node_applicability_entry(ai_state, node["id"])
        score = score_entry.get("score", 0.5)
        evidence_count = score_entry.get("evidenceCount", 0)
        if effective in ("completed", "not_applicable"):
            completed.append(node["name"])
        elif node_state.get("riskNote", "").strip() or (evidence_count and 0.35 <= score < 0.75):
            clarification.append(node["name"])
        if node_state.get("decisionState") == "not_applicable" or (evidence_count and score < 0.35):
            low_applicability.append(f"{node['name']}（{score:.2f}）")
    overview = {
        "currentMdaStage": current_stage,
        "expectedDomains": focus_names,
        "completedNodes": completed[:12],
        "clarificationTargets": clarification[:12],
        "lowApplicabilityCandidates": low_applicability[:12],
    }
    ai_state["routeOverview"] = overview
    ai_state["updatedAt"] = now_iso()
    return overview


def detect_force_output(user_text):
    text = str(user_text or "")
    return any(keyword in text for keyword in ("输出", "生成完整", "生成方案", "完整方案", "全项目输出"))


def compact_project_summary(engine, project_state):
    coverage = engine.project_coverage(project_state)
    l4 = engine.project_l4_progress(project_state)
    return {
        "projectName": project_state.get("projectName", ""),
        "profile": project_state.get("profile", {}),
        "coverage": coverage,
        "l4Progress": l4,
        "focusDomainIds": sorted(engine.profile_focus_domains(project_state)),
    }


def entity_schema_summaries(engine, compact=False):
    registry = getattr(engine, "entity_schema_registry", None)
    schemas = getattr(registry, "schemas_by_id", {}) if registry else {}
    summaries = []
    for schema_id, schema in sorted(schemas.items()):
        required = list(schema.get("required", []))
        properties = list((schema.get("properties", {}) or {}).keys())
        optional = [
            key for key in properties
            if key not in required and not key.startswith("$") and not key.startswith("_")
        ]
        payload = {
            "id": schema_id,
            "kind": schema.get("kind", ""),
            "schemaVersion": schema.get("schemaVersion", ""),
            "required": required,
        }
        if not compact:
            payload["optional"] = optional[:10]
        summaries.append(payload)
    return summaries


def concrete_entity_prompt(engine, compact=False):
    return {
        "writeField": "designEntities",
        "validation": "schema_required_fields_must_pass_before_write",
        "allowedSchemas": entity_schema_summaries(engine, compact=compact),
    }


def node_context(
    engine,
    node,
    include_options=False,
    compact=False,
    mda_stage_id="",
    option_description_limit=None,
):
    checklist = []
    items = node.get("checklist", [])
    if compact:
        items = items[:4]
    for item in items:
        groups = []
        option_groups = item.get("optionGroups", [])
        if compact:
            stage_groups = [group for group in option_groups if group.get("mdaLayer", "") == mda_stage_id]
            option_groups = stage_groups or option_groups[:1]
        for group in option_groups:
            group_payload = {
                "id": group.get("id", ""),
                "label": group.get("label", ""),
                "required": bool(group.get("required")),
                "selectionMode": group.get("selectionMode", "multi"),
                "mdaLayer": group.get("mdaLayer", ""),
                "mdaLayerLabel": group.get("mdaLayerLabel", ""),
                "designQuestion": short_text(group.get("designQuestion", ""), 120) if compact else group.get("designQuestion", ""),
            }
            if include_options:
                group_payload["options"] = [
                    {
                        "id": option.get("id", ""),
                        "label": option.get("label", ""),
                        **(
                            {"description": short_text(option.get("description", ""), option_description_limit)}
                            if option_description_limit is not None
                            else {"description": option.get("description", "")}
                        ),
                    }
                    for option in group.get("options", [])
                ]
            groups.append(group_payload)
        item_payload = {
            "id": item.get("id", ""),
            "label": item.get("label", ""),
            "optionGroups": groups,
        }
        if not compact:
            item_payload["description"] = item.get("description", "")
        checklist.append(item_payload)
    payload = {
        "id": node.get("id", ""),
        "name": node.get("name", ""),
        "domain": node.get("domain", ""),
        "roleClass": node.get("roleClass", ""),
        "description": short_text(node.get("description", ""), 180) if compact else node.get("description", ""),
        "checklist": checklist,
    }
    if node.get("roleClass") in CONCRETE_ROLE_CLASSES:
        payload["designEntityPrompt"] = concrete_entity_prompt(engine, compact=compact)
    return payload


def framework_context(engine, project_state, include_full=False, candidate_ids=None, node_limit=8):
    ai_state = ensure_ai_interview(project_state)
    stage_index = ai_state.get("questionGroupCount", 0) % len(MDA_STAGES)
    current_stage_id = MDA_STAGES[stage_index][0]
    focus_ids = sorted(engine.profile_focus_domains(project_state))
    if not focus_ids:
        focus_ids = [domain_doc["domain"]["id"] for domain_doc in engine.domains[:4]]
    candidate_ids = list(candidate_ids or [])
    if include_full:
        domain_docs = engine.domains
    elif candidate_ids:
        domain_ids = []
        for node_id in candidate_ids:
            node = engine.node_by_id.get(node_id)
            if node and node.get("domain") not in domain_ids:
                domain_ids.append(node.get("domain"))
        domain_docs = [
            engine.domain_by_id[domain_id]
            for domain_id in domain_ids
            if domain_id in engine.domain_by_id
        ]
    else:
        domain_docs = [
            engine.domain_by_id[domain_id]
            for domain_id in focus_ids
            if domain_id in engine.domain_by_id
        ]
    context = []
    for domain_doc in domain_docs:
        domain = domain_doc["domain"]
        if candidate_ids:
            candidate_set = set(candidate_ids)
            nodes = [
                node
                for node_id in candidate_ids
                for node in [engine.node_by_id.get(node_id)]
                if node and node.get("domain") == domain.get("id") and node["id"] in candidate_set
            ]
        else:
            nodes = sorted(
                domain_doc.get("nodes", []),
                key=lambda node: node_applicability_score(ai_state, node["id"]),
                reverse=True,
            )
        if not include_full:
            nodes = nodes[:node_limit]
        context.append({
            "id": domain.get("id", ""),
            "name": domain.get("name", ""),
            "description": short_text(domain.get("description", ""), 180) if not include_full else domain.get("description", ""),
            "nodes": [
                node_context(
                    engine,
                    node,
                    include_options=include_full,
                    compact=not include_full,
                    mda_stage_id=current_stage_id,
                )
                for node in nodes
            ],
        })
    return context


def framework_context_for_domains(engine, domain_ids, include_options=True, compact_options=False):
    context = []
    for domain_id in domain_ids or []:
        domain_doc = engine.domain_by_id.get(domain_id)
        if not domain_doc:
            continue
        domain = domain_doc["domain"]
        context.append({
            "id": domain.get("id", ""),
            "name": domain.get("name", ""),
            "description": short_text(domain.get("description", ""), 180) if compact_options else domain.get("description", ""),
            "nodes": [
                node_context(
                    engine,
                    node,
                    include_options=include_options,
                    compact=False,
                    option_description_limit=48 if compact_options else None,
                )
                for node in domain_doc.get("nodes", [])
            ],
        })
    return context


def packed_framework_context_for_domains(engine, domain_ids):
    domains = []
    for domain_id in domain_ids or []:
        domain_doc = engine.domain_by_id.get(domain_id)
        if not domain_doc:
            continue
        domain = domain_doc["domain"]
        packed_nodes = []
        for node in domain_doc.get("nodes", []):
            packed_items = []
            for item in node.get("checklist", []):
                packed_groups = []
                for group in item.get("optionGroups", []):
                    packed_options = [
                        [option.get("id", ""), option.get("label", "")]
                        for option in group.get("options", [])
                    ]
                    packed_groups.append([
                        group.get("id", ""),
                        group.get("label", ""),
                        group.get("selectionMode", "multi"),
                        group.get("mdaLayer", ""),
                        short_text(group.get("designQuestion", ""), 100),
                        packed_options,
                    ])
                packed_items.append([
                    item.get("id", ""),
                    item.get("label", ""),
                    packed_groups,
                ])
            packed_nodes.append([
                node.get("id", ""),
                node.get("name", ""),
                node.get("domain", ""),
                node.get("roleClass", ""),
                short_text(node.get("description", ""), 140),
                entity_schema_summaries(engine, compact=True)
                if node.get("roleClass") in CONCRETE_ROLE_CLASSES else [],
                packed_items,
            ])
        domains.append([
            domain.get("id", ""),
            domain.get("name", ""),
            packed_nodes,
        ])
    return {
        "format": {
            "domain": ["id", "name", "nodes"],
            "node": ["id", "name", "domainId", "roleClass", "description", "entitySchemas", "items"],
            "item": ["id", "label", "groups"],
            "group": ["id", "label", "selectionMode", "mdaLayer", "designQuestion", "options"],
            "option": ["id", "label"],
        },
        "domains": domains,
    }


def project_state_for_domains(engine, project_state, domain_ids):
    domain_ids = set(domain_ids or [])
    nodes = {}
    for node in engine.nodes:
        if node.get("domain") in domain_ids:
            nodes[node["id"]] = deepcopy(project_state.get("nodes", {}).get(node["id"], {}))
    return {
        "projectName": project_state.get("projectName", ""),
        "profile": deepcopy(project_state.get("profile", {})),
        "nodes": nodes,
    }


def output_domain_partitions(engine, part_count=4):
    domain_ids = [domain_doc["domain"]["id"] for domain_doc in engine.domains]
    if not domain_ids:
        return []
    part_count = max(1, min(int(part_count or 1), len(domain_ids)))
    partitions = [[] for _ in range(part_count)]
    for index, domain_id in enumerate(domain_ids):
        partitions[index % part_count].append(domain_id)
    return [partition for partition in partitions if partition]


def output_partition_prompt_budget():
    try:
        return int(os.environ.get("AI_OUTPUT_PARTITION_PROMPT_BUDGET", OUTPUT_PARTITION_PROMPT_BUDGET))
    except (TypeError, ValueError):
        return OUTPUT_PARTITION_PROMPT_BUDGET


def choose_output_domain_partitions(engine, project_state, user_text, runtime_root=None, budget=None, candidate_counts=None):
    budget = budget or output_partition_prompt_budget()
    counts = tuple(candidate_counts or OUTPUT_PARTITION_CANDIDATE_COUNTS)
    best = None
    for count in counts:
        partitions = output_domain_partitions(engine, count)
        if not partitions:
            continue
        sizes = []
        for index, domain_ids in enumerate(partitions, start=1):
            prompt = build_output_partition_prompt(
                engine,
                project_state,
                user_text,
                domain_ids,
                partition_index=index,
                partition_count=len(partitions),
                runtime_root=runtime_root,
                turn_id=f"partition_plan_{count}_{index}",
                record=False,
            )
            sizes.append(len(prompt))
        plan = {
            "partitions": partitions,
            "promptBudget": budget,
            "promptSizes": sizes,
            "maxPromptChars": max(sizes) if sizes else 0,
            "avgPromptChars": round(sum(sizes) / len(sizes)) if sizes else 0,
        }
        best = plan
        if plan["maxPromptChars"] <= budget:
            return plan
    return best or {
        "partitions": [],
        "promptBudget": budget,
        "promptSizes": [],
        "maxPromptChars": 0,
        "avgPromptChars": 0,
    }


def recent_messages(ai_state, limit=20):
    return ai_state.get("messages", [])[-limit:]


def runtime_ai_dir(runtime_root):
    root = Path(runtime_root or runtime_project_root()) / "ai_runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root


def append_jsonl(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(compact_json(payload) + "\n")


def prompt_meter_entry(turn_id, schema_mode, output_mode, prompt_payload, prompt_text, degradations, ai_state):
    section_sizes = prompt_section_sizes(prompt_payload)
    response_schema_empty_fields = []
    if schema_mode == "turn":
        response_schema_empty_fields = ["fullProjectOutput", "optionDifferences"]
    elif schema_mode == "readiness":
        response_schema_empty_fields = ["questionGroup", "fullProjectOutput", "optionDifferences"]
    return {
        "turnId": turn_id,
        "createdAt": now_iso(),
        "schemaMode": schema_mode,
        "outputMode": output_mode,
        "promptChars": len(prompt_text),
        "promptEstimatedTokens": round(len(prompt_text) / 4),
        "sectionChars": section_sizes,
        "degradations": list(degradations or []),
        "responseSchemaEmptyFieldsRemoved": response_schema_empty_fields,
        "codexSessionId": ai_state.get("codexSessionId", ""),
        "sessionAccumulatedTurns": ai_state.get("sessionTurnCount", 0),
        "questionGroupCount": ai_state.get("questionGroupCount", 0),
    }


def record_prompt_meter(runtime_root, entry):
    append_jsonl(runtime_ai_dir(runtime_root) / "prompt_meter.jsonl", entry)
    return entry


def response_shape_metrics(payload):
    if not isinstance(payload, dict):
        return {
            "responseTopLevelFieldCount": 0,
            "responseEmptyFieldCount": 0,
            "responseEmptyFieldRatio": 0.0,
            "responseEmptyFields": [],
        }
    empty_fields = []
    for key, value in payload.items():
        if value in ("", None, [], {}):
            empty_fields.append(key)
    total = len(payload)
    return {
        "responseTopLevelFieldCount": total,
        "responseEmptyFieldCount": len(empty_fields),
        "responseEmptyFieldRatio": round(len(empty_fields) / total, 4) if total else 0.0,
        "responseEmptyFields": empty_fields,
    }


def record_prompt_runtime(runtime_root, turn_id, result=None, validation_seconds=0.0, apply_seconds=0.0, validation_errors=None, mode=""):
    payload = {
        "turnId": turn_id,
        "createdAt": now_iso(),
        "mode": mode,
        "validationSeconds": round(float(validation_seconds or 0.0), 4),
        "applySeconds": round(float(apply_seconds or 0.0), 4),
        "validationErrorCount": len(validation_errors or []),
    }
    if result is not None:
        payload.update({
            "codexDurationSeconds": round(float(getattr(result, "duration_seconds", 0.0) or 0.0), 4),
            "firstEventSeconds": (
                round(float(result.first_event_seconds), 4)
                if getattr(result, "first_event_seconds", None) is not None else None
            ),
            "responseChars": int(getattr(result, "response_chars", 0) or 0),
            "rawEventCount": len(getattr(result, "raw_events", []) or []),
            "sessionId": getattr(result, "session_id", ""),
            "apiProfile": getattr(result, "api_profile", ""),
            "apiModel": getattr(result, "api_model", ""),
            "apiBaseUrl": getattr(result, "api_base_url", ""),
            **response_shape_metrics(getattr(result, "payload", None)),
        })
    append_jsonl(runtime_ai_dir(runtime_root) / "prompt_meter_runtime.jsonl", payload)
    return payload


def write_turn_replay(runtime_root, turn_id, fields):
    if not turn_id:
        return None
    turns_root = runtime_ai_dir(runtime_root) / "turns"
    project_id = str((fields or {}).get("projectMemoryId", "") or "")
    batch_id = str((fields or {}).get("evaluationBatchId", "") or "")
    if project_id and batch_id:
        path = turns_root / project_id / batch_id / f"{turn_id}.json"
    else:
        matches = list(turns_root.glob(f"**/{turn_id}.json")) if turns_root.exists() else []
        path = matches[0] if matches else turns_root / "unknown_project" / "unknown_batch" / f"{turn_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload.update(deepcopy(fields or {}))
    payload.setdefault("turnId", turn_id)
    payload["updatedAt"] = now_iso()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def router_decision_payload(engine, candidate_ids, degradations=None):
    return {
        "candidateNodeIds": list(candidate_ids or []),
        "candidateNodes": [
            {
                "id": node_id,
                "name": engine.node_by_id.get(node_id, {}).get("name", node_id),
                "domain": engine.node_by_id.get(node_id, {}).get("domain", ""),
                "roleClass": engine.node_by_id.get(node_id, {}).get("roleClass", ""),
                "designEntityTarget": engine.node_by_id.get(node_id, {}).get("roleClass", "") in CONCRETE_ROLE_CLASSES,
            }
            for node_id in candidate_ids or []
        ],
        "degradations": list(degradations or []),
    }


def should_force_readiness_check(ai_state):
    count = ai_state.get("questionGroupCount", 0)
    if count <= 0 or count % QUESTION_GROUP_CHECK_INTERVAL != 0:
        return False
    return ai_state.get("lastReadinessCheckGroup", 0) < count


def build_interview_prompt(
    engine,
    project_state,
    user_text,
    force_output=False,
    force_readiness_check=False,
    runtime_root=None,
    turn_id=None,
    record=True,
):
    root = runtime_root or runtime_project_root()
    ai_state = ensure_ai_interview(project_state)
    memory_state = ensure_project_memory(project_state, root)
    prompt_snapshot = prompt_snapshot_for_project(project_state, root)
    prompt_framework = compose_prompt_framework(root)
    update_route_overview(engine, project_state)
    conversation_summary(ai_state)["mdaProgress"] = mda_progress_for_count(ai_state.get("questionGroupCount", 0))
    include_full = bool(force_output or detect_force_output(user_text))
    schema_mode = "full_output" if include_full else ("readiness" if force_readiness_check else "turn")
    turn_id = turn_id or new_memory_id("turn")
    ai_state["lastTurnId"] = turn_id
    candidate_ids = [] if include_full else candidate_node_ids(engine, project_state, user_text, limit=CANDIDATE_NODE_LIMIT)
    recent_limit = RECENT_MESSAGE_LIMIT_FULL if include_full else RECENT_MESSAGE_LIMIT_TURN
    output_mode = "full_project_output" if include_full else "interview_turn"
    degradations = []
    memory_influence = retrieved_memory_context(root, project_state, user_text, candidate_ids, limit=3)
    router_decision = router_decision_payload(engine, candidate_ids, degradations)
    prompt_payload = {
        "turnId": turn_id,
        "task": "commercial_game_design_ai_interview",
        "promptFramework": {
            "snapshot": prompt_snapshot,
            "rules": prompt_framework.get("rules", []),
            "visibility": "hidden_to_user",
            "designOptionFrameworkMutation": "forbidden",
        },
        "schemaMode": schema_mode,
        "outputMode": output_mode,
        "sessionPolicy": {
            "mode": "stateless_fast_turn" if not include_full else "full_output_turn",
            "sourceOfTruth": "aiInterview.summary.v1 + recentMessages + projectDigest",
            "doNotRelyOnHiddenSessionMemory": True,
        },
        "projectSummary": compact_project_summary(engine, project_state),
        "projectDigest": project_digest(engine, project_state, minimal=False),
        "conversationSummary": conversation_summary(ai_state),
        "routeOverview": ai_state.get("routeOverview", {}),
        "routerDecision": router_decision,
        "questionGroupCount": ai_state.get("questionGroupCount", 0),
        "evaluationBatchId": memory_state.get("evaluationBatchId", ""),
        "projectMemoryId": memory_state.get("projectMemoryId", ""),
        "forceReadinessCheck": bool(force_readiness_check),
        "memoryInfluence": memory_influence,
        "recentMessages": recent_messages(ai_state, recent_limit),
        "frameworkContext": framework_context(
            engine,
            project_state,
            include_full=include_full,
            candidate_ids=candidate_ids,
            node_limit=CANDIDATE_NODE_LIMIT,
        ),
        "userMessage": str(user_text or ""),
    }
    if include_full:
        prompt_payload["currentProjectState"] = project_state
    if include_full:
        prompt_payload["fullOutputRequirements"] = [
            "必须返回 fullProjectOutput.projectStateJson，值是 JSON 字符串，解析后结构与 currentProjectState 相同。",
            "必须返回 fullProjectOutput.confidenceMapJson，值是 JSON 字符串，解析后至少包含 groups 或 nodes 置信度。",
            "只把高置信设计作为候选写入；低置信内容留在 inferences 里继续澄清。",
            "optionDifferences 说明当前项目与 AI 全项目输出的选项差异。",
        ]
        prompt_payload["fullOutputRequirements"].append(
            "For nodes with roleClass system_concrete/content_concrete, write L5 cards to node.designEntities only when required fields in designEntityPrompt.allowedSchemas are present and confidenceMap.nodes[nodeId] >= 0.75."
        )
    else:
        prompt_payload["turnRequirements"] = [
            "如果需要追问，返回 mode=question_group 和 questionGroup。",
            "如果已经接近可生成，返回 mode=readiness_check 并询问是否输出。",
            "普通追问轮次不需要强行完成完整选项映射；证据不足时 inferences 可以为空数组。",
            "如果用户自然语言纠偏，先确认重排路线，不要让用户手动选节点。",
        ]
        if force_readiness_check:
            prompt_payload["turnRequirements"].insert(0, "本轮是工具侧生成就绪检查点，必须返回 mode=readiness_check。")

    prompt_text = build_prompt_text(prompt_snapshot, prompt_payload)
    if not include_full and len(prompt_text) > PROMPT_CHAR_BUDGET_TURN:
        signals = prompt_payload.get("memoryInfluence", {}).get("signals", [])
        if len(signals) > 1:
            prompt_payload["memoryInfluence"]["signals"] = signals[:1]
            prompt_payload["memoryInfluence"]["policy"] = "budget_top_1"
            degradations.append("memoryInfluence:top3_to_top1")
    prompt_text = build_prompt_text(prompt_snapshot, prompt_payload)
    if not include_full and len(prompt_text) > PROMPT_CHAR_BUDGET_TURN:
        prompt_payload["recentMessages"] = recent_messages(ai_state, 4)
        degradations.append("recentMessages:limit_to_4")
    prompt_text = build_prompt_text(prompt_snapshot, prompt_payload)
    if not include_full and len(prompt_text) > PROMPT_CHAR_BUDGET_TURN and len(candidate_ids) > CANDIDATE_NODE_MIN_LIMIT:
        candidate_ids = candidate_ids[:CANDIDATE_NODE_MIN_LIMIT]
        prompt_payload["frameworkContext"] = framework_context(
            engine,
            project_state,
            include_full=False,
            candidate_ids=candidate_ids,
            node_limit=CANDIDATE_NODE_MIN_LIMIT,
        )
        prompt_payload["routerDecision"] = router_decision_payload(engine, candidate_ids, degradations)
        degradations.append("candidateNodes:top5_to_top3")
    prompt_text = build_prompt_text(prompt_snapshot, prompt_payload)
    if not include_full and len(prompt_text) > PROMPT_CHAR_BUDGET_TURN:
        prompt_payload["projectDigest"] = project_digest(engine, project_state, minimal=True)
        degradations.append("projectDigest:minimal")
    prompt_text = build_prompt_text(prompt_snapshot, prompt_payload)
    if not include_full and len(prompt_text) > PROMPT_CHAR_BUDGET_TURN:
        degradations.append("budget_warning:over_limit")
    prompt_payload["routerDecision"] = router_decision_payload(engine, candidate_ids, degradations)
    prompt_text = build_prompt_text(prompt_snapshot, prompt_payload)

    if record:
        meter = prompt_meter_entry(turn_id, schema_mode, output_mode, prompt_payload, prompt_text, degradations, ai_state)
        record_prompt_meter(root, meter)
        write_turn_replay(root, turn_id, {
            "turnId": turn_id,
            "createdAt": now_iso(),
            "projectMemoryId": memory_state.get("projectMemoryId", ""),
            "evaluationBatchId": memory_state.get("evaluationBatchId", ""),
            "userText": str(user_text or ""),
            "schemaMode": schema_mode,
            "outputMode": output_mode,
            "forceOutput": bool(force_output),
            "forceReadinessCheck": bool(force_readiness_check),
            "routerDecision": prompt_payload.get("routerDecision", {}),
            "projectStateHash": stable_hash(project_digest(engine, project_state, minimal=True)),
            "promptMeter": meter,
            **prompt_replay_fields(prompt_text),
        })
    return prompt_text


def build_output_partition_prompt(
    engine,
    project_state,
    user_text,
    domain_ids,
    partition_index,
    partition_count,
    runtime_root=None,
    turn_id=None,
    record=True,
):
    root = runtime_root or runtime_project_root()
    ai_state = ensure_ai_interview(project_state)
    memory_state = ensure_project_memory(project_state, root)
    prompt_snapshot = prompt_snapshot_for_project(project_state, root)
    prompt_framework = compose_prompt_framework(root)
    update_route_overview(engine, project_state)
    turn_id = turn_id or new_memory_id("turn_part")
    domain_ids = [domain_id for domain_id in domain_ids if domain_id in engine.domain_by_id]
    partition_state = project_state_for_domains(engine, project_state, domain_ids)
    prompt_payload = {
        "turnId": turn_id,
        "task": "commercial_game_design_ai_interview_output_partition",
        "promptFramework": {
            "snapshot": prompt_snapshot,
            "rules": prompt_framework.get("rules", []),
            "visibility": "hidden_to_user",
            "designOptionFrameworkMutation": "forbidden",
        },
        "schemaMode": "partial_output",
        "outputMode": "partial_project_output",
        "partition": {
            "index": int(partition_index),
            "count": int(partition_count),
            "domainIds": domain_ids,
            "policy": "只输出这些 domainIds 下节点的 projectState patch，不要补全其他领域。",
        },
        "projectSummary": compact_project_summary(engine, project_state),
        "projectDigest": project_digest(engine, project_state, minimal=False),
        "conversationSummary": conversation_summary(ai_state),
        "routeOverview": ai_state.get("routeOverview", {}),
        "questionGroupCount": ai_state.get("questionGroupCount", 0),
        "evaluationBatchId": memory_state.get("evaluationBatchId", ""),
        "projectMemoryId": memory_state.get("projectMemoryId", ""),
        "recentMessages": recent_messages(ai_state, RECENT_MESSAGE_LIMIT_FULL),
        "domainProjectState": partition_state,
        "frameworkContext": packed_framework_context_for_domains(engine, domain_ids),
        "userMessage": str(user_text or ""),
        "partialOutputRequirements": [
            "必须返回 mode=partial_project_output 和 partialProjectOutput。",
            "partialProjectOutput.domainIds 必须等于本分片 domainIds。",
            "partialProjectOutput.projectStatePatchJson 必须是 JSON 字符串，解析后结构至少包含 nodes 对象。",
            "nodes 只能包含本分片 domainIds 下的节点；不要包含其他领域节点。",
            "confidenceMapJson 必须是 JSON 字符串，解析后至少包含 groups 或 nodes 置信度。",
            "低置信内容留在 inferences 中，不要提高置信度。",
        ],
    }
    prompt_payload["partialOutputRequirements"].append(
        "For concrete nodes in this partition, include node.designEntities only when the entity matches one of the packed entitySchemas and confidenceMap.nodes[nodeId] >= 0.75."
    )
    prompt_text = build_prompt_text(prompt_snapshot, prompt_payload)
    if record:
        meter = prompt_meter_entry(
            turn_id,
            "partial_output",
            "partial_project_output",
            prompt_payload,
            prompt_text,
            [],
            ai_state,
        )
        record_prompt_meter(root, meter)
        write_turn_replay(root, turn_id, {
            "turnId": turn_id,
            "createdAt": now_iso(),
            "projectMemoryId": memory_state.get("projectMemoryId", ""),
            "evaluationBatchId": memory_state.get("evaluationBatchId", ""),
            "userText": str(user_text or ""),
            "schemaMode": "partial_output",
            "outputMode": "partial_project_output",
            "partition": prompt_payload["partition"],
            "projectStateHash": stable_hash(project_state_for_domains(engine, project_state, domain_ids)),
            "promptMeter": meter,
            **prompt_replay_fields(prompt_text),
        })
    return prompt_text
