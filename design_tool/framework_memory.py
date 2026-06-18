import json
import os
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from design_tool.prompt_framework import (
    create_candidate_from_diff,
    framework_memory_dir,
    prompt_version_snapshot,
    promote_candidate,
    rollback_to_previous,
    validate_candidate_prompt_framework,
    validate_prompt_framework,
)


MEMORY_SCHEMA_VERSION = "1.0"
PROJECT_THRESHOLD = 3
COLD_START_PROJECT_THRESHOLD = 5
LOCAL_SIGNAL_REVIEW_COUNT = 3

QUALIFIED_EVIDENCE = {"qualified", "project_local_signal"}
HARD_ROLLBACK_SIGNALS = {
    "memory_exposed",
    "design_option_framework_change_attempt",
    "structured_output_schema_broken",
    "ai_file_edit_attempt",
}
OBSERVATION_ROLLBACK_SIGNALS = {
    "severe_correction",
    "low_quality_output",
    "explicit_user_rejection",
    "validation_failure",
}
OBSERVATION_ROLLBACK_PROJECT_THRESHOLD = 2
PROMPT_DIFF_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "operation",
        "targetModule",
        "targetRuleId",
        "newRule",
        "newRuleText",
        "sourceRuleIds",
        "oldRuleSummary",
        "reason",
        "evidenceIds",
        "expectedEffect",
        "risk",
        "rollbackPoint",
    ],
    "properties": {
        "operation": {"type": "string", "enum": ["add_rule", "edit_rule", "delete_rule", "merge_rules"]},
        "targetModule": {"type": "string"},
        "targetRuleId": {"type": "string"},
        "newRule": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["id", "text"],
            "properties": {
                "id": {"type": "string"},
                "text": {"type": "string"},
            },
        },
        "newRuleText": {"type": "string"},
        "sourceRuleIds": {"type": "array", "items": {"type": "string"}},
        "oldRuleSummary": {"type": "string"},
        "reason": {"type": "string"},
        "evidenceIds": {"type": "array", "items": {"type": "string"}},
        "expectedEffect": {"type": "string"},
        "risk": {"type": "string"},
        "rollbackPoint": {"type": "string"},
    },
}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def memory_paths(runtime_root):
    root = framework_memory_dir(runtime_root)
    return {
        "root": root,
        "events": root / "events.jsonl",
        "logs": root / "memory_log.jsonl",
        "scores": root / "scores.json",
        "staged": root / "staged_signals.jsonl",
        "backend": root / "backend_events.jsonl",
        "regression": root / "regression_examples.jsonl",
        "risk": root / "risk_reports",
        "failed": root / "failed_candidates",
        "candidates": root / "candidates",
        "versions": root / "versions",
        "imports": root / "imports",
    }


def ensure_memory_dirs(runtime_root):
    paths = memory_paths(runtime_root)
    for key, path in paths.items():
        if key == "root":
            path.mkdir(parents=True, exist_ok=True)
        elif path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    return paths


def append_jsonl(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def load_scores(runtime_root):
    paths = ensure_memory_dirs(runtime_root)
    path = paths["scores"]
    if not path.exists():
        return {
            "schemaVersion": MEMORY_SCHEMA_VERSION,
            "promotedKeys": [],
            "failedPatterns": {},
            "stagedSignalIds": [],
            "updatedAt": now_iso(),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    payload.setdefault("schemaVersion", MEMORY_SCHEMA_VERSION)
    payload.setdefault("promotedKeys", [])
    payload.setdefault("failedPatterns", {})
    payload.setdefault("stagedSignalIds", [])
    payload.setdefault("updatedAt", now_iso())
    return payload


def save_scores(runtime_root, scores):
    paths = ensure_memory_dirs(runtime_root)
    scores["updatedAt"] = now_iso()
    paths["scores"].write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")


def ai_memory_state(project_state):
    ai_state = project_state.setdefault("aiInterview", {})
    memory = ai_state.setdefault("frameworkMemory", {})
    memory.setdefault("projectMemoryId", new_id("project"))
    memory.setdefault("evaluationBatchId", "")
    memory.setdefault("batchStatus", "idle")
    memory.setdefault("promptVersionSnapshot", {})
    memory.setdefault("lastCompletedBatchId", "")
    memory.setdefault("reviewChains", {})
    memory.setdefault("updatedAt", now_iso())
    return memory


def ensure_project_memory(project_state, runtime_root, prompt_snapshot=None):
    memory = ai_memory_state(project_state)
    if not memory.get("projectMemoryId"):
        memory["projectMemoryId"] = new_id("project")
    if not memory.get("evaluationBatchId") or memory.get("batchStatus") == "ended":
        latest_snapshot = prompt_snapshot or prompt_version_snapshot(runtime_root)
        old_snapshot = memory.get("promptVersionSnapshot") or {}
        if old_snapshot and old_snapshot != latest_snapshot:
            project_state.setdefault("aiInterview", {})["codexSessionId"] = ""
        memory["evaluationBatchId"] = new_id("batch")
        memory["batchStatus"] = "active"
        memory["promptVersionSnapshot"] = deepcopy(latest_snapshot)
        memory["batchStartedAt"] = now_iso()
    memory["updatedAt"] = now_iso()
    return memory


def signal_key(target_module, signal_type, target_rule_id="", focus_id=""):
    return "|".join([str(target_module or ""), str(signal_type or ""), str(target_rule_id or ""), str(focus_id or "")])


def semantic_tokens(value):
    text = str(value or "").lower()
    ascii_tokens = re.findall(r"[a-z0-9_]{2,}", text)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_tokens = []
    for chunk in cjk_chunks:
        cjk_tokens.extend(chunk[index:index + 2] for index in range(max(1, len(chunk) - 1)))
    tokens = set(ascii_tokens + cjk_tokens)
    stopwords = {"the", "and", "for", "with", "this", "that", "what", "when", "where", "how"}
    return {token for token in tokens if token not in stopwords}


def semantic_similarity(left, right):
    left_tokens = semantic_tokens(left)
    right_tokens = semantic_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def semantic_text_for_question_group(payload):
    question_group = payload.get("questionGroup") if isinstance(payload, dict) and isinstance(payload.get("questionGroup"), dict) else {}
    parts = [question_group.get("purpose", "")]
    for question in question_group.get("questions", []) or []:
        if isinstance(question, dict):
            parts.extend([question.get("text", ""), question.get("reason", "")])
    return " ".join(str(part or "") for part in parts)


def semantic_cluster_id(text):
    tokens = sorted(semantic_tokens(text))
    if not tokens:
        return "semantic_empty"
    digest = uuid.uuid5(uuid.NAMESPACE_URL, "|".join(tokens[:24])).hex[:12]
    return f"semantic_{digest}"


def similar_review_chain_key(chains, target_module, signal_type, focus_id, semantic_text, threshold=0.34):
    best_key = ""
    best_score = 0.0
    for key, chain in (chains or {}).items():
        if chain.get("targetModule") != target_module or chain.get("signalType") != signal_type:
            continue
        if focus_id and chain.get("focusId") and chain.get("focusId") != focus_id:
            continue
        score = semantic_similarity(semantic_text, chain.get("semanticText", ""))
        if score > best_score:
            best_key = key
            best_score = score
    if best_score >= threshold:
        return best_key, best_score
    return "", best_score


def infer_question_group_signal(payload):
    payload = payload if isinstance(payload, dict) else {}
    question_group = payload.get("questionGroup") if isinstance(payload.get("questionGroup"), dict) else {}
    purpose = str(question_group.get("purpose", ""))
    questions = question_group.get("questions", []) if isinstance(question_group.get("questions"), list) else []
    joined_questions = " ".join(str(item.get("text", "")) for item in questions if isinstance(item, dict))
    text = f"{purpose} {joined_questions}"
    if "置信" in text or "不确定" in text or "模糊" in text:
        return "confidence", "low_confidence_mapping"
    if "映射" in text or "选项" in text or "节点" in text:
        return "mapping", "mapping_or_interpretation_failure"
    if "输出" in text or "生成" in text or payload.get("mode") == "readiness_check":
        return "readiness", "readiness_uncertainty"
    if "路线" in text or "顺序" in text:
        return "routing", "route_uncertainty"
    if "追问" in text or "澄清" in text:
        return "followup", "repeated_clarification"
    return "interpretation", "interpretation_uncertainty"


def focus_id_for_question_group(payload):
    question_group = payload.get("questionGroup") if isinstance(payload, dict) and isinstance(payload.get("questionGroup"), dict) else {}
    target_ids = []
    for question in question_group.get("questions", []) or []:
        if isinstance(question, dict):
            target_ids.extend(str(item) for item in question.get("targetNodeIds", []) if item)
    if target_ids:
        return sorted(set(target_ids))[0]
    for inference in payload.get("inferences", []) or []:
        if isinstance(inference, dict) and inference.get("nodeId"):
            return str(inference.get("nodeId"))
    return ""


def record_question_group_review(runtime_root, project_state, payload):
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("mode") != "question_group" or not isinstance(payload.get("questionGroup"), dict):
        return None
    memory = ensure_project_memory(project_state, runtime_root)
    ai_state = project_state.setdefault("aiInterview", {})
    group_index = int(ai_state.get("questionGroupCount", 0) or 0)
    question_group = payload.get("questionGroup", {})
    target_module, signal_type = infer_question_group_signal(payload)
    focus_id = focus_id_for_question_group(payload)
    semantic_text = semantic_text_for_question_group(payload)
    review_chains = memory.setdefault("reviewChains", {})
    key = signal_key(target_module, signal_type, "", focus_id or semantic_cluster_id(semantic_text))
    similar_key, similarity = similar_review_chain_key(review_chains, target_module, signal_type, focus_id, semantic_text)
    if similar_key:
        key = similar_key
    chain = review_chains.setdefault(key, {
        "chainId": new_id("review_chain"),
        "targetModule": target_module,
        "targetRuleId": "",
        "signalType": signal_type,
        "focusId": focus_id,
        "semanticClusterId": semantic_cluster_id(semantic_text),
        "semanticText": semantic_text,
        "reviews": [],
        "qualifiedEventId": "",
        "createdAt": now_iso(),
    })
    chain["lastSemanticSimilarity"] = round(float(similarity or 0.0), 4)
    if semantic_text and len(semantic_text) > len(str(chain.get("semanticText", ""))):
        chain["semanticText"] = semantic_text
    reviews = chain.setdefault("reviews", [])
    if any(int(review.get("questionGroupIndex", -1)) == group_index for review in reviews):
        return chain
    if reviews:
        last_index = max(int(review.get("questionGroupIndex", -1)) for review in reviews)
        if group_index <= last_index + 1:
            append_memory_log(
                runtime_root,
                project_state,
                action="non_consecutive_review_skipped",
                memorySignalIds=[chain.get("chainId", "")],
                decision="skip",
                reasonSummary="复核问题组与上一次复核连续，不能计入非连续三次复核。",
                result=key,
            )
            return chain
    questions = [
        short_text(item.get("text", ""), 90)
        for item in question_group.get("questions", [])[:4]
        if isinstance(item, dict)
    ]
    reviews.append({
        "questionGroupId": question_group.get("id", ""),
        "questionGroupIndex": group_index,
        "createdAt": now_iso(),
        "purpose": short_text(question_group.get("purpose", ""), 120),
        "questions": questions,
        "semanticClusterId": chain.get("semanticClusterId", ""),
        "semanticSimilarity": chain.get("lastSemanticSimilarity", 0.0),
    })
    append_memory_log(
        runtime_root,
        project_state,
        action="non_consecutive_review_recorded",
        memorySignalIds=[chain.get("chainId", "")],
        decision="record",
        reasonSummary=f"{target_module}/{signal_type} 非连续复核记录。",
        result=f"{len(reviews)}/{LOCAL_SIGNAL_REVIEW_COUNT}",
    )
    if len(reviews) >= LOCAL_SIGNAL_REVIEW_COUNT and not chain.get("qualifiedEventId"):
        event = append_evidence_event(
            runtime_root,
            project_state,
            sourceType="implicit_review_chain",
            qualification="project_local_signal",
            weight=1.0,
            targetModule=target_module,
            targetRuleId="",
            signalType=signal_type,
            summary="同一项目内三次非连续隐式复核形成提示词修订信号。",
            shortExcerpt=" | ".join(review.get("purpose", "") for review in reviews[-3:]),
            relatedIds=[review.get("questionGroupId", "") for review in reviews[-3:]],
        )
        chain["qualifiedEventId"] = event.get("eventId", "")
        append_memory_log(
            runtime_root,
            project_state,
            action="project_local_prompt_signal_qualified",
            memorySignalIds=[event.get("eventId", ""), chain.get("chainId", "")],
            decision="qualify",
            reasonSummary="项目内非连续三次复核已达到门槛。",
            result=key,
        )
    memory["updatedAt"] = now_iso()
    return chain


def prompt_snapshot_for_project(project_state, runtime_root):
    memory = ensure_project_memory(project_state, runtime_root)
    snapshot = memory.get("promptVersionSnapshot") or prompt_version_snapshot(runtime_root)
    memory["promptVersionSnapshot"] = deepcopy(snapshot)
    return snapshot


def event_base(project_state, runtime_root):
    memory = ensure_project_memory(project_state, runtime_root)
    snapshot = memory.get("promptVersionSnapshot") or prompt_version_snapshot(runtime_root)
    return {
        "eventId": new_id("event"),
        "createdAt": now_iso(),
        "projectMemoryId": memory.get("projectMemoryId", ""),
        "evaluationBatchId": memory.get("evaluationBatchId", ""),
        "promptFrameworkVersion": snapshot.get("frameworkVersion", ""),
        "moduleVersions": snapshot.get("modules", {}),
    }


def append_evidence_event(runtime_root, project_state, **fields):
    paths = ensure_memory_dirs(runtime_root)
    payload = event_base(project_state, runtime_root)
    payload.update({
        "sourceType": fields.get("sourceType", "unknown"),
        "qualification": fields.get("qualification", "context"),
        "weight": float(fields.get("weight", 0.0) or 0.0),
        "targetModule": fields.get("targetModule", ""),
        "targetRuleId": fields.get("targetRuleId", ""),
        "signalType": fields.get("signalType", ""),
        "summary": fields.get("summary", ""),
        "shortExcerpt": fields.get("shortExcerpt", ""),
        "relatedIds": list(fields.get("relatedIds", [])),
    })
    append_jsonl(paths["events"], payload)
    return payload


def append_memory_log(runtime_root, project_state=None, **fields):
    paths = ensure_memory_dirs(runtime_root)
    if project_state is not None:
        memory = ai_memory_state(project_state)
        project_id = memory.get("projectMemoryId", "")
        batch_id = memory.get("evaluationBatchId", "")
        snapshot = memory.get("promptVersionSnapshot") or prompt_version_snapshot(runtime_root)
    else:
        project_id = fields.get("projectMemoryId", "")
        batch_id = fields.get("evaluationBatchId", "")
        snapshot = fields.get("promptVersionSnapshot") or prompt_version_snapshot(runtime_root)
    payload = {
        "logId": new_id("log"),
        "createdAt": now_iso(),
        "projectMemoryId": project_id,
        "evaluationBatchId": batch_id,
        "action": fields.get("action", ""),
        "promptVersionSnapshot": snapshot,
        "memorySignalIds": list(fields.get("memorySignalIds", [])),
        "decision": fields.get("decision", ""),
        "reasonSummary": fields.get("reasonSummary", ""),
        "result": fields.get("result", ""),
    }
    append_jsonl(paths["logs"], payload)
    return payload


def record_backend_runtime_event(runtime_root, project_state, event_type, summary, detail=""):
    paths = ensure_memory_dirs(runtime_root)
    memory = ensure_project_memory(project_state, runtime_root)
    payload = {
        "eventId": new_id("backend"),
        "createdAt": now_iso(),
        "projectMemoryId": memory.get("projectMemoryId", ""),
        "evaluationBatchId": memory.get("evaluationBatchId", ""),
        "eventType": event_type,
        "summary": summary,
        "detail": detail[:800],
        "promptVersionSnapshot": memory.get("promptVersionSnapshot", {}),
    }
    append_jsonl(paths["backend"], payload)
    append_memory_log(
        runtime_root,
        project_state,
        action="backend_runtime_event",
        decision="record_context_only",
        reasonSummary=summary,
        result=event_type,
    )
    return payload


def short_text(value, limit=180):
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit]


def module_for_validation_error(error):
    text = str(error or "")
    if "schema" in text.lower() or "JSON" in text or "输出" in text:
        return "output"
    if "置信" in text:
        return "confidence"
    if "未知节点" in text or "未知" in text or "选项" in text:
        return "mapping"
    return "interpretation"


def record_payload_validation_errors(runtime_root, project_state, errors):
    events = []
    for error in errors or []:
        module_id = module_for_validation_error(error)
        signal_type = "structured_output_schema_broken" if module_id == "output" else "mapping_or_interpretation_failure"
        events.append(append_evidence_event(
            runtime_root,
            project_state,
            sourceType="tool_validation",
            qualification="qualified" if module_id == "output" else "context",
            weight=1.0 if module_id == "output" else 0.0,
            targetModule=module_id,
            signalType=signal_type,
            summary="AI 输出校验失败。",
            shortExcerpt=short_text(error),
        ))
    return events


def record_user_correction(runtime_root, project_state, summary, target_module="mapping", signal_type="explicit_user_correction"):
    event = append_evidence_event(
        runtime_root,
        project_state,
        sourceType="user_correction_action",
        qualification="qualified",
        weight=1.0,
        targetModule=target_module,
        targetRuleId="",
        signalType=signal_type,
        summary=summary,
        shortExcerpt=short_text(summary, 160),
    )
    append_memory_log(
        runtime_root,
        project_state,
        action="user_correction_recorded",
        memorySignalIds=[event.get("eventId", "")],
        decision="qualified_evidence",
        reasonSummary="用户显式纠错动作。",
        result=target_module,
    )
    return event


def record_ai_payload_context(runtime_root, project_state, payload, validation_errors=None, differences=None):
    payload = payload if isinstance(payload, dict) else {}
    mode = payload.get("mode", "")
    events = []
    if validation_errors:
        events.extend(record_payload_validation_errors(runtime_root, project_state, validation_errors))
    for inference in payload.get("inferences", []) or []:
        if not isinstance(inference, dict):
            continue
        try:
            confidence = float(inference.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0
        if 0 < confidence < 0.75:
            events.append(append_evidence_event(
                runtime_root,
                project_state,
                sourceType="ai_output",
                qualification="ai_context",
                weight=0.0,
                targetModule="confidence",
                targetRuleId="high_confidence_threshold",
                signalType="low_confidence_mapping",
                summary="AI 产生低置信映射，作为上下文记录，不计票。",
                shortExcerpt=short_text(inference.get("reason", "")),
                relatedIds=[inference.get("nodeId", ""), inference.get("groupId", "")],
            ))
    if differences:
        events.append(append_evidence_event(
            runtime_root,
            project_state,
            sourceType="ai_output_difference",
            qualification="ai_context",
            weight=0.0,
            targetModule="mapping",
            signalType="option_difference_context",
            summary=f"AI 输出产生 {len(differences)} 条选项差异，作为上下文记录。",
            shortExcerpt="; ".join(short_text(item.get("groupId", "")) for item in differences[:5] if isinstance(item, dict)),
        ))
    if mode:
        append_memory_log(
            runtime_root,
            project_state,
            action="ai_payload_context_recorded",
            decision="context_only",
            reasonSummary=f"AI payload mode={mode}",
            result=f"{len(events)} evidence events",
        )
    extract_regression_examples(runtime_root, project_state, payload, validation_errors=validation_errors)
    return events


def staged_memory_context(runtime_root, project_state, limit=3):
    paths = ensure_memory_dirs(runtime_root)
    staged = read_jsonl(paths["staged"])
    if not staged:
        return {
            "visibility": "hidden",
            "policy": "no_staged_signal",
            "signals": [],
        }
    signals = []
    seen = set()
    for row in reversed(staged):
        key = signal_key(row.get("targetModule", ""), row.get("signalType", ""), row.get("targetRuleId", ""), "")
        if key in seen:
            continue
        seen.add(key)
        signals.append({
            "signalId": row.get("eventId", ""),
            "targetModule": row.get("targetModule", ""),
            "signalType": row.get("signalType", ""),
            "summary": short_text(row.get("summary", ""), 120),
            "instruction": "仅可低权重影响澄清问题或保守映射；不得提高置信度、直接落选项或向用户暴露记忆。",
        })
        if len(signals) >= limit:
            break
    if signals:
        append_memory_log(
            runtime_root,
            project_state,
            action="staged_memory_context_injected",
            memorySignalIds=[item.get("signalId", "") for item in signals],
            decision="low_weight_prompt_context",
            reasonSummary="暂存信号以低权重隐式影响本轮追问。",
            result=f"{len(signals)} staged signals",
        )
    return {
        "visibility": "hidden",
        "policy": "low_weight_only",
        "signals": signals,
    }


def regression_example_key(payload):
    return "|".join([
        str(payload.get("inputSummary", "")),
        str(payload.get("expectedFollowupType", "")),
        ",".join(payload.get("expectedMappingConstraints", [])),
    ])


def existing_regression_keys(runtime_root):
    return {
        regression_example_key(row)
        for row in read_jsonl(memory_paths(runtime_root)["regression"])
    }


def extract_regression_examples(runtime_root, project_state, payload, validation_errors=None):
    payload = payload if isinstance(payload, dict) else {}
    paths = ensure_memory_dirs(runtime_root)
    keys = existing_regression_keys(runtime_root)
    memory = ensure_project_memory(project_state, runtime_root)
    ai_state = project_state.get("aiInterview", {})
    recent_user = ""
    for message in reversed(ai_state.get("messages", [])):
        if message.get("role") == "user":
            recent_user = message.get("content", "")
            break
    examples = []
    question_group = payload.get("questionGroup") if isinstance(payload.get("questionGroup"), dict) else None
    if question_group:
        constraints = []
        for question in question_group.get("questions", []) or []:
            if isinstance(question, dict):
                constraints.extend(str(item) for item in question.get("targetNodeIds", []) if item)
        examples.append({
            "exampleId": new_id("regression"),
            "createdAt": now_iso(),
            "source": "real_interview",
            "projectMemoryId": memory.get("projectMemoryId", ""),
            "evaluationBatchId": memory.get("evaluationBatchId", ""),
            "promptVersionSnapshot": memory.get("promptVersionSnapshot", {}),
            "inputSummary": short_text(recent_user, 140),
            "expectedFollowupType": short_text(question_group.get("purpose", "") or payload.get("mode", ""), 120),
            "forbiddenBehavior": [
                "不得暴露历史记忆或暂存信号。",
                "不得新增或修改设计选项框架。",
                "不得直接替用户选择选项。",
            ],
            "expectedMappingConstraints": sorted(set(constraints))[:8],
        })
    for error in validation_errors or []:
        examples.append({
            "exampleId": new_id("regression"),
            "createdAt": now_iso(),
            "source": "tool_validation",
            "projectMemoryId": memory.get("projectMemoryId", ""),
            "evaluationBatchId": memory.get("evaluationBatchId", ""),
            "promptVersionSnapshot": memory.get("promptVersionSnapshot", {}),
            "inputSummary": short_text(recent_user, 140),
            "expectedFollowupType": "validation_recovery",
            "forbiddenBehavior": [
                short_text(error, 160),
                "不得用自然语言替代结构化 JSON 字段。",
            ],
            "expectedMappingConstraints": [],
        })
    written = []
    for example in examples:
        key = regression_example_key(example)
        if not key or key in keys:
            continue
        keys.add(key)
        append_jsonl(paths["regression"], example)
        written.append(example)
    if written:
        append_memory_log(
            runtime_root,
            project_state,
            action="regression_examples_extracted",
            memorySignalIds=[item.get("exampleId", "") for item in written],
            decision="record",
            reasonSummary="从真实访谈/校验中提炼匿名结构化回归样例。",
            result=str(len(written)),
        )
    return written


def complete_evaluation_batch(runtime_root, project_state, reason="batch_end"):
    memory = ensure_project_memory(project_state, runtime_root)
    batch_id = memory.get("evaluationBatchId", "")
    memory["lastCompletedBatchId"] = batch_id
    memory["batchStatus"] = "ended"
    memory["batchEndedAt"] = now_iso()
    memory["updatedAt"] = now_iso()
    append_memory_log(
        runtime_root,
        project_state,
        action="evaluation_batch_completed",
        decision="aggregate",
        reasonSummary=reason,
        result=batch_id,
    )
    update_observation_usage(runtime_root, project_state)
    return aggregate_memory(runtime_root)


def evidence_project_groups(events):
    by_project_signal = defaultdict(list)
    for event in events:
        if event.get("qualification") not in QUALIFIED_EVIDENCE:
            continue
        if float(event.get("weight", 0.0) or 0.0) <= 0:
            continue
        module_id = event.get("targetModule", "")
        signal_type = event.get("signalType", "")
        project_id = event.get("projectMemoryId", "")
        if not module_id or not signal_type or not project_id:
            continue
        key = (project_id, module_id, signal_type, event.get("targetRuleId", ""))
        by_project_signal[key].append(event)
    project_local = []
    for (project_id, module_id, signal_type, rule_id), group in by_project_signal.items():
        if signal_type in HARD_ROLLBACK_SIGNALS or len(group) >= LOCAL_SIGNAL_REVIEW_COUNT:
            project_local.append({
                "projectMemoryId": project_id,
                "targetModule": module_id,
                "targetRuleId": rule_id,
                "signalType": signal_type,
                "events": group,
            })
    return project_local


def mature_memory(runtime_root, events):
    project_ids = {event.get("projectMemoryId") for event in events if event.get("projectMemoryId")}
    batch_ids = {event.get("evaluationBatchId") for event in events if event.get("evaluationBatchId")}
    qualified_events = [
        event for event in events
        if event.get("qualification") in QUALIFIED_EVIDENCE
        and float(event.get("weight", 0.0) or 0.0) > 0
    ]
    regression_examples = read_jsonl(memory_paths(runtime_root)["regression"])
    covered_modules = {event.get("targetModule") for event in qualified_events if event.get("targetModule")}
    return (
        len(project_ids) >= 5
        and len(batch_ids) >= 10
        and len(qualified_events) >= 30
        and len(regression_examples) >= 12
        and len(covered_modules) >= 4
    )


def candidate_rule_text(module_id, signal_type, events=None):
    events = events or []
    sample = "；".join(short_text(event.get("summary", ""), 50) for event in events[:3])
    if signal_type == "structured_output_schema_broken":
        return "当结构化输出 schema 有失败风险时，必须优先返回最小合法 JSON，对不确定内容使用空数组或 null，不得用自然语言替代结构化字段。"
    if signal_type == "mapping_or_interpretation_failure":
        return "当用户回答无法稳定映射到现有节点或 L4 选项时，先提出澄清问题并降低置信度，不得猜测不存在的框架项。"
    if signal_type == "low_confidence_mapping":
        return "当多次出现低置信映射时，下一轮必须追问导致不确定的具体取舍，并明确保留低置信内容不写入项目。"
    if signal_type == "memory_exposed":
        return "不得向用户暴露任何记忆、历史信号、暂存信号、版本或复核机制；所有记忆影响必须转化为自然追问。"
    return f"针对 {signal_type} 反复出现的问题，先用自然追问补足证据，再进行映射或输出。证据摘要：{sample}"


def make_candidate_diff(module_id, signal_type, events):
    digest_source = "|".join(sorted(event.get("eventId", "") for event in events))
    rule_id = f"memory_{module_id}_{uuid.uuid5(uuid.NAMESPACE_URL, module_id + signal_type + digest_source).hex[:10]}"
    return {
        "operation": "add_rule",
        "targetModule": module_id,
        "targetRuleId": "",
        "newRule": {
            "id": rule_id,
            "text": candidate_rule_text(module_id, signal_type, events),
        },
        "oldRuleSummary": "",
        "reason": "跨项目项目内提示词修订信号累计达到门槛。",
        "evidenceIds": [event.get("eventId", "") for event in events],
        "expectedEffect": "提升提问精准度、映射保守性或输出稳定性。",
        "risk": "新增规则可能让追问变多；通过回归和观察期控制。",
        "rollbackPoint": "previous_module_version",
    }


def evidence_summaries(events, limit=12):
    return [
        {
            "eventId": event.get("eventId", ""),
            "sourceType": event.get("sourceType", ""),
            "signalType": event.get("signalType", ""),
            "summary": short_text(event.get("summary", ""), 160),
            "shortExcerpt": short_text(event.get("shortExcerpt", ""), 120),
        }
        for event in events[:limit]
    ]


def synthesize_candidate_diff(runtime_root, module_id, signal_type, events):
    fallback = make_candidate_diff(module_id, signal_type, events)
    if os.environ.get("FRAMEWORK_MEMORY_DISABLE_CODEX_DIFF") == "1":
        return fallback
    try:
        from design_tool.ai_backend import CodexCliBackend, CodexUnavailableError, codex_available
        from design_tool.prompt_framework import compose_prompt_framework, validate_structured_diff
    except Exception as error:
        append_memory_log(
            runtime_root,
            action="ai_diff_synthesis_unavailable",
            decision="fallback",
            reasonSummary=f"无法加载 Codex diff 生成依赖：{error}",
            result="deterministic_diff",
        )
        return fallback
    if not codex_available():
        append_memory_log(
            runtime_root,
            action="ai_diff_synthesis_unavailable",
            decision="fallback",
            reasonSummary="Codex CLI 不可用，使用本地确定性提示词 diff。",
            result="deterministic_diff",
        )
        return fallback
    framework = compose_prompt_framework(runtime_root)
    prompt = {
        "task": "prompt_framework_diff_synthesis",
        "strictBoundary": [
            "只能生成提问提示词框架 diff。",
            "不得修改设计选项框架、领域、节点、L4、MDA、模板、校验规则或后端参数。",
            "默认只改一个模块；不得超出证据支持范围。",
            "如果不确定，生成保守的 add_rule。",
        ],
        "targetModule": module_id,
        "signalType": signal_type,
        "currentPromptFramework": framework,
        "evidence": evidence_summaries(events),
        "requiredOutput": "Return only one structured JSON diff matching schema.",
    }
    try:
        result = CodexCliBackend(runtime_root, workdir=runtime_root, timeout_seconds=60).run_json_task(
            json.dumps(prompt, ensure_ascii=False, indent=2),
            schema=PROMPT_DIFF_SCHEMA,
            schema_name="codex_prompt_diff.schema.json",
        )
        diff = result.payload
        errors = validate_structured_diff(diff)
        if errors:
            append_memory_log(
                runtime_root,
                action="ai_diff_synthesis_invalid",
                memorySignalIds=[event.get("eventId", "") for event in events],
                decision="fallback",
                reasonSummary="Codex 生成的提示词 diff 未通过边界校验。",
                result="; ".join(errors[:4]),
            )
            return fallback
        diff["evidenceIds"] = [event.get("eventId", "") for event in events]
        append_memory_log(
            runtime_root,
            action="ai_diff_synthesis_success",
            memorySignalIds=diff.get("evidenceIds", []),
            decision="use_ai_diff",
            reasonSummary="Codex 已生成结构化提示词 diff。",
            result=f"{diff.get('operation')}:{diff.get('targetModule')}",
        )
        return diff
    except (CodexUnavailableError, ValueError, OSError, json.JSONDecodeError) as error:
        append_memory_log(
            runtime_root,
            action="ai_diff_synthesis_failed",
            memorySignalIds=[event.get("eventId", "") for event in events],
            decision="fallback",
            reasonSummary="Codex 提示词 diff 生成失败，使用本地确定性 diff。",
            result=short_text(error, 240),
        )
        return fallback


def failed_pattern_key(module_id, signal_type, rule_id):
    return "|".join([module_id or "", signal_type or "", rule_id or ""])


def failed_pattern_count(scores, module_id, signal_type, rule_id):
    return int(scores.get("failedPatterns", {}).get(failed_pattern_key(module_id, signal_type, rule_id), 0) or 0)


def increment_failed_pattern(runtime_root, scores, module_id, signal_type, rule_id):
    key = failed_pattern_key(module_id, signal_type, rule_id)
    failed = scores.setdefault("failedPatterns", {})
    failed[key] = int(failed.get(key, 0) or 0) + 1
    save_scores(runtime_root, scores)
    return failed[key]


def required_project_threshold(base_threshold, failed_count):
    if failed_count >= 3:
        return max(base_threshold + 2, 5)
    if failed_count >= 2:
        return base_threshold + 1
    return base_threshold


def promoted_key(module_id, signal_type, rule_id, project_ids):
    return "|".join([module_id, signal_type, rule_id or "", ",".join(sorted(project_ids))])


def aggregate_memory(runtime_root):
    paths = ensure_memory_dirs(runtime_root)
    events = read_jsonl(paths["events"])
    scores = load_scores(runtime_root)
    results = []
    project_threshold = PROJECT_THRESHOLD if mature_memory(runtime_root, events) else COLD_START_PROJECT_THRESHOLD

    hard_events = [
        event for event in events
        if event.get("signalType") in HARD_ROLLBACK_SIGNALS
        and event.get("qualification") in QUALIFIED_EVIDENCE
        and float(event.get("weight", 0.0) or 0.0) > 0
    ]
    if hard_events:
        rollback_id, rollback_errors = rollback_to_previous(runtime_root, reason="hard_boundary_failure")
        append_memory_log(
            runtime_root,
            action="automatic_rollback",
            memorySignalIds=[event.get("eventId", "") for event in hard_events],
            decision="rollback" if not rollback_errors else "rollback_failed",
            reasonSummary="硬性边界错误触发自动回滚。",
            result=rollback_id or "; ".join(rollback_errors),
        )
        results.append({"action": "rollback", "id": rollback_id, "errors": rollback_errors})

    observation_result = check_observation_rollback(runtime_root, events)
    if observation_result:
        results.append(observation_result)

    project_local = evidence_project_groups(events)
    by_global_signal = defaultdict(list)
    for signal in project_local:
        key = (signal["targetModule"], signal["signalType"], signal.get("targetRuleId", ""))
        by_global_signal[key].append(signal)

    for (module_id, signal_type, rule_id), signals in by_global_signal.items():
        project_ids = {signal["projectMemoryId"] for signal in signals}
        failed_count = failed_pattern_count(scores, module_id, signal_type, rule_id)
        threshold = required_project_threshold(project_threshold, failed_count)
        if len(project_ids) < threshold:
            continue
        key = promoted_key(module_id, signal_type, rule_id, project_ids)
        if key in scores.get("promotedKeys", []):
            continue
        related_events = [event for signal in signals for event in signal["events"]]
        diff = synthesize_candidate_diff(runtime_root, module_id, signal_type, related_events)
        candidate_root, candidate_errors = create_candidate_from_diff(runtime_root, diff)
        validation_errors = candidate_errors or validate_candidate_prompt_framework(runtime_root=runtime_root, root_override=candidate_root, diff=diff)
        if validation_errors:
            new_failed_count = increment_failed_pattern(runtime_root, scores, module_id, signal_type, rule_id)
            failed_id = new_id("failed")
            failed_path = paths["failed"] / f"{failed_id}.json"
            failed_path.write_text(json.dumps({
                "failedId": failed_id,
                "createdAt": now_iso(),
                "moduleId": module_id,
                "signalType": signal_type,
                "failedPatternCount": new_failed_count,
                "structuredDiff": diff,
                "errors": validation_errors,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            append_memory_log(
                runtime_root,
                action="candidate_failed",
                memorySignalIds=[event.get("eventId", "") for event in related_events],
                decision="reject",
                reasonSummary="候选提示词 diff 未通过验证。",
                result=failed_id,
            )
            results.append({"action": "candidate_failed", "id": failed_id, "errors": validation_errors})
            continue
        try:
            from design_tool.prompt_evaluation import promotion_gate_decision
            gate = promotion_gate_decision(runtime_root)
        except Exception as error:
            gate = {
                "blocksPromotion": False,
                "decision": "gate_unavailable",
                "reasons": [str(error)],
            }
        if gate.get("blocksPromotion"):
            append_memory_log(
                runtime_root,
                action="promotion_blocked_by_evaluation_gate",
                memorySignalIds=[event.get("eventId", "") for event in related_events],
                decision="block",
                reasonSummary="Prompt evaluation gate blocked automatic prompt promotion.",
                result="; ".join(gate.get("reasons", [])[:4]),
            )
            results.append({
                "action": "promotion_blocked_by_evaluation_gate",
                "moduleId": module_id,
                "gate": gate,
            })
            continue
        version_id, promotion_errors = promote_candidate(runtime_root, candidate_root, metadata={
            "moduleId": module_id,
            "signalType": signal_type,
            "targetRuleId": rule_id,
            "evidenceIds": [event.get("eventId", "") for event in related_events],
            "projectMemoryIds": sorted(project_ids),
            "structuredDiff": diff,
            "promotionGate": gate,
        })
        if promotion_errors:
            results.append({"action": "promotion_failed", "errors": promotion_errors})
            continue
        scores.setdefault("promotedKeys", []).append(key)
        save_scores(runtime_root, scores)
        append_memory_log(
            runtime_root,
            action="candidate_promoted",
            memorySignalIds=[event.get("eventId", "") for event in related_events],
            decision="promote",
            reasonSummary="跨项目提示词信号累计达到门槛并通过验证。",
            result=version_id,
        )
        results.append({"action": "candidate_promoted", "id": version_id, "moduleId": module_id})
    return results


def latest_promotion_record(runtime_root):
    records_root = memory_paths(runtime_root)["versions"]
    if not records_root.exists():
        return None, None
    records = sorted(records_root.glob("prompt_framework_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    for record_dir in records:
        record_path = record_dir / "record.json"
        if not record_path.exists():
            continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("type") == "promotion":
            return record_dir, record
    return None, None


def update_observation_usage(runtime_root, project_state):
    record_dir, record = latest_promotion_record(runtime_root)
    if not record:
        return None
    memory = ai_memory_state(project_state)
    snapshot = memory.get("promptVersionSnapshot", {})
    new_snapshot = record.get("newSnapshot", {})
    if snapshot.get("frameworkVersion") != new_snapshot.get("frameworkVersion"):
        return None
    ai_state = project_state.get("aiInterview", {})
    observation = record.setdefault("observation", {
        "startedAt": record.get("createdAt", now_iso()),
        "status": "active",
        "projectMemoryIds": [],
        "evaluationBatchIds": [],
        "questionGroups": 0,
        "endedAt": "",
    })
    project_ids = set(observation.get("projectMemoryIds", []))
    batch_ids = set(observation.get("evaluationBatchIds", []))
    project_ids.add(memory.get("projectMemoryId", ""))
    batch_ids.add(memory.get("evaluationBatchId", ""))
    observation["projectMemoryIds"] = sorted(item for item in project_ids if item)
    observation["evaluationBatchIds"] = sorted(item for item in batch_ids if item)
    try:
        observation["questionGroups"] = max(int(observation.get("questionGroups", 0) or 0), int(ai_state.get("questionGroupCount", 0) or 0))
    except (TypeError, ValueError):
        observation["questionGroups"] = int(observation.get("questionGroups", 0) or 0)
    if (
        len(observation["projectMemoryIds"]) >= 5
        or len(observation["evaluationBatchIds"]) >= 10
        or observation["questionGroups"] >= 30
    ):
        observation["status"] = "completed"
        observation["endedAt"] = observation.get("endedAt") or now_iso()
    record["observation"] = observation
    record_path = record_dir / "record.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    append_memory_log(
        runtime_root,
        project_state,
        action="observation_usage_updated",
        decision=observation.get("status", "active"),
        reasonSummary="提示词框架观察期使用量更新。",
        result=f"projects={len(observation['projectMemoryIds'])}, batches={len(observation['evaluationBatchIds'])}, groups={observation['questionGroups']}",
    )
    return observation


def check_observation_rollback(runtime_root, events):
    record_dir, record = latest_promotion_record(runtime_root)
    if not record:
        return None
    new_snapshot = record.get("newSnapshot", {})
    version = new_snapshot.get("frameworkVersion", "")
    promoted_at = record.get("createdAt", "")
    observation = record.get("observation", {})
    threshold = OBSERVATION_ROLLBACK_PROJECT_THRESHOLD if observation.get("status", "active") != "completed" else OBSERVATION_ROLLBACK_PROJECT_THRESHOLD + 1
    severe_events = [
        event for event in events
        if event.get("promptFrameworkVersion") == version
        and event.get("createdAt", "") >= promoted_at
        and event.get("signalType") in OBSERVATION_ROLLBACK_SIGNALS
        and event.get("qualification") in QUALIFIED_EVIDENCE
        and float(event.get("weight", 0.0) or 0.0) > 0
    ]
    project_ids = {event.get("projectMemoryId") for event in severe_events if event.get("projectMemoryId")}
    if len(project_ids) < threshold:
        return None
    rollback_id, rollback_errors = rollback_to_previous(runtime_root, version_id=record_dir.name, reason="observation_quality_failure")
    append_memory_log(
        runtime_root,
        action="observation_rollback",
        memorySignalIds=[event.get("eventId", "") for event in severe_events],
        decision="rollback" if not rollback_errors else "rollback_failed",
        reasonSummary="观察期内多个项目出现严重质量失败。",
        result=rollback_id or "; ".join(rollback_errors),
    )
    return {"action": "observation_rollback", "id": rollback_id, "errors": rollback_errors}


def import_memory_archive(runtime_root, archive_path):
    paths = ensure_memory_dirs(runtime_root)
    archive_path = Path(archive_path)
    import_id = new_id("import")
    target_dir = paths["imports"] / import_id
    target_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "importId": import_id,
        "createdAt": now_iso(),
        "source": str(archive_path),
        "importedEvents": 0,
        "duplicates": 0,
        "staged": 0,
        "errors": [],
    }
    existing_ids = {event.get("eventId") for event in read_jsonl(paths["events"])}
    try:
        rows = read_jsonl(archive_path)
    except OSError as error:
        summary["errors"].append(str(error))
        return summary
    for row in rows:
        event_id = row.get("eventId")
        if not event_id:
            summary["errors"].append("导入事件缺少 eventId。")
            continue
        if event_id in existing_ids:
            summary["duplicates"] += 1
            continue
        row = deepcopy(row)
        row["qualification"] = "staged"
        row["weight"] = 0.0
        row["importId"] = import_id
        append_jsonl(paths["staged"], row)
        summary["staged"] += 1
    summary["importedEvents"] = len(rows)
    (target_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_memory_log(
        runtime_root,
        action="memory_archive_imported",
        decision="stage_only",
        reasonSummary="手动导入记忆归档，暂存等待后续项目验证。",
        result=import_id,
    )
    return summary
