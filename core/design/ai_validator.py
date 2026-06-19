import json
from copy import deepcopy

from core.design.ai_interview import HIGH_CONFIDENCE_THRESHOLD, ensure_ai_interview, now_iso
from core.design.engine import NODE_STATES


CONCRETE_ROLE_CLASSES = {"system_concrete", "content_concrete"}


def validate_ai_response_payload(payload):
    errors = []
    if not isinstance(payload, dict):
        return ["AI 输出不是 JSON 对象。"]
    if not payload.get("schemaVersion"):
        errors.append("AI 输出缺少 schemaVersion。")
    if payload.get("mode") not in {
        "question_group",
        "confirmation",
        "readiness_check",
        "full_project_output",
        "partial_project_output",
        "maintenance",
        "error",
    }:
        errors.append(f"AI 输出 mode 非法：{payload.get('mode')}")
    if not isinstance(payload.get("assistantMessage"), str) or not payload.get("assistantMessage", "").strip():
        errors.append("AI 输出缺少 assistantMessage。")
    question_group = payload.get("questionGroup")
    if isinstance(question_group, dict):
        questions = question_group.get("questions", [])
        if not isinstance(questions, list):
            errors.append("questionGroup.questions 必须是数组。")
        elif len(questions) > 4:
            errors.append("追问问题组最多 4 个问题。")
    return errors


def full_project_output(payload):
    if not isinstance(payload, dict):
        return None
    output = payload.get("fullProjectOutput")
    return output if isinstance(output, dict) else None


def partial_project_output(payload):
    if not isinstance(payload, dict):
        return None
    output = payload.get("partialProjectOutput")
    return output if isinstance(output, dict) else None


def parse_json_value(value):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        return json.loads(value)
    return None


def candidate_project_state(payload):
    output = full_project_output(payload)
    if not output:
        return None
    state = output.get("projectState")
    if state is None:
        state = parse_json_value(output.get("projectStateJson"))
    return state if isinstance(state, dict) else None


def candidate_project_patch(payload):
    output = partial_project_output(payload)
    if not output:
        return None
    patch = output.get("projectStatePatch")
    if patch is None:
        patch = parse_json_value(output.get("projectStatePatchJson"))
    return patch if isinstance(patch, dict) else None


def confidence_map(payload):
    output = full_project_output(payload) or partial_project_output(payload) or {}
    value = output.get("confidenceMap") or output.get("confidence") or {}
    if not value:
        try:
            value = parse_json_value(output.get("confidenceMapJson")) or {}
        except json.JSONDecodeError:
            value = {}
    return value if isinstance(value, dict) else {}


def nested_confidence(confidence, section, *keys):
    section_value = confidence.get(section, {})
    if not isinstance(section_value, dict):
        return 0.0
    dotted = ".".join(keys)
    value = section_value.get(dotted)
    if value is None and keys:
        value = section_value
        for key in keys:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def node_confidence(confidence, node_id):
    return nested_confidence(confidence, "nodes", node_id)


def item_confidence(confidence, node_id, item_id):
    return max(
        nested_confidence(confidence, "items", node_id, item_id),
        nested_confidence(confidence, "items", f"{node_id}.{item_id}"),
    )


def group_confidence(confidence, node_id, item_id, group_id):
    return max(
        nested_confidence(confidence, "groups", node_id, item_id, group_id),
        nested_confidence(confidence, "groups", f"{node_id}.{item_id}.{group_id}"),
        item_confidence(confidence, node_id, item_id),
        node_confidence(confidence, node_id),
    )


def validate_node_design_entities(engine, node, node_state, errors):
    node_id = node["id"]
    if "entityValidationErrors" in node_state and not isinstance(node_state.get("entityValidationErrors"), list):
        errors.append(f"node {node_id} entityValidationErrors must be an array.")

    if "designEntities" not in node_state:
        return

    raw_entities = node_state.get("designEntities", [])
    if raw_entities in (None, ""):
        raw_entities = []

    if raw_entities and node.get("roleClass") not in CONCRETE_ROLE_CLASSES:
        errors.append(
            f"node {node_id} has roleClass={node.get('roleClass', '')} and cannot write designEntities."
        )

    _, entity_errors = engine.normalize_node_design_entities(raw_entities, node_id)
    if not entity_errors:
        return

    for error in entity_errors[:8]:
        schema_id = error.get("schemaId", "")
        schema_suffix = f" ({schema_id})" if schema_id else ""
        errors.append(
            f"node {node_id} designEntities invalid at {error.get('path', 'designEntities')}"
            f"{schema_suffix}: {error.get('message', 'invalid entity')}"
        )
    if len(entity_errors) > 8:
        errors.append(f"node {node_id} designEntities has {len(entity_errors) - 8} more validation errors.")


def validate_project_state_output(engine, state):
    errors = []
    if not isinstance(state, dict):
        return ["fullProjectOutput.projectState 必须是对象。"]
    nodes_state = state.get("nodes")
    if not isinstance(nodes_state, dict):
        return ["fullProjectOutput.projectState.nodes 必须是对象。"]

    expected_node_ids = {node["id"] for node in engine.nodes}
    actual_node_ids = set(nodes_state)
    missing = sorted(expected_node_ids - actual_node_ids)
    unknown = sorted(actual_node_ids - expected_node_ids)
    if missing:
        errors.append(f"AI 全项目输出缺少节点：{', '.join(missing[:12])}")
    if unknown:
        errors.append(f"AI 全项目输出包含未知节点：{', '.join(unknown[:12])}")

    for node in engine.nodes:
        node_id = node["id"]
        node_state = nodes_state.get(node_id, {})
        if not isinstance(node_state, dict):
            errors.append(f"节点 {node_id} 状态必须是对象。")
            continue
        decision_state = node_state.get("decisionState", "not_started")
        if decision_state not in NODE_STATES:
            errors.append(f"节点 {node_id} decisionState 非法：{decision_state}")
        checklist = node_state.get("checklist", {})
        checklist_options = node_state.get("checklistOptions", {})
        if not isinstance(checklist, dict):
            errors.append(f"节点 {node_id} checklist 必须是对象。")
            checklist = {}
        if not isinstance(checklist_options, dict):
            errors.append(f"节点 {node_id} checklistOptions 必须是对象。")
            checklist_options = {}
        validate_node_design_entities(engine, node, node_state, errors)

        expected_item_ids = {item["id"] for item in node.get("checklist", [])}
        unknown_items = sorted((set(checklist) | set(checklist_options)) - expected_item_ids)
        if unknown_items:
            errors.append(f"节点 {node_id} 包含未知 checklist：{', '.join(unknown_items[:8])}")

        for item in node.get("checklist", []):
            item_id = item["id"]
            item_options = checklist_options.get(item_id, {})
            if item_options is None:
                item_options = {}
            if not isinstance(item_options, dict):
                errors.append(f"节点 {node_id} / {item_id} checklistOptions 必须是对象。")
                continue
            expected_group_ids = {group["id"] for group in item.get("optionGroups", [])}
            unknown_groups = sorted(set(item_options) - expected_group_ids)
            if unknown_groups:
                errors.append(f"节点 {node_id} / {item_id} 包含未知 L4 组：{', '.join(unknown_groups[:8])}")
            for group in item.get("optionGroups", []):
                group_id = group["id"]
                group_state = item_options.get(group_id, {})
                if group_state is None:
                    group_state = {}
                if not isinstance(group_state, dict):
                    errors.append(f"节点 {node_id} / {item_id} / {group_id} 状态必须是对象。")
                    continue
                selected = group_state.get("selected", [])
                if selected is None:
                    selected = []
                if not isinstance(selected, list):
                    errors.append(f"节点 {node_id} / {item_id} / {group_id} selected 必须是数组。")
                    selected = []
                allowed = {option["id"] for option in group.get("options", [])}
                invalid = [option_id for option_id in selected if option_id not in allowed]
                if invalid:
                    errors.append(f"节点 {node_id} / {item_id} / {group_id} 包含未知选项：{', '.join(invalid[:8])}")
                if group.get("selectionMode") == "single" and len(selected) > 1:
                    errors.append(f"节点 {node_id} / {item_id} / {group_id} 是单选但 selected 超过 1 个。")
                primary = group_state.get("primary", "")
                if primary and primary not in selected:
                    errors.append(f"节点 {node_id} / {item_id} / {group_id} primary 不在 selected 中。")
    if "gameplaySystems" in state:
        if not isinstance(state.get("gameplaySystems"), dict):
            errors.append("gameplaySystems 必须是对象。")
        else:
            engine.gameplay_systems_state(state)
    return errors


def validate_node_state_subset(engine, node, node_state, errors):
    node_id = node["id"]
    if not isinstance(node_state, dict):
        errors.append(f"节点 {node_id} 状态必须是对象。")
        return
    decision_state = node_state.get("decisionState", "not_started")
    if decision_state not in NODE_STATES:
        errors.append(f"节点 {node_id} decisionState 非法：{decision_state}")
    checklist = node_state.get("checklist", {})
    checklist_options = node_state.get("checklistOptions", {})
    if not isinstance(checklist, dict):
        errors.append(f"节点 {node_id} checklist 必须是对象。")
        checklist = {}
    if not isinstance(checklist_options, dict):
        errors.append(f"节点 {node_id} checklistOptions 必须是对象。")
        checklist_options = {}
    validate_node_design_entities(engine, node, node_state, errors)

    expected_item_ids = {item["id"] for item in node.get("checklist", [])}
    unknown_items = sorted((set(checklist) | set(checklist_options)) - expected_item_ids)
    if unknown_items:
        errors.append(f"节点 {node_id} 包含未知 checklist：{', '.join(unknown_items[:8])}")

    for item in node.get("checklist", []):
        item_id = item["id"]
        item_options = checklist_options.get(item_id, {})
        if item_options is None:
            item_options = {}
        if not isinstance(item_options, dict):
            errors.append(f"节点 {node_id} / {item_id} checklistOptions 必须是对象。")
            continue
        expected_group_ids = {group["id"] for group in item.get("optionGroups", [])}
        unknown_groups = sorted(set(item_options) - expected_group_ids)
        if unknown_groups:
            errors.append(f"节点 {node_id} / {item_id} 包含未知 L4 组：{', '.join(unknown_groups[:8])}")
        for group in item.get("optionGroups", []):
            group_id = group["id"]
            if group_id not in item_options:
                continue
            group_state = item_options.get(group_id, {})
            if group_state is None:
                group_state = {}
            if not isinstance(group_state, dict):
                errors.append(f"节点 {node_id} / {item_id} / {group_id} 状态必须是对象。")
                continue
            selected = group_state.get("selected", [])
            if selected is None:
                selected = []
            if not isinstance(selected, list):
                errors.append(f"节点 {node_id} / {item_id} / {group_id} selected 必须是数组。")
                selected = []
            allowed = {option["id"] for option in group.get("options", [])}
            invalid = [option_id for option_id in selected if option_id not in allowed]
            if invalid:
                errors.append(f"节点 {node_id} / {item_id} / {group_id} 包含未知选项：{', '.join(invalid[:8])}")
            if group.get("selectionMode") == "single" and len(selected) > 1:
                errors.append(f"节点 {node_id} / {item_id} / {group_id} 是单选但 selected 超过 1 个。")
            primary = group_state.get("primary", "")
            if primary and primary not in selected:
                errors.append(f"节点 {node_id} / {item_id} / {group_id} primary 不在 selected 中。")


def validate_partial_project_output(engine, payload, allowed_domain_ids=None):
    errors = validate_ai_response_payload(payload)
    output = partial_project_output(payload)
    if payload.get("mode") == "partial_project_output" or output:
        if not output:
            errors.append("AI 输出 mode=partial_project_output 但缺少 partialProjectOutput。")
            return errors
        allowed_domain_ids = set(allowed_domain_ids or output.get("domainIds", []) or [])
        try:
            patch = candidate_project_patch(payload)
        except json.JSONDecodeError as error:
            patch = None
            errors.append(f"partialProjectOutput.projectStatePatchJson 不是合法 JSON：{error}")
        if not isinstance(patch, dict):
            errors.append("partialProjectOutput 缺少 projectStatePatch。")
            return errors
        nodes_state = patch.get("nodes", {})
        if not isinstance(nodes_state, dict):
            errors.append("partialProjectOutput.projectStatePatch.nodes 必须是对象。")
            return errors
        if "gameplaySystems" in patch and not isinstance(patch.get("gameplaySystems"), dict):
            errors.append("partialProjectOutput.projectStatePatch.gameplaySystems 必须是对象。")
        for node_id, node_state in nodes_state.items():
            node = engine.node_by_id.get(node_id)
            if not node:
                errors.append(f"AI 分片输出包含未知节点：{node_id}")
                continue
            if allowed_domain_ids and node.get("domain") not in allowed_domain_ids:
                errors.append(f"AI 分片输出节点 {node_id} 不属于允许领域：{node.get('domain')}")
                continue
            validate_node_state_subset(engine, node, node_state, errors)
    return errors


def validate_full_project_output(engine, payload):
    errors = validate_ai_response_payload(payload)
    output = full_project_output(payload)
    if payload.get("mode") == "full_project_output" or output:
        if not output:
            errors.append("AI 输出 mode=full_project_output 但缺少 fullProjectOutput。")
        else:
            try:
                state = candidate_project_state(payload)
            except json.JSONDecodeError as error:
                state = None
                errors.append(f"fullProjectOutput.projectStateJson 不是合法 JSON：{error}")
            if not isinstance(state, dict):
                errors.append("fullProjectOutput 缺少 projectState。")
            else:
                errors.extend(validate_project_state_output(engine, state))
    return errors


def merge_confidence_maps(left, right):
    merged = deepcopy(left or {})
    for section, values in (right or {}).items():
        if not isinstance(values, dict):
            continue
        section_payload = merged.setdefault(section, {})
        if not isinstance(section_payload, dict):
            section_payload = {}
            merged[section] = section_payload
        for key, value in values.items():
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            previous = section_payload.get(key)
            try:
                previous = float(previous)
            except (TypeError, ValueError):
                previous = 0.0
            section_payload[key] = max(previous, value)
    return merged


def merge_partial_project_outputs(engine, current_state, payloads):
    candidate = engine.normalize_state(deepcopy(current_state))
    confidence = {}
    summaries = []
    inferences = []
    domain_ids = []
    errors = []
    for payload in payloads or []:
        output = partial_project_output(payload)
        allowed = output.get("domainIds", []) if output else []
        domain_ids.extend(str(item) for item in allowed if item)
        validation_errors = validate_partial_project_output(engine, payload, allowed_domain_ids=allowed)
        if validation_errors:
            errors.extend(validation_errors)
            continue
        try:
            patch = candidate_project_patch(payload) or {}
        except json.JSONDecodeError as error:
            errors.append(f"partialProjectOutput.projectStatePatchJson 不是合法 JSON：{error}")
            continue
        if "projectName" in patch:
            candidate["projectName"] = patch.get("projectName") or candidate.get("projectName", "")
        if isinstance(patch.get("profile"), dict):
            candidate["profile"].update(patch.get("profile", {}))
        if isinstance(patch.get("gameplaySystems"), dict):
            candidate["gameplaySystems"] = engine.gameplay_systems_state(patch)
        for node_id, node_state in (patch.get("nodes", {}) or {}).items():
            if node_id in candidate.get("nodes", {}) and isinstance(node_state, dict):
                candidate["nodes"][node_id] = deepcopy(node_state)
        confidence = merge_confidence_maps(confidence, confidence_map(payload))
        summaries.append(output.get("summary", "") if output else "")
        inferences.extend(payload.get("inferences", []) or [])
    if errors:
        return None, errors
    merged_payload = {
        "schemaVersion": "1.0",
        "mode": "full_project_output",
        "assistantMessage": "AI 分片输出已合并为全项目候选。",
        "routeOverview": (payloads or [{}])[-1].get("routeOverview", {}) if payloads else {},
        "inferences": inferences,
        "fullProjectOutput": {
            "projectStateJson": json.dumps(engine.normalize_state(candidate), ensure_ascii=False),
            "confidenceMapJson": json.dumps(confidence, ensure_ascii=False),
            "summary": "；".join(summary for summary in summaries if summary),
        },
        "optionDifferences": [],
        "mergeMeta": {
            "source": "partial_project_outputs",
            "domainIds": sorted(set(domain_ids)),
            "partCount": len(payloads or []),
        },
    }
    errors = validate_full_project_output(engine, merged_payload)
    return (merged_payload if not errors else None), errors


def option_labels_by_ids(group, option_ids):
    labels = []
    by_id = {option["id"]: option for option in group.get("options", [])}
    for option_id in option_ids:
        labels.append(by_id.get(option_id, {}).get("label", option_id))
    return labels


def entity_labels(entities):
    labels = []
    for entity in entities or []:
        if not isinstance(entity, dict):
            labels.append(str(entity))
            continue
        kind = str(entity.get("kind") or entity.get("schema") or "entity")
        label = str(entity.get("label") or entity.get("id") or kind)
        labels.append(f"{kind}:{label}")
    return labels


def diff_project_options(engine, before, after, threshold=HIGH_CONFIDENCE_THRESHOLD, confidence=None):
    confidence = confidence or {}
    differences = []
    before_gameplay = engine.gameplay_systems_state(deepcopy(before))
    after_gameplay = engine.gameplay_systems_state(deepcopy(after))
    before_selected = set(before_gameplay.get("selected", []))
    after_selected = set(after_gameplay.get("selected", []))
    gameplay_names = {
        option["id"]: option.get("name", option["id"])
        for option in engine.gameplay_all_options({"gameplaySystems": after_gameplay})
    }
    for system_id in sorted(before_selected | after_selected):
        before_parts = []
        after_parts = []
        if system_id in before_selected:
            before_parts.append("已选")
            weight = before_gameplay.get("weights", {}).get(system_id, {}).get("weight", "")
            if weight not in ("", None):
                before_parts.append(f"{weight}%")
        if system_id in after_selected:
            after_parts.append("已选")
            weight = after_gameplay.get("weights", {}).get(system_id, {}).get("weight", "")
            if weight not in ("", None):
                after_parts.append(f"{weight}%")
        if before_parts != after_parts:
            differences.append({
                "type": "gameplay_system",
                "nodeId": "",
                "nodeName": "玩法系统设计",
                "itemId": system_id,
                "itemLabel": gameplay_names.get(system_id, system_id),
                "groupId": "",
                "groupLabel": "",
                "before": before_parts,
                "after": after_parts,
                "confidence": node_confidence(confidence, "gameplaySystems"),
                "highConfidence": node_confidence(confidence, "gameplaySystems") >= threshold,
            })
    before_nodes = before.get("nodes", {})
    after_nodes = after.get("nodes", {})
    for node in engine.nodes:
        node_id = node["id"]
        before_node = before_nodes.get(node_id, {})
        after_node = after_nodes.get(node_id, {})
        before_state = before_node.get("decisionState", "not_started")
        after_state = after_node.get("decisionState", "not_started")
        node_score = node_confidence(confidence, node_id)
        if before_state != after_state:
            differences.append({
                "type": "node_state",
                "nodeId": node_id,
                "nodeName": node.get("name", node_id),
                "before": [before_state],
                "after": [after_state],
                "confidence": node_score,
            })
        before_entities = before_node.get("designEntities", [])
        after_entities = after_node.get("designEntities", [])
        if before_entities != after_entities:
            differences.append({
                "type": "design_entities",
                "nodeId": node_id,
                "nodeName": node.get("name", node_id),
                "itemId": "",
                "groupId": "",
                "before": entity_labels(before_entities),
                "after": entity_labels(after_entities),
                "confidence": node_score,
                "highConfidence": node_score >= threshold,
            })
        for item in node.get("checklist", []):
            item_id = item["id"]
            before_item_options = before_node.get("checklistOptions", {}).get(item_id, {})
            after_item_options = after_node.get("checklistOptions", {}).get(item_id, {})
            for group in item.get("optionGroups", []):
                group_id = group["id"]
                before_selected = before_item_options.get(group_id, {}).get("selected", [])
                after_selected = after_item_options.get(group_id, {}).get("selected", [])
                if before_selected == after_selected:
                    continue
                differences.append({
                    "type": "option_group",
                    "nodeId": node_id,
                    "nodeName": node.get("name", node_id),
                    "itemId": item_id,
                    "itemLabel": item.get("label", item_id),
                    "groupId": group_id,
                    "groupLabel": group.get("label", group_id),
                    "before": option_labels_by_ids(group, before_selected),
                    "after": option_labels_by_ids(group, after_selected),
                    "confidence": group_confidence(confidence, node_id, item_id, group_id),
                    "highConfidence": group_confidence(confidence, node_id, item_id, group_id) >= threshold,
                })
    return differences


def apply_high_confidence_output(engine, current_state, payload, threshold=HIGH_CONFIDENCE_THRESHOLD):
    output = full_project_output(payload)
    if not output:
        return current_state, []
    try:
        state_payload = candidate_project_state(payload) or {}
    except json.JSONDecodeError:
        state_payload = {}
    candidate = engine.normalize_state(state_payload)
    confidence = confidence_map(payload)
    result = engine.empty_state()
    result["projectName"] = candidate.get("projectName", current_state.get("projectName", result["projectName"]))
    result["profile"] = deepcopy(candidate.get("profile", current_state.get("profile", result["profile"])))
    gameplay_score = node_confidence(confidence, "gameplaySystems")
    if gameplay_score >= threshold and "gameplaySystems" in candidate:
        result["gameplaySystems"] = deepcopy(candidate.get("gameplaySystems", result.get("gameplaySystems", {})))
    else:
        result["gameplaySystems"] = deepcopy(current_state.get("gameplaySystems", result.get("gameplaySystems", {})))

    for node in engine.nodes:
        node_id = node["id"]
        candidate_node = candidate.get("nodes", {}).get(node_id, {})
        result_node = result["nodes"].setdefault(node_id, {})
        node_score = node_confidence(confidence, node_id)
        candidate_state = candidate_node.get("decisionState", "not_started")
        if candidate_state == "not_applicable" and node_score >= threshold:
            result_node["decisionState"] = "not_applicable"
            result_node["notApplicableReason"] = candidate_node.get("notApplicableReason", "")
            continue

        if node_score >= threshold:
            result_node["designNote"] = candidate_node.get("designNote", "")
            if candidate_state == "risk":
                result_node["riskNote"] = candidate_node.get("riskNote", "")
            if node.get("roleClass") in CONCRETE_ROLE_CLASSES and "designEntities" in candidate_node:
                design_entities, entity_errors = engine.normalize_node_design_entities(
                    candidate_node.get("designEntities", []),
                    node_id,
                )
                if not entity_errors:
                    result_node["designEntities"] = design_entities
                    result_node["entityValidationErrors"] = []

        for item in node.get("checklist", []):
            item_id = item["id"]
            candidate_item_options = candidate_node.get("checklistOptions", {}).get(item_id, {})
            copied_item = False
            for group in item.get("optionGroups", []):
                group_id = group["id"]
                score = group_confidence(confidence, node_id, item_id, group_id)
                if score < threshold:
                    continue
                candidate_group = candidate_item_options.get(group_id, {})
                selected = list(candidate_group.get("selected", []))
                primary = candidate_group.get("primary", "")
                result_group = (
                    result_node.setdefault("checklistOptions", {})
                    .setdefault(item_id, {})
                    .setdefault(group_id, {"selected": [], "primary": ""})
                )
                result_group["selected"] = selected
                result_group["primary"] = primary if primary in selected else ""
                if selected:
                    copied_item = True
            if copied_item or (
                item_confidence(confidence, node_id, item_id) >= threshold
                and candidate_node.get("checklist", {}).get(item_id)
            ):
                result_node.setdefault("checklist", {})[item_id] = True
        engine.refresh_node_state(result, node_id)

    ai_state = ensure_ai_interview(result)
    previous_ai = current_state.get("aiInterview")
    if isinstance(previous_ai, dict):
        result["aiInterview"] = deepcopy(previous_ai)
        ai_state = ensure_ai_interview(result)
    differences = diff_project_options(engine, current_state, result, threshold=threshold, confidence=confidence)
    ai_state["optionDifferences"] = differences
    ai_state.setdefault("outputHistory", []).append({
        "createdAt": now_iso(),
        "summary": output.get("summary", ""),
        "appliedDifferenceCount": len(differences),
        "threshold": threshold,
    })
    ai_state["updatedAt"] = now_iso()
    return engine.normalize_state(result), differences


def format_differences(differences, limit=80):
    if not differences:
        return ["本次 AI 输出没有写入新的高置信选项差异。"]
    lines = []
    for diff in differences[:limit]:
        if diff.get("type") == "node_state":
            lines.append(
                f"- {diff.get('nodeName', diff.get('nodeId'))}："
                f"{'、'.join(diff.get('before', [])) or '无'} -> {'、'.join(diff.get('after', [])) or '无'}"
            )
        elif diff.get("type") == "gameplay_system":
            before = "、".join(diff.get("before", [])) or "未选"
            after = "、".join(diff.get("after", [])) or "未选"
            lines.append(
                f"- 玩法系统 / {diff.get('itemLabel', diff.get('itemId'))}："
                f"{before} -> {after}（置信度 {diff.get('confidence', 0):.2f}）"
            )
        else:
            before = "、".join(diff.get("before", [])) or "未选"
            after = "、".join(diff.get("after", [])) or "未选"
            lines.append(
                f"- {diff.get('nodeName')} / {diff.get('itemLabel')} / {diff.get('groupLabel')}："
                f"{before} -> {after}（置信度 {diff.get('confidence', 0):.2f}）"
            )
    if len(differences) > limit:
        lines.append(f"- 还有 {len(differences) - limit} 条差异未显示。")
    return lines
