import json
import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from core.design.engine import STATE_LABELS
from core.design.profile_schema import display_profile, field_label, option_label


EXPORT_SCHEMA_VERSION = "0.5.0"
DOCUMENT_VERSION = 1
TAXONOMY_VERSION = "v1"
PROVENANCE_AUTHOR = "exporter_compatibility_layer"

REVERSE_INFERENCE_HINTS = (
    "范本反推",
    "反推",
    "非官方配置",
    "公开信息",
)

GENERIC_RATIONALE_HINTS = (
    "基于公开信息与设计分析反推",
    "部分 L4 为基于同品类结构的合理推断",
    "明确",
    "确认",
    "记录",
    "说明",
)

DOMAIN_STAGE_INDEX = {
    "product_positioning_design": [0, 1, 2, 7, 13],
    "core_experience_design": [1, 2, 3, 7, 10],
    "gameplay_system_design": [1, 2, 3, 7, 10],
    "content_design": [2, 3, 5, 7, 10],
    "balance_design": [2, 7, 8, 10],
    "economy_monetization_design": [2, 7, 8, 13],
    "ux_interface_design": [5, 8, 11],
    "presentation_feel_design": [5, 8, 11],
    "social_community_design": [7, 10, 13],
    "retention_lifecycle_design": [7, 13, 14, 15],
    "liveops_version_design": [7, 13, 14, 15],
    "release_growth_design": [7, 13, 14, 15],
    "launch_readiness_design": [7, 13, 14, 15],
    "documentation_collaboration_design": [2, 7, 10, 13],
    "data_validation_design": [2, 7, 10, 13],
    "compliance_risk_design": [2, 7, 10, 13],
}


def safe_file_name(value, fallback="commercial-game-design"):
    cleaned = "".join("_" if char in '\\/:*?\"<>|' else char for char in value.strip())
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned or fallback


def option_label_by_id(group, option_id):
    for option in group.get("options", []):
        if option.get("id") == option_id:
            return option.get("label", option_id)
    return option_id


def option_ref_label(item, group_id, option_id):
    for group in item.get("optionGroups", []):
        if group.get("id") != group_id:
            continue
        return f"{group.get('label', group_id)} / {option_label_by_id(group, option_id)}"
    return f"{group_id} / {option_id}"


def selected_option_refs(item, node_state):
    item_options = node_state.get("checklistOptions", {}).get(item["id"], {})
    refs = set()
    for group_id, group_state in item_options.items():
        for option_id in group_state.get("selected", []):
            refs.add((group_id, option_id))
    return refs


def stable_json_hash(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def taxonomy_fingerprint(engine):
    canonical = []
    for domain_doc in engine.domains:
        domain = domain_doc.get("domain", {})
        for node in domain_doc.get("nodes", []):
            node_entry = {
                "domain": domain.get("id", ""),
                "node": node.get("id", ""),
                "roleClass": node.get("roleClass", ""),
                "requires": sorted(node.get("requires", [])),
                "unlocks": sorted(node.get("unlocks", [])),
                "checklist": [],
            }
            for item in node.get("checklist", []):
                item_entry = {
                    "id": item.get("id", ""),
                    "outputKey": item.get("outputKey", ""),
                    "templateRef": item.get("templateRef", ""),
                    "optionGroups": [],
                    "optionRelations": item.get("optionRelations", []),
                }
                for group in item.get("optionGroups", []):
                    item_entry["optionGroups"].append({
                        "id": group.get("id", ""),
                        "outputKey": group.get("outputKey", ""),
                        "selectionMode": group.get("selectionMode", ""),
                        "required": bool(group.get("required")),
                        "allowPrimary": bool(group.get("allowPrimary")),
                        "mdaLayer": group.get("mdaLayer", ""),
                        "progressionStep": group.get("progressionStep", 0),
                        "options": [
                            {
                                "id": option.get("id", ""),
                                "outputKey": option.get("outputKey", ""),
                            }
                            for option in group.get("options", [])
                        ],
                    })
                node_entry["checklist"].append(item_entry)
            canonical.append(node_entry)
    return stable_json_hash(canonical)


def infer_document_type(project_state):
    explicit = project_state.get("documentType") or project_state.get("document_type")
    if explicit:
        return explicit
    project_name = project_state.get("projectName", "")
    all_text = " ".join(
        [
            project_name,
            *(
                node_state.get("designNote", "")
                for node_state in project_state.get("nodes", {}).values()
                if isinstance(node_state, dict)
            ),
        ]
    )
    if project_name.startswith("范本") or any(hint in all_text for hint in REVERSE_INFERENCE_HINTS):
        return "template_reverse_inferred"
    return "project_answer"


def infer_authoring_source(document_type):
    if document_type == "template_reverse_inferred":
        return "reverse_inference_from_public_info"
    if document_type == "mixed":
        return "mixed"
    return "internal_design"


def infer_overall_confidence(project_state, document_type):
    if document_type == "template_reverse_inferred":
        notes = [
            node_state.get("designNote", "")
            for node_state in project_state.get("nodes", {}).values()
            if isinstance(node_state, dict)
        ]
        if any("合理推断" in note or "部分" in note for note in notes):
            return "mid"
        return "high"
    if document_type == "mixed":
        return "mid"
    return "high"


def profile_case_genre(profile):
    genres = []
    target_scale = profile.get("targetScale")
    business_model = profile.get("businessModel")
    operation_model = profile.get("operationModel")
    social_model = profile.get("socialModel")
    session_band = profile.get("targetSessionBand")
    if target_scale and target_scale != "unknown":
        genres.append(target_scale)
    if business_model and business_model != "unknown":
        genres.append(business_model)
    if operation_model and operation_model != "unknown":
        genres.append(operation_model)
    if social_model and social_model != "unknown":
        genres.append(social_model)
    if session_band and session_band != "unknown":
        genres.append(session_band)
    return genres


def profile_applicability(profile):
    items = []
    target_scale = profile.get("targetScale")
    primary_platform = profile.get("primaryPlatform")
    session_band = profile.get("targetSessionBand")
    business_model = profile.get("businessModel")
    social_model = profile.get("socialModel")
    if target_scale and target_scale != "unknown":
        items.append(f"项目规模适配：{option_label('targetScale', target_scale)}")
    if primary_platform and primary_platform != "unknown":
        items.append(f"主平台适配：{option_label('primaryPlatform', primary_platform)}")
    if session_band and session_band != "unknown":
        items.append(f"单次时长适配：{option_label('targetSessionBand', session_band)}")
    if business_model and business_model != "unknown":
        items.append(f"商业模式适配：{option_label('businessModel', business_model)}")
    if social_model and social_model != "unknown":
        items.append(f"社交结构适配：{option_label('socialModel', social_model)}")
    return items


def profile_not_applicable(profile):
    items = []
    target_scale = profile.get("targetScale")
    primary_platform = profile.get("primaryPlatform")
    session_band = profile.get("targetSessionBand")
    social_model = profile.get("socialModel")
    if target_scale == "iaa_hypercasual":
        items.extend(["重度数值养成主导项目", "大型长线服务项目"])
    elif target_scale == "3a":
        items.extend(["极短平快 IAA 超休闲项目", "低成本快速试错项目"])
    elif target_scale == "large_service":
        items.append("离线单次发布项目")
    if primary_platform == "mobile":
        items.append("PC / 主机输入优先项目")
    elif primary_platform == "pc_console":
        items.append("手机触屏优先项目")
    if session_band in {"session_1_3", "session_3_10"}:
        items.append("单局 20 分钟以上深度会话项目")
    if social_model == "none":
        items.append("多人实时对抗或强社区驱动项目")
    return items


def build_document_metadata(project_state, taxonomy_hash, exported_at):
    profile = project_state.get("profile", {})
    document_type = infer_document_type(project_state)
    return {
        "document_type": document_type,
        "document_version": DOCUMENT_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy_hash": taxonomy_hash,
        "case_name": project_state.get("projectName", ""),
        "case_genre": profile_case_genre(profile),
        "case_applicability": profile_applicability(profile),
        "not_applicable_to": profile_not_applicable(profile),
        "authoring_source": infer_authoring_source(document_type),
        "authoring_confidence_overall": infer_overall_confidence(project_state, document_type),
        "exported_at": exported_at,
    }


def selection_state_for_node(node_state, document_type):
    explicit = node_state.get("selectionState") or node_state.get("selection_state")
    if explicit:
        return explicit
    decision_state = node_state.get("decisionState", "not_started")
    if decision_state == "not_applicable":
        return "not_applicable"
    if decision_state == "not_started":
        return "open"
    if document_type == "template_reverse_inferred":
        return "reverse_inferred"
    if document_type == "mixed" and any(hint in node_state.get("designNote", "") for hint in REVERSE_INFERENCE_HINTS):
        return "reverse_inferred"
    return "answered"


def confidence_for_node(node_state, selection_state, document_metadata):
    explicit = node_state.get("confidence") or node_state.get("authoringConfidence")
    if explicit:
        return explicit
    if selection_state == "open":
        return "low"
    if selection_state == "not_applicable":
        return "high"
    if selection_state == "reverse_inferred":
        note = node_state.get("designNote", "")
        if "部分" in note or "合理推断" in note:
            return "mid"
        return document_metadata.get("authoring_confidence_overall", "mid")
    return "high"


def derives_to_stage_for_node(node):
    explicit = node.get("derivesToStage") or node.get("derives_to_stage")
    if explicit:
        return explicit
    domain_id = node.get("domain", "")
    return DOMAIN_STAGE_INDEX.get(domain_id, [2, 7, 13])


def depends_on_for_node(node):
    deps = []
    for field_name in ("requires", "recommendedBefore", "requiresAny"):
        deps.extend(node.get(field_name, []))
    return sorted(dict.fromkeys(deps))


def selection_rationale(node_state, selection_state, document_metadata):
    note = node_state.get("designNote", "").strip()
    risk = node_state.get("riskNote", "").strip()
    not_applicable = node_state.get("notApplicableReason", "").strip()
    if selection_state == "open":
        intent = "当前节点尚未形成可导出的设计回答。"
        evidence = "未填写。"
    elif selection_state == "not_applicable":
        intent = "该节点被明确标记为不适用。"
        evidence = not_applicable or "不适用原因未填写。"
    elif selection_state == "reverse_inferred":
        intent = note or "基于范本结构反推当前节点选择。"
        evidence = "公开信息与设计结构反推；非官方配置。"
    else:
        intent = note or "由项目当前状态确认。"
        evidence = "来自设计者在工具内记录的项目状态。"
    return {
        "intent": intent,
        "evidence": evidence,
        "locked_downstream": "见 derives_to_stage 与 depends_on_decisions。",
        "risks_and_alternatives": risk or ("仍需在后续 stage 复核低置信或反推项。" if selection_state == "reverse_inferred" else ""),
    }


def build_decision_metadata(node, node_state, document_metadata):
    selection_state = selection_state_for_node(node_state, document_metadata["document_type"])
    return {
        "id": node["id"],
        "selection_state": selection_state,
        "confidence": confidence_for_node(node_state, selection_state, document_metadata),
        "derives_to_stage": derives_to_stage_for_node(node),
        "depends_on_decisions": depends_on_for_node(node),
        "selection_rationale": selection_rationale(node_state, selection_state, document_metadata),
    }


def option_strength_for_group(group):
    if group.get("mdaLayer") == "constraints":
        return "hard_constraint"
    if group.get("required"):
        return "soft_preference"
    return "derived"


def option_treatment(selected, item_done):
    if selected:
        return "selected"
    if not item_done:
        return "deferred"
    return "not_evaluated"


def provenance_source_for_selection(document_metadata, decision_metadata):
    if decision_metadata.get("selection_state") == "reverse_inferred":
        return "reverse_inference"
    if decision_metadata.get("selection_state") == "not_applicable":
        return "operator_decision"
    if document_metadata.get("authoring_source") == "playtest_result":
        return "playtest_result"
    return "operator_decision"


def build_selection_provenance(document_metadata, decision_metadata, group, option, exported_at):
    source = provenance_source_for_selection(document_metadata, decision_metadata)
    if source == "reverse_inference":
        evidence = "由范本项目状态与公开信息反推生成；非官方配置。"
    else:
        evidence = "由当前项目状态导出。"
    return {
        "source": source,
        "evidence": evidence,
        "evidence_url": None,
        "confidence": decision_metadata.get("confidence", "mid"),
        "author": PROVENANCE_AUTHOR,
        "timestamp": exported_at,
    }


def count_payload_items(domains):
    totals = {
        "nodes": 0,
        "resolvedNodes": 0,
        "rationaleNodes": 0,
        "downstreamReadyNodes": 0,
        "checklist": 0,
        "selectedOrHandledChecklist": 0,
        "options": 0,
        "handledOptions": 0,
    }
    for domain_payload in domains:
        for node in domain_payload.get("nodes", []):
            totals["nodes"] += 1
            metadata = node.get("decisionMetadata", {})
            selection_state = metadata.get("selection_state", "open")
            if selection_state in {"answered", "not_applicable"}:
                totals["resolvedNodes"] += 1
            rationale = metadata.get("selection_rationale", {})
            rationale_text = " ".join(str(value) for value in rationale.values() if value)
            if rationale_text and not all(hint in rationale_text for hint in GENERIC_RATIONALE_HINTS[:2]):
                totals["rationaleNodes"] += 1
            if metadata.get("derives_to_stage") is not None and metadata.get("depends_on_decisions") is not None:
                totals["downstreamReadyNodes"] += 1
            for item in node.get("checklist", []):
                totals["checklist"] += 1
                if item.get("done") or any(group.get("selected") for group in item.get("optionGroups", [])):
                    totals["selectedOrHandledChecklist"] += 1
                for group in item.get("optionGroups", []):
                    for option in group.get("options", []):
                        totals["options"] += 1
                        if option.get("treatment") in {"selected", "rejected_with_reason", "deferred"}:
                            totals["handledOptions"] += 1
    return totals


def ratio(done, total):
    return round(done / total, 4) if total else 1.0


def build_coverage_metrics(project_coverage, domains):
    totals = count_payload_items(domains)
    return {
        "structural_coverage": round(project_coverage.get("nodePercent", 0) / 100, 4),
        "checklist_tick_coverage": round(project_coverage.get("checklistPercent", 0) / 100, 4),
        "selection_state_resolution": ratio(totals["resolvedNodes"], totals["nodes"]),
        "rationale_density": ratio(totals["rationaleNodes"], totals["nodes"]),
        "downstream_readiness": ratio(totals["downstreamReadyNodes"], totals["nodes"]),
        "option_treatment_resolution": ratio(totals["handledOptions"], totals["options"]),
        "counts": totals,
    }


def build_taxonomy_payload(engine, taxonomy_hash):
    dependency_edges = []
    derives_to_stage = {}
    compatibility = {"incompatibilities": [], "co_requirements": []}
    for domain_doc in engine.domains:
        for node in domain_doc.get("nodes", []):
            derives_to_stage[node["id"]] = derives_to_stage_for_node(node)
            for dependency_id in depends_on_for_node(node):
                dependency_edges.append({
                    "from": dependency_id,
                    "to": node["id"],
                    "relation": "requires",
                    "rule": f"{node['id']} should be reviewed after {dependency_id}",
                })
            for item in node.get("checklist", []):
                for relation in item.get("optionRelations", []):
                    bucket = "incompatibilities" if relation.get("type") in {"soft_conflict", "hard_exclusive"} else "co_requirements"
                    source = relation.get("source", {})
                    for target in relation.get("targets", []):
                        compatibility[bucket].append({
                            "decision_a": node["id"],
                            "item_a": item.get("id", ""),
                            "group_a": source.get("groupId", ""),
                            "option_a": source.get("optionId", ""),
                            "decision_b": node["id"],
                            "item_b": item.get("id", ""),
                            "group_b": target.get("groupId", ""),
                            "option_b": target.get("optionId", ""),
                            "severity": relation.get("severity", "warning"),
                            "message": relation.get("reason", ""),
                        })
    return {
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy_hash": taxonomy_hash,
        "previous_version": None,
        "deprecated_codes": [],
        "renamed_codes": [],
        "added_codes": [],
        "naming_convention": {
            "domain": "snake_case",
            "decision_id": "snake_case",
            "option_code": "snake_case_id_with_camelCase_outputKey",
            "profile_value": "snake_case",
        },
        "derives_to_stage": derives_to_stage,
        "decision_dependency_graph": {"edges": dependency_edges},
        "option_compatibility_matrix": compatibility,
    }


def build_option_relations_payload(item, node_state):
    selected_refs = selected_option_refs(item, node_state)
    relations = []
    for relation in item.get("optionRelations", []):
        source = relation.get("source", {})
        source_ref = (source.get("groupId"), source.get("optionId"))
        active_targets = []
        for target in relation.get("targets", []):
            target_ref = (target.get("groupId"), target.get("optionId"))
            active = source_ref in selected_refs and target_ref in selected_refs
            target_payload = {
                "groupId": target_ref[0],
                "optionId": target_ref[1],
                "label": option_ref_label(item, *target_ref),
                "active": active,
            }
            if active:
                active_targets.append(target_payload)
        relations.append({
            "id": relation.get("id", ""),
            "type": relation.get("type", ""),
            "severity": relation.get("severity", "warning"),
            "reason": relation.get("reason", ""),
            "source": {
                "groupId": source_ref[0],
                "optionId": source_ref[1],
                "label": option_ref_label(item, *source_ref),
                "selected": source_ref in selected_refs,
            },
            "targets": [
                {
                    "groupId": target.get("groupId"),
                    "optionId": target.get("optionId"),
                    "label": option_ref_label(item, target.get("groupId"), target.get("optionId")),
                    "selected": (target.get("groupId"), target.get("optionId")) in selected_refs,
                }
                for target in relation.get("targets", [])
            ],
            "active": bool(active_targets),
            "activeTargets": active_targets,
        })
    return relations


def active_conflicts_for_group(relations, group_id):
    conflicts = []
    for relation in relations:
        if relation.get("type") != "soft_conflict" or not relation.get("active"):
            continue
        source = relation.get("source", {})
        for target in relation.get("activeTargets", []):
            if group_id in (source.get("groupId"), target.get("groupId")):
                conflicts.append({
                    "id": relation.get("id", ""),
                    "reason": relation.get("reason", ""),
                    "source": source,
                    "target": target,
                })
    return conflicts


def build_option_groups_payload(item, node_state, relations, document_metadata, decision_metadata, exported_at):
    item_options = node_state.get("checklistOptions", {}).get(item["id"], {})
    item_done = bool(node_state.get("checklist", {}).get(item["id"]))
    groups = []
    for group in item.get("optionGroups", []):
        group_state = item_options.get(group["id"], {})
        selected_ids = group_state.get("selected", [])
        primary_id = group_state.get("primary", "")
        strength = option_strength_for_group(group)
        groups.append({
            "id": group["id"],
            "label": group["label"],
            "description": group.get("description", ""),
            "outputKey": group.get("outputKey", ""),
            "selectionMode": group.get("selectionMode", "multi"),
            "required": bool(group.get("required", False)),
            "allowPrimary": bool(group.get("allowPrimary", False)),
            "mdaLayer": group.get("mdaLayer", ""),
            "mdaLayerLabel": group.get("mdaLayerLabel", ""),
            "progressionStep": group.get("progressionStep", 0),
            "relation": group.get("relation", ""),
            "designQuestion": group.get("designQuestion", ""),
            "strength": strength,
            "selected": selected_ids,
            "selectedLabels": [option_label_by_id(group, option_id) for option_id in selected_ids],
            "primary": primary_id,
            "primaryLabel": option_label_by_id(group, primary_id) if primary_id else "",
            "activeConflicts": active_conflicts_for_group(relations, group["id"]),
            "options": [
                {
                    "id": option["id"],
                    "label": option["label"],
                    "description": option.get("description", ""),
                    "outputKey": option.get("outputKey", ""),
                    "selected": option["id"] in selected_ids,
                    "primary": option["id"] == primary_id,
                    "strength": strength,
                    "treatment": option_treatment(option["id"] in selected_ids, item_done),
                    "selectionProvenance": (
                        build_selection_provenance(document_metadata, decision_metadata, group, option, exported_at)
                        if option["id"] in selected_ids else None
                    ),
                }
                for option in group.get("options", [])
            ],
        })
    return groups


def build_payload(engine, project_state):
    quality = engine.quality_metrics(project_state)
    project_coverage = quality["structureCoverage"]
    exported_at = datetime.now().isoformat(timespec="seconds")
    taxonomy_hash = taxonomy_fingerprint(engine)
    document_metadata = build_document_metadata(project_state, taxonomy_hash, exported_at)
    gameplay_state = engine.gameplay_systems_state(project_state)
    gameplay_selected = engine.gameplay_selected_systems(project_state)
    gameplay_global_view = engine.gameplay_selected_systems(project_state, sort_by_weight=True)
    gameplay_weight_summary = engine.gameplay_weight_summary(project_state)
    gameplay_validation = engine.gameplay_validation_messages(project_state)
    domains = []
    for domain_doc in engine.domains:
        domain = domain_doc["domain"]
        coverage = engine.domain_coverage(domain["id"], project_state)
        nodes = []
        for node in engine.domain_nodes(domain["id"]):
            node_state = project_state["nodes"].get(node["id"], {})
            decision_metadata = build_decision_metadata(node, node_state, document_metadata)
            checklist = []
            for item in node.get("checklist", []):
                option_relations = build_option_relations_payload(item, node_state)
                checklist.append({
                    "id": item["id"],
                    "label": item["label"],
                    "description": item.get("description", ""),
                    "outputKey": item.get("outputKey", ""),
                    "templateRef": item.get("templateRef", ""),
                    "path": f"{node.get('domain', '')}.{node['id']}.{item['id']}",
                    "done": bool(node_state.get("checklist", {}).get(item["id"])),
                    "optionGroups": build_option_groups_payload(
                        item,
                        node_state,
                        option_relations,
                        document_metadata,
                        decision_metadata,
                        exported_at,
                    ),
                    "optionRelations": option_relations,
                    "activeOptionConflicts": [relation for relation in option_relations if relation.get("active")],
                })
            nodes.append({
                "id": node["id"],
                "name": node["name"],
                "description": node.get("description", ""),
                "requires": node.get("requires", []),
                "unlocks": node.get("unlocks", []),
                "designEntities": engine.node_design_entities(node, project_state),
                "entityValidationErrors": engine.node_entity_validation_errors(node, project_state),
                "decisionState": node_state.get("decisionState", "not_started"),
                "designNote": node_state.get("designNote", ""),
                "riskNote": node_state.get("riskNote", ""),
                "notApplicableReason": node_state.get("notApplicableReason", ""),
                "decisionMetadata": decision_metadata,
                "selection_state": decision_metadata["selection_state"],
                "confidence": decision_metadata["confidence"],
                "derives_to_stage": decision_metadata["derives_to_stage"],
                "depends_on_decisions": decision_metadata["depends_on_decisions"],
                "selection_rationale": decision_metadata["selection_rationale"],
                "checklist": checklist,
            })
        domains.append({"domain": domain, "coverage": coverage, "nodes": nodes})
    coverage_metrics = build_coverage_metrics(project_coverage, domains)
    return {
        "schemaVersion": EXPORT_SCHEMA_VERSION,
        "exportedAt": exported_at,
        "projectName": project_state.get("projectName", ""),
        "documentMetadata": document_metadata,
        "taxonomy": build_taxonomy_payload(engine, taxonomy_hash),
        "profile": project_state.get("profile", {}),
        "profileDisplay": display_profile(project_state.get("profile", {})),
        "projectCoverage": project_coverage,
        "coverage": project_coverage,
        "coverageMetrics": coverage_metrics,
        "qualityBadge": quality["qualityBadge"],
        "structureCoverage": quality["structureCoverage"],
        "concretenessCoverage": quality["concretenessCoverage"],
        "consistencyScore": quality["consistencyScore"],
        "qualityViolations": quality["qualityViolations"],
        "qualityCriticalCount": quality["qualityCriticalCount"],
        "crossLayerViolations": engine.cross_layer_violations(project_state),
        "gameplaySystems": {
            "schemaVersion": gameplay_state.get("schemaVersion", "1.0"),
            "presetOptions": engine.gameplay_system_options,
            "selected": gameplay_selected,
            "custom": gameplay_state.get("custom", []),
            "weights": gameplay_state.get("weights", {}),
            "coreLoops": gameplay_state.get("coreLoops", {}),
            "interview": gameplay_state.get("interview", {}),
            "weightSummary": gameplay_weight_summary,
            "validationMessages": gameplay_validation,
        },
        "gameplaySystemGlobalView": gameplay_global_view,
        "domains": domains,
    }


def selected_option_text(group):
    labels = []
    primary_label = group.get("primaryLabel", "")
    for label in group.get("selectedLabels", []):
        if label == primary_label:
            labels.append(f"{label}（主）")
        else:
            labels.append(label)
    return "、".join(labels)


def group_title(group):
    required = "必选" if group.get("required") else "可选"
    step = group.get("progressionStep", 0)
    layer = group.get("mdaLayerLabel", "")
    prefix = f"步骤 {step} / {layer} / " if step and layer else ""
    return f"{prefix}{group['label']}（{required}）"


def selected_groups(item):
    return [
        group
        for group in item.get("optionGroups", [])
        if group.get("selected")
    ]


def empty_groups(item):
    return [
        group
        for group in item.get("optionGroups", [])
        if not group.get("selected")
    ]


def conflict_lines(item):
    lines = []
    for conflict in item.get("activeOptionConflicts", []):
        source = conflict.get("source", {})
        for target in conflict.get("activeTargets", []):
            lines.append(f"{source.get('label', '')} ↔ {target.get('label', '')}。{conflict.get('reason', '')}")
    return lines


def entity_lookup_label(entity):
    schema_id = entity.get("schema") or entity.get("schemaVersion") or ""
    entity_id = entity.get("id", "")
    label = entity.get("label") or entity_id or "未命名实体"
    parts = [label]
    if entity_id:
        parts.append(f"`{entity_id}`")
    if schema_id:
        parts.append(f"`{schema_id}`")
    return " / ".join(parts)


def entity_summary_fields(entity):
    fields = []
    for key in ("device", "assetClass", "updateTick", "winCondition", "formula"):
        value = entity.get(key)
        if value not in (None, "", [], {}):
            fields.append(f"{key}={value}")
    for key in ("mapping", "nodes", "exitConditions", "phases", "inputs", "outputs", "owners"):
        value = entity.get(key)
        if isinstance(value, list):
            fields.append(f"{key}[{len(value)}]")
    for key in ("input", "frames", "effect", "boundaryRule", "countBand", "gatingLogic"):
        value = entity.get(key)
        if isinstance(value, dict):
            fields.append(f"{key}{{{len(value)}}}")
    return fields


def grouped_entities(entities):
    grouped = defaultdict(list)
    for entity in entities:
        grouped[entity.get("kind", "unknown")].append(entity)
    return grouped


def entity_error_text(error):
    severity = error.get("severity", "WARNING")
    path = error.get("path", "")
    message = error.get("message", "")
    schema_id = error.get("schemaId", "")
    schema_text = f" [{schema_id}]" if schema_id else ""
    return f"{severity}{schema_text} {path}: {message}".strip()


def violation_option_label(option):
    return (
        f"{option.get('domainName', '')} / {option.get('nodeName', '')} / "
        f"{option.get('itemLabel', '')} / {option.get('groupLabel', '')} / "
        f"{option.get('optionLabel', option.get('optionId', ''))}"
    )


def append_markdown_cross_layer_violations(lines, payload):
    violations = payload.get("crossLayerViolations", [])
    lines.extend(["", "## 跨层一致性", ""])
    if not violations:
        lines.append("暂无跨层一致性问题。")
        return
    for violation in violations:
        lines.append(
            f"- **{violation.get('severity', 'WARNING')}** `{violation.get('ruleId', '')}`："
            f"{violation.get('reason', '')}"
        )
        for option in violation.get("hitOptions", [])[:8]:
            lines.append(f"  - 命中：{violation_option_label(option)} (`{option.get('optionId', '')}`)")
        if len(violation.get("hitOptions", [])) > 8:
            lines.append(f"  - 还有 {len(violation.get('hitOptions', [])) - 8} 个命中选项未显示。")


def append_text_cross_layer_violations(lines, payload):
    violations = payload.get("crossLayerViolations", [])
    lines.extend(["", "跨层一致性:"])
    if not violations:
        lines.append("  暂无跨层一致性问题。")
        return
    for violation in violations:
        lines.append(f"  [{violation.get('severity', 'WARNING')}] {violation.get('ruleId', '')}: {violation.get('reason', '')}")
        for option in violation.get("hitOptions", [])[:8]:
            lines.append(f"    命中: {violation_option_label(option)} ({option.get('optionId', '')})")
        if len(violation.get("hitOptions", [])) > 8:
            lines.append(f"    还有 {len(violation.get('hitOptions', [])) - 8} 个命中选项未显示。")


def append_markdown_quality_violations(lines, payload):
    violations = payload.get("qualityViolations", [])
    lines.extend(["", "## 质量问题", ""])
    if not violations:
        lines.append("暂无质量问题。")
        return
    for violation in violations[:120]:
        label = violation.get("id") or violation.get("ruleId") or violation.get("type", "")
        lines.append(f"- **{violation.get('severity', 'WARNING')}** `{label}`：{violation.get('message', '')}")
        if violation.get("nodeName"):
            lines.append(f"  - 节点：{violation.get('nodeName')} (`{violation.get('nodeId', '')}`)")
        if violation.get("hitOptionIds"):
            lines.append(f"  - 命中选项：{', '.join(f'`{item}`' for item in violation.get('hitOptionIds', []))}")
    if len(violations) > 120:
        lines.append(f"- 还有 {len(violations) - 120} 条质量问题未显示。")


def append_text_quality_violations(lines, payload):
    violations = payload.get("qualityViolations", [])
    lines.extend(["", "质量问题:"])
    if not violations:
        lines.append("  暂无质量问题。")
        return
    for violation in violations[:120]:
        label = violation.get("id") or violation.get("ruleId") or violation.get("type", "")
        lines.append(f"  [{violation.get('severity', 'WARNING')}] {label}: {violation.get('message', '')}")
        if violation.get("nodeName"):
            lines.append(f"    节点: {violation.get('nodeName')} ({violation.get('nodeId', '')})")
    if len(violations) > 120:
        lines.append(f"  还有 {len(violations) - 120} 条质量问题未显示。")


def markdown_quality_lines(payload):
    concreteness = payload.get("concretenessCoverage", {})
    consistency = payload.get("consistencyScore", {})
    lines = [
        f"> qualityBadge: {payload.get('qualityBadge', 'L4_only_filled')}",
        "",
        f"- 结构覆盖：节点 {payload['projectCoverage']['nodePercent']}%，三级子项 {payload['projectCoverage']['checklistPercent']}%",
        (
            f"- 具体度覆盖：{concreteness.get('percent', 0)}%"
            f"（{concreteness.get('doneNodes', 0)}/{concreteness.get('totalNodes', 0)} concrete 节点）"
        ),
        (
            f"- 一致性分数：{consistency.get('score', 100)}"
            f"（CRITICAL {consistency.get('criticalViolationCount', 0)}/{consistency.get('applicableRuleCount', 0)} applicable rules）"
        ),
    ]
    if payload.get("qualityCriticalCount", 0):
        lines.extend(["", f"> **CRITICAL quality violations: {payload.get('qualityCriticalCount', 0)}**"])
    return lines


def text_quality_lines(payload):
    concreteness = payload.get("concretenessCoverage", {})
    consistency = payload.get("consistencyScore", {})
    lines = [
        f"qualityBadge: {payload.get('qualityBadge', 'L4_only_filled')}",
        f"结构覆盖: 节点 {payload['projectCoverage']['nodePercent']}%, 三级子项 {payload['projectCoverage']['checklistPercent']}%",
        f"具体度覆盖: {concreteness.get('percent', 0)}% ({concreteness.get('doneNodes', 0)}/{concreteness.get('totalNodes', 0)} concrete 节点)",
        f"一致性分数: {consistency.get('score', 100)} (CRITICAL {consistency.get('criticalViolationCount', 0)}/{consistency.get('applicableRuleCount', 0)} applicable rules)",
    ]
    if payload.get("qualityCriticalCount", 0):
        lines.append(f"CRITICAL quality violations: {payload.get('qualityCriticalCount', 0)}")
    return lines


def percent_text(value):
    return f"{round(float(value or 0) * 100)}%"


def markdown_coverage_metric_lines(payload):
    metrics = payload.get("coverageMetrics", {})
    if not metrics:
        return []
    return [
        "",
        "**五维覆盖率**",
        "",
        f"- 结构覆盖：{percent_text(metrics.get('structural_coverage'))}",
        f"- Checklist 勾选覆盖：{percent_text(metrics.get('checklist_tick_coverage'))}",
        f"- 状态分辨率：{percent_text(metrics.get('selection_state_resolution'))}",
        f"- 理由密度：{percent_text(metrics.get('rationale_density'))}",
        f"- 下游就绪度：{percent_text(metrics.get('downstream_readiness'))}",
        f"- 选项处理分辨率：{percent_text(metrics.get('option_treatment_resolution'))}",
    ]


def text_coverage_metric_lines(payload):
    metrics = payload.get("coverageMetrics", {})
    if not metrics:
        return []
    return [
        "五维覆盖率:",
        f"  结构覆盖: {percent_text(metrics.get('structural_coverage'))}",
        f"  Checklist 勾选覆盖: {percent_text(metrics.get('checklist_tick_coverage'))}",
        f"  状态分辨率: {percent_text(metrics.get('selection_state_resolution'))}",
        f"  理由密度: {percent_text(metrics.get('rationale_density'))}",
        f"  下游就绪度: {percent_text(metrics.get('downstream_readiness'))}",
        f"  选项处理分辨率: {percent_text(metrics.get('option_treatment_resolution'))}",
    ]


def markdown_document_metadata_lines(payload):
    metadata = payload.get("documentMetadata", {})
    if not metadata:
        return []
    lines = [
        "## 文档元数据",
        "",
        f"- document_type：`{metadata.get('document_type', '')}`",
        f"- document_version：`{metadata.get('document_version', '')}`",
        f"- taxonomy_version：`{metadata.get('taxonomy_version', '')}`",
        f"- taxonomy_hash：`{metadata.get('taxonomy_hash', '')}`",
        f"- case_name：{metadata.get('case_name', '')}",
        f"- authoring_source：`{metadata.get('authoring_source', '')}`",
        f"- authoring_confidence_overall：`{metadata.get('authoring_confidence_overall', '')}`",
        f"- exported_at：`{metadata.get('exported_at', '')}`",
    ]
    if metadata.get("case_genre"):
        lines.append(f"- case_genre：{', '.join(f'`{item}`' for item in metadata.get('case_genre', []))}")
    if metadata.get("case_applicability"):
        lines.extend(["", "**适用范围**", ""])
        lines.extend(f"- {item}" for item in metadata.get("case_applicability", []))
    if metadata.get("not_applicable_to"):
        lines.extend(["", "**不适用范围**", ""])
        lines.extend(f"- {item}" for item in metadata.get("not_applicable_to", []))
    return lines


def text_document_metadata_lines(payload):
    metadata = payload.get("documentMetadata", {})
    if not metadata:
        return []
    lines = [
        "文档元数据:",
        f"  document_type: {metadata.get('document_type', '')}",
        f"  document_version: {metadata.get('document_version', '')}",
        f"  taxonomy_version: {metadata.get('taxonomy_version', '')}",
        f"  taxonomy_hash: {metadata.get('taxonomy_hash', '')}",
        f"  case_name: {metadata.get('case_name', '')}",
        f"  authoring_source: {metadata.get('authoring_source', '')}",
        f"  authoring_confidence_overall: {metadata.get('authoring_confidence_overall', '')}",
        f"  exported_at: {metadata.get('exported_at', '')}",
    ]
    if metadata.get("case_genre"):
        lines.append(f"  case_genre: {', '.join(metadata.get('case_genre', []))}")
    if metadata.get("case_applicability"):
        lines.append("  适用范围:")
        lines.extend(f"    - {item}" for item in metadata.get("case_applicability", []))
    if metadata.get("not_applicable_to"):
        lines.append("  不适用范围:")
        lines.extend(f"    - {item}" for item in metadata.get("not_applicable_to", []))
    return lines


def append_markdown_design_entities(lines, node):
    entities = node.get("designEntities", [])
    errors = node.get("entityValidationErrors", [])
    if not entities and not errors:
        return
    lines.extend(["", "**已挂载实体**", ""])
    if entities:
        for kind, items in sorted(grouped_entities(entities).items()):
            lines.append(f"- `{kind}`")
            for entity in items:
                summary = entity_summary_fields(entity)
                suffix = f" — {'; '.join(summary)}" if summary else ""
                lines.append(f"  - {entity_lookup_label(entity)}{suffix}")
    else:
        lines.append("- 暂无可导出的实体。")
    if errors:
        lines.extend(["", "**实体校验警告**", ""])
        for error in errors[:20]:
            lines.append(f"- {entity_error_text(error)}")
        if len(errors) > 20:
            lines.append(f"- 还有 {len(errors) - 20} 条实体校验警告未显示。")


def append_text_design_entities(lines, node, indent="  "):
    entities = node.get("designEntities", [])
    errors = node.get("entityValidationErrors", [])
    if not entities and not errors:
        return
    lines.append(f"{indent}已挂载实体:")
    if entities:
        for kind, items in sorted(grouped_entities(entities).items()):
            lines.append(f"{indent}- {kind}")
            for entity in items:
                summary = entity_summary_fields(entity)
                suffix = f" - {'; '.join(summary)}" if summary else ""
                lines.append(f"{indent}  - {entity_lookup_label(entity)}{suffix}")
    else:
        lines.append(f"{indent}- 暂无可导出的实体。")
    if errors:
        lines.append(f"{indent}实体校验警告:")
        for error in errors[:20]:
            lines.append(f"{indent}- {entity_error_text(error)}")
        if len(errors) > 20:
            lines.append(f"{indent}- 还有 {len(errors) - 20} 条实体校验警告未显示。")


def missing_required_group_titles(item):
    if not item.get("done"):
        return []
    return [
        group_title(group)
        for group in item.get("optionGroups", [])
        if group.get("required") and not group.get("selected")
    ]


def append_limited_group_names(lines, groups, prefix, indent="", limit=8):
    if not groups:
        return
    names = [group_title(group) for group in groups[:limit]]
    if len(groups) > limit:
        names.append(f"还有 {len(groups) - limit} 组")
    lines.append(f"{indent}{prefix}{'；'.join(names)}")


def item_has_decision(item):
    return bool(item.get("done") or selected_groups(item) or conflict_lines(item))


def node_has_decision(node):
    if node.get("decisionState") in ("selected", "completed", "risk", "not_applicable"):
        return True
    if node.get("designNote") or node.get("riskNote") or node.get("notApplicableReason"):
        return True
    if node.get("designEntities") or node.get("entityValidationErrors"):
        return True
    return any(item_has_decision(item) for item in node.get("checklist", []))


def decision_items(node):
    if node.get("decisionState") == "not_applicable":
        return []
    return [item for item in node.get("checklist", []) if item_has_decision(item)]


def pending_counts(domain_payload):
    pending_nodes = 0
    pending_items = 0
    for node in domain_payload.get("nodes", []):
        if node.get("decisionState") == "not_applicable":
            continue
        if not node_has_decision(node):
            pending_nodes += 1
        pending_items += sum(1 for item in node.get("checklist", []) if not item.get("done"))
    return pending_nodes, pending_items


def decision_nodes(domain_payload):
    return [node for node in domain_payload.get("nodes", []) if node_has_decision(node)]


def append_markdown_decision_item(lines, item):
    mark = "x" if item["done"] else " "
    lines.append(f"- [{mark}] **{item['label']}** (`{item['outputKey']}`)")
    if item.get("templateRef"):
        lines.append(f"  - 本节点采用共享元模板 `{item['templateRef']}`,具体内容需在 L5 补充。")
    if item.get("description"):
        lines.append(f"  - 说明：{item['description']}")
    for group in selected_groups(item):
        lines.append(f"  - 已选：{group_title(group)} -> {selected_option_text(group)}")
        if group.get("designQuestion"):
            lines.append(f"    - 设计问题：{group['designQuestion']}")
    missing_groups = missing_required_group_titles(item)
    if missing_groups:
        lines.append(f"  - L4 待补：{'；'.join(missing_groups)}")
    for conflict in conflict_lines(item):
        lines.append(f"  - 软冲突：{conflict}")


def append_text_decision_item(lines, item):
    mark = "完成" if item["done"] else "已选择 L4"
    lines.append(f"    [{mark}] {item['label']} ({item['outputKey']})")
    if item.get("templateRef"):
        lines.append(f"      本节点采用共享元模板 {item['templateRef']},具体内容需在 L5 补充。")
    if item.get("description"):
        lines.append(f"      说明: {item['description']}")
    for group in selected_groups(item):
        lines.append(f"      已选: {group_title(group)} -> {selected_option_text(group)}")
        if group.get("designQuestion"):
            lines.append(f"        设计问题: {group['designQuestion']}")
    missing_groups = missing_required_group_titles(item)
    if missing_groups:
        lines.append(f"      L4 待补: {'; '.join(missing_groups)}")
    for conflict in conflict_lines(item):
        lines.append(f"      软冲突: {conflict}")


def gameplay_weight_text(system):
    weight = system.get("weight", "")
    if weight in ("", None):
        return "未填写"
    try:
        value = float(weight)
    except (TypeError, ValueError):
        return "未填写"
    if value.is_integer():
        value = int(value)
    return f"{value}%"


def gameplay_source_text(system):
    return "custom" if system.get("source") == "custom" or system.get("category") == "custom" else "preset"


def append_markdown_gameplay_systems(lines, payload):
    selected = payload.get("gameplaySystems", {}).get("selected", [])
    if not selected:
        return
    summary = payload.get("gameplaySystems", {}).get("weightSummary", {})
    lines.extend(["", "## 玩法系统设计", ""])
    lines.append(f"- 系统数量：{len(selected)}")
    lines.append(f"- 总占比：{summary.get('total', 0)}%")
    validation = payload.get("gameplaySystems", {}).get("validationMessages", [])
    if validation:
        lines.extend(["", "**校验提示**", ""])
        lines.extend(f"- {item}" for item in validation)
    lines.extend(["", "| 系统 | 来源 | 占比 | 映射描述 | 核心循环描述 |", "| --- | --- | ---: | --- | --- |"])
    for system in selected:
        lines.append(
            f"| {system.get('name', system.get('id', ''))} "
            f"| `{gameplay_source_text(system)}` "
            f"| {gameplay_weight_text(system)} "
            f"| {system.get('mapping_desc', '')} "
            f"| {system.get('core_loop') or '未填写'} |"
        )


def append_text_gameplay_systems(lines, payload):
    selected = payload.get("gameplaySystems", {}).get("selected", [])
    if not selected:
        return
    summary = payload.get("gameplaySystems", {}).get("weightSummary", {})
    lines.extend(["", "玩法系统设计:"])
    lines.append(f"  系统数量: {len(selected)}")
    lines.append(f"  总占比: {summary.get('total', 0)}%")
    validation = payload.get("gameplaySystems", {}).get("validationMessages", [])
    if validation:
        lines.append("  校验提示:")
        lines.extend(f"    - {item}" for item in validation)
    for system in selected:
        lines.append(f"  - {system.get('name', system.get('id', ''))}")
        lines.append(f"    source: {gameplay_source_text(system)}")
        lines.append(f"    weight: {gameplay_weight_text(system)}")
        lines.append(f"    mapping_desc: {system.get('mapping_desc', '')}")
        lines.append(f"    core_loop: {system.get('core_loop') or '未填写'}")


def append_markdown_gameplay_global_view(lines, payload):
    systems = payload.get("gameplaySystemGlobalView", [])
    if not systems:
        return
    lines.extend(["", "## 玩法系统全局视图附页", ""])
    lines.extend(["| 排序 | 系统 | 占比 | 核心循环 |", "| ---: | --- | ---: | --- |"])
    for index, system in enumerate(systems, start=1):
        lines.append(
            f"| {index} | {system.get('name', system.get('id', ''))} "
            f"| {gameplay_weight_text(system)} "
            f"| {system.get('core_loop') or '未填写'} |"
        )


def append_text_gameplay_global_view(lines, payload):
    systems = payload.get("gameplaySystemGlobalView", [])
    if not systems:
        return
    lines.extend(["", "玩法系统全局视图附页:"])
    for index, system in enumerate(systems, start=1):
        lines.append(
            f"  {index}. {system.get('name', system.get('id', ''))}: "
            f"{gameplay_weight_text(system)}; 核心循环: {system.get('core_loop') or '未填写'}"
        )


def append_markdown_decision_metadata(lines, node):
    metadata = node.get("decisionMetadata", {})
    if not metadata:
        return
    lines.extend([
        f"- selection_state：`{metadata.get('selection_state', '')}`",
        f"- confidence：`{metadata.get('confidence', '')}`",
        f"- derives_to_stage：{', '.join(str(item) for item in metadata.get('derives_to_stage', [])) or '`[]`'}",
        (
            "- depends_on_decisions："
            + (", ".join(f"`{item}`" for item in metadata.get("depends_on_decisions", [])) or "`[]`")
        ),
    ])
    rationale = metadata.get("selection_rationale", {})
    if rationale:
        lines.extend(["", "**选择说明**", ""])
        lines.append(f"- 为什么这么选(意图)：{rationale.get('intent', '')}")
        lines.append(f"- 反推依据 / 真实依据(来源)：{rationale.get('evidence', '')}")
        lines.append(f"- 不可改的部分(锁住的下游)：{rationale.get('locked_downstream', '')}")
        lines.append(f"- 风险与备选方向(留给 stage 7 评估)：{rationale.get('risks_and_alternatives', '')}")


def append_text_decision_metadata(lines, node):
    metadata = node.get("decisionMetadata", {})
    if not metadata:
        return
    lines.append(f"  selection_state: {metadata.get('selection_state', '')}")
    lines.append(f"  confidence: {metadata.get('confidence', '')}")
    lines.append(f"  derives_to_stage: {', '.join(str(item) for item in metadata.get('derives_to_stage', []))}")
    lines.append(f"  depends_on_decisions: {', '.join(metadata.get('depends_on_decisions', []))}")
    rationale = metadata.get("selection_rationale", {})
    if rationale:
        lines.append("  选择说明:")
        lines.append(f"    为什么这么选(意图): {rationale.get('intent', '')}")
        lines.append(f"    反推依据 / 真实依据(来源): {rationale.get('evidence', '')}")
        lines.append(f"    不可改的部分(锁住的下游): {rationale.get('locked_downstream', '')}")
        lines.append(f"    风险与备选方向(留给 stage 7 评估): {rationale.get('risks_and_alternatives', '')}")


def option_status_suffix(option):
    parts = [
        f"强度={option.get('strength', '')}",
        f"处理={option.get('treatment', '')}",
    ]
    if option.get("primary"):
        parts.append("主目标")
    provenance = option.get("selectionProvenance")
    if provenance:
        parts.append(f"来源={provenance.get('source', '')}")
        parts.append(f"置信度={provenance.get('confidence', '')}")
    return "，".join(part for part in parts if part)


def payload_totals(payload):
    nodes = 0
    checklist = 0
    groups = 0
    options = 0
    conflicts = 0
    for domain_payload in payload.get("domains", []):
        nodes += len(domain_payload.get("nodes", []))
        for node in domain_payload.get("nodes", []):
            checklist += len(node.get("checklist", []))
            for item in node.get("checklist", []):
                groups += len(item.get("optionGroups", []))
                options += sum(len(group.get("options", [])) for group in item.get("optionGroups", []))
                conflicts += len(item.get("activeOptionConflicts", []))
    return {
        "domains": len(payload.get("domains", [])),
        "nodes": nodes,
        "checklist": checklist,
        "groups": groups,
        "options": options,
        "activeConflicts": conflicts,
    }


def decision_totals(payload):
    nodes = 0
    checklist = 0
    groups = 0
    not_applicable = 0
    active_conflicts = 0
    pending_nodes = 0
    pending_items = 0
    for domain_payload in payload.get("domains", []):
        pending_node_count, pending_item_count = pending_counts(domain_payload)
        pending_nodes += pending_node_count
        pending_items += pending_item_count
        for node in decision_nodes(domain_payload):
            nodes += 1
            if node.get("decisionState") == "not_applicable":
                not_applicable += 1
            for item in decision_items(node):
                checklist += 1
                selected = selected_groups(item)
                groups += len(selected)
                active_conflicts += len(item.get("activeOptionConflicts", []))
    return {
        "nodes": nodes,
        "checklist": checklist,
        "groups": groups,
        "notApplicable": not_applicable,
        "activeConflicts": active_conflicts,
        "pendingNodes": pending_nodes,
        "pendingItems": pending_items,
    }


def export_preview_lines(engine, project_state, export_format, export_scope="decision", include_gameplay_global_view=False):
    payload = build_payload(engine, project_state)
    fmt = (export_format or "markdown").lower()
    scope = "archive" if fmt == "json" else (export_scope or "decision").lower()
    gameplay_count = len(payload.get("gameplaySystems", {}).get("selected", []))
    appendix_text = "，附带玩法系统全局视图" if include_gameplay_global_view and fmt != "json" and gameplay_count else ""
    if fmt == "json":
        totals = payload_totals(payload)
        return [
            "内容范围：JSON 完整机器结构",
            f"包含：{totals['domains']} 个领域，{totals['nodes']} 个节点，{totals['checklist']} 个三级项",
            f"L4：{totals['groups']} 个选项组，{totals['options']} 个固定选项",
            f"玩法系统：{gameplay_count} 个已选系统",
            f"当前激活软冲突：{totals['activeConflicts']} 条",
            "用途：兼容、备份、后续程序读取",
        ]
    if scope == "archive":
        totals = payload_totals(payload)
        return [
            "内容范围：完整导出",
            f"包含：{totals['domains']} 个领域，{totals['nodes']} 个节点，{totals['checklist']} 个三级项",
            f"L4：{totals['groups']} 个选项组，{totals['options']} 个固定选项",
            f"玩法系统：{gameplay_count} 个已选系统{appendix_text}",
            f"当前激活软冲突：{totals['activeConflicts']} 条",
            "用途：完整归档、审计、框架核对",
        ]
    totals = decision_totals(payload)
    l4_progress = engine.project_l4_progress(project_state)
    return [
        "内容范围：决策导出",
        f"包含：{totals['nodes']} 个已决策节点，{totals['checklist']} 个已决策三级项，{totals['groups']} 个已选择 L4 组",
        f"不适用节点：{totals['notApplicable']} 个",
        f"待补概览：待确认节点 {totals['pendingNodes']} 个，待完成三级项 {totals['pendingItems']} 个",
        f"L4 完整度：{l4_progress['done']}/{l4_progress['total']}，存在缺口的节点 {l4_progress['gapNodes']} 个",
        f"玩法系统：{gameplay_count} 个已选系统{appendix_text}",
        f"当前激活软冲突：{totals['activeConflicts']} 条",
        "用途：阅读、评审、继续补全",
    ]


def render_markdown(payload, include_gameplay_global_view=False):
    lines = [
        f"# {payload['projectName']}",
        "",
        "## 导出摘要",
        "",
        f"- 导出时间：`{payload['exportedAt']}`",
        *markdown_quality_lines(payload),
        "",
        "## 项目画像",
        "",
    ]
    for key, value in payload.get("profile", {}).items():
        lines.append(f"- {field_label(key)}：{option_label(key, value)} (`{value}`)")
    append_markdown_gameplay_systems(lines, payload)
    lines.extend(["", "## 领域总览", "", "| 领域 | 节点覆盖 | 三级子项覆盖 | 已决策节点 |", "| --- | ---: | ---: | ---: |"])
    for domain_payload in payload["domains"]:
        domain = domain_payload["domain"]
        coverage = domain_payload["coverage"]
        nodes = decision_nodes(domain_payload)
        lines.append(f"| {domain['name']} | {coverage['nodePercent']}% | {coverage['checklistPercent']}% | {len(nodes)} |")
    lines.extend(["", "## 待补概览", ""])
    pending_lines = []
    for domain_payload in payload["domains"]:
        pending_nodes, pending_items = pending_counts(domain_payload)
        if pending_nodes or pending_items:
            pending_lines.append(f"- {domain_payload['domain']['name']}：待确认节点 {pending_nodes} 个，待完成三级项 {pending_items} 个")
    lines.extend(pending_lines or ["暂无待补项。"])
    lines.extend(["", "## 已决策内容", ""])

    has_decisions = False
    for domain_payload in payload["domains"]:
        nodes = decision_nodes(domain_payload)
        if not nodes:
            continue
        has_decisions = True
        domain = domain_payload["domain"]
        coverage = domain_payload["coverage"]
        lines.extend([
            f"### {domain['name']}",
            "",
            f"- 覆盖：节点 {coverage['nodePercent']}%，三级子项 {coverage['checklistPercent']}%",
            "",
        ])
        for node in nodes:
            state_label = STATE_LABELS.get(node["decisionState"], node["decisionState"])
            lines.extend([
                f"#### {node['name']} · {state_label}",
                "",
                node["description"],
                "",
                f"- id：`{node['id']}`",
            ])
            if node["designNote"]:
                lines.extend(["", "**设计描述**", "", node["designNote"]])
            if node["riskNote"]:
                lines.extend(["", "**风险说明**", "", node["riskNote"]])
            if node["notApplicableReason"]:
                lines.extend(["", "**不适用原因**", "", node["notApplicableReason"]])
            items = decision_items(node)
            if items:
                lines.extend(["", "**已确认三级项**", ""])
                for item in items:
                    append_markdown_decision_item(lines, item)
            append_markdown_design_entities(lines, node)
            lines.append("")
    if not has_decisions:
        lines.append("暂无已决策内容。")
    if include_gameplay_global_view:
        append_markdown_gameplay_global_view(lines, payload)
    append_markdown_quality_violations(lines, payload)
    append_markdown_cross_layer_violations(lines, payload)
    return "\n".join(lines)


def render_text(payload, include_gameplay_global_view=False):
    lines = [
        payload["projectName"],
        "=" * max(8, len(payload["projectName"])),
        "",
        f"导出时间: {payload['exportedAt']}",
        *text_quality_lines(payload),
        "",
        "项目画像:",
    ]
    for key, value in payload.get("profile", {}).items():
        lines.append(f"  {field_label(key)}: {option_label(key, value)} ({value})")
    append_text_gameplay_systems(lines, payload)
    lines.extend(["", "领域总览:"])
    for domain_payload in payload["domains"]:
        domain = domain_payload["domain"]
        coverage = domain_payload["coverage"]
        nodes = decision_nodes(domain_payload)
        lines.append(f"  {domain['name']}: 节点 {coverage['nodePercent']}%, 三级子项 {coverage['checklistPercent']}%, 已决策节点 {len(nodes)}")
    lines.extend(["", "待补概览:"])
    pending_lines = []
    for domain_payload in payload["domains"]:
        pending_nodes, pending_items = pending_counts(domain_payload)
        if pending_nodes or pending_items:
            pending_lines.append(f"  {domain_payload['domain']['name']}: 待确认节点 {pending_nodes} 个, 待完成三级项 {pending_items} 个")
    lines.extend(pending_lines or ["  暂无待补项。"])
    lines.extend(["", "已决策内容:", ""])

    has_decisions = False
    for domain_payload in payload["domains"]:
        nodes = decision_nodes(domain_payload)
        if not nodes:
            continue
        has_decisions = True
        domain = domain_payload["domain"]
        coverage = domain_payload["coverage"]
        lines.extend([
            f"[{domain['name']}]",
            f"覆盖: 节点 {coverage['nodePercent']}%, 三级子项 {coverage['checklistPercent']}%",
            "",
        ])
        for node in nodes:
            lines.append(f"- {node['name']} ({STATE_LABELS.get(node['decisionState'], node['decisionState'])})")
            lines.append(f"  id: {node['id']}")
            lines.append(f"  说明: {node['description']}")
            if node["designNote"]:
                lines.append(f"  设计描述: {node['designNote']}")
            if node["riskNote"]:
                lines.append(f"  风险说明: {node['riskNote']}")
            if node["notApplicableReason"]:
                lines.append(f"  不适用原因: {node['notApplicableReason']}")
            for item in decision_items(node):
                append_text_decision_item(lines, item)
            append_text_design_entities(lines, node, indent="  ")
            lines.append("")
    if not has_decisions:
        lines.append("暂无已决策内容。")
    if include_gameplay_global_view:
        append_text_gameplay_global_view(lines, payload)
    append_text_quality_violations(lines, payload)
    append_text_cross_layer_violations(lines, payload)
    return "\n".join(lines)


def render_prompt(payload, include_gameplay_global_view=False):
    lines = [
        "请基于以下已决策内容继续补全设计，保持已有决策不被覆盖；未出现的框架项不代表取消，只代表当前导出未展开。",
        "",
        f"项目名称: {payload['projectName']}",
        f"导出时间: {payload['exportedAt']}",
        *text_quality_lines(payload),
        "",
        "项目画像:",
    ]
    for key, value in payload.get("profile", {}).items():
        lines.append(f"- {field_label(key)}: {option_label(key, value)} ({value})")
    append_text_gameplay_systems(lines, payload)
    if include_gameplay_global_view:
        append_text_gameplay_global_view(lines, payload)
    lines.extend(["", "待补概览:", ""])
    for domain_payload in payload["domains"]:
        pending_nodes, pending_items = pending_counts(domain_payload)
        if pending_nodes or pending_items:
            lines.append(f"- {domain_payload['domain']['name']}: 待确认节点 {pending_nodes} 个，待完成三级项 {pending_items} 个")
    lines.extend(["", "建议下一步优先澄清:", ""])
    missing_count = 0
    for domain_payload in payload["domains"]:
        domain = domain_payload["domain"]
        for node in domain_payload["nodes"]:
            if node_has_decision(node) or node.get("decisionState") == "not_applicable":
                continue
            for item in node["checklist"]:
                if not item["done"]:
                    missing_count += 1
                    lines.append(f"- {domain['name']} / {node['name']} / {item['label']}: {item.get('description', '')}")
                if missing_count >= 30:
                    break
            if missing_count >= 30:
                break
        if missing_count >= 30:
            lines.append("- 待补项较多，其余内容请在工具内继续筛选或使用完整导出。")
            break
    if missing_count == 0:
        lines.append("- 暂无明显待补项，请围绕已有风险、软冲突和设计描述继续细化。")
    lines.extend(["", "已决策摘要:", "", render_text(payload, include_gameplay_global_view=include_gameplay_global_view)])
    return "\n".join(lines)


def render_archive_markdown(payload, include_gameplay_global_view=False):
    lines = [
        f"# {payload['projectName']} - 完整归档",
        "",
        "## 导出摘要",
        "",
        f"- 导出时间：`{payload['exportedAt']}`",
        *markdown_quality_lines(payload),
        *markdown_coverage_metric_lines(payload),
        "",
        *markdown_document_metadata_lines(payload),
        "",
        "## 项目画像",
        "",
    ]
    for key, value in payload.get("profile", {}).items():
        lines.append(f"- {field_label(key)}：{option_label(key, value)} (`{value}`)")
    append_markdown_gameplay_systems(lines, payload)
    lines.append("")

    for domain_payload in payload["domains"]:
        domain = domain_payload["domain"]
        coverage = domain_payload["coverage"]
        lines.extend([
            f"## {domain['name']}",
            "",
            domain.get("description", ""),
            "",
            f"- domain：`{domain['id']}`",
            f"- 节点覆盖率：{coverage['nodePercent']}%",
            f"- 三级子项覆盖率：{coverage['checklistPercent']}%",
            "",
        ])
        for node in domain_payload["nodes"]:
            state_label = STATE_LABELS.get(node["decisionState"], node["decisionState"])
            lines.extend([
                f"### {node['name']} · {state_label}",
                "",
                node["description"],
                "",
                f"- id：`{node['id']}`",
            ])
            append_markdown_decision_metadata(lines, node)
            if node["designNote"]:
                lines.extend(["", "**设计描述**", "", node["designNote"]])
            if node["riskNote"]:
                lines.extend(["", "**风险说明**", "", node["riskNote"]])
            if node["notApplicableReason"]:
                lines.extend(["", "**不适用原因**", "", node["notApplicableReason"]])
            lines.extend(["", "**完整 Checklist**", ""])
            for item in node["checklist"]:
                mark = "x" if item["done"] else " "
                lines.append(f"- [{mark}] **{item['label']}** (`{item['outputKey']}`)")
                if item.get("templateRef"):
                    lines.append(f"  - 本节点采用共享元模板 `{item['templateRef']}`,具体内容需在 L5 补充。")
                if item.get("description"):
                    lines.append(f"  - 说明：{item['description']}")
                for group in item.get("optionGroups", []):
                    lines.append(f"  - {group_title(group)} (`{group['outputKey']}`)")
                    if group.get("designQuestion"):
                        lines.append(f"    - 设计问题：{group['designQuestion']}")
                    for option in group.get("options", []):
                        option_mark = "x" if option.get("selected") else " "
                        suffix = option_status_suffix(option)
                        suffix_text = f"，{suffix}" if suffix else ""
                        lines.append(f"    - [{option_mark}] {option['label']} (`{option['outputKey']}`{suffix_text})")
                for conflict in conflict_lines(item):
                    lines.append(f"  - 软冲突：{conflict}")
            append_markdown_design_entities(lines, node)
            lines.append("")
    if include_gameplay_global_view:
        append_markdown_gameplay_global_view(lines, payload)
    append_markdown_quality_violations(lines, payload)
    append_markdown_cross_layer_violations(lines, payload)
    return "\n".join(lines)


def render_archive_text(payload, include_gameplay_global_view=False):
    lines = [
        f"{payload['projectName']} - 完整归档",
        "=" * max(8, len(payload["projectName"]) + 7),
        "",
        f"导出时间: {payload['exportedAt']}",
        *text_quality_lines(payload),
        "",
        *text_coverage_metric_lines(payload),
        "",
        *text_document_metadata_lines(payload),
        "",
        "项目画像:",
    ]
    for key, value in payload.get("profile", {}).items():
        lines.append(f"  {field_label(key)}: {option_label(key, value)} ({value})")
    append_text_gameplay_systems(lines, payload)
    lines.append("")

    for domain_payload in payload["domains"]:
        domain = domain_payload["domain"]
        coverage = domain_payload["coverage"]
        lines.extend([
            f"[{domain['name']}]",
            f"domain: {domain['id']}",
            f"节点覆盖率: {coverage['nodePercent']}%",
            f"三级子项覆盖率: {coverage['checklistPercent']}%",
            "",
        ])
        for node in domain_payload["nodes"]:
            lines.append(f"- {node['name']} ({STATE_LABELS.get(node['decisionState'], node['decisionState'])})")
            lines.append(f"  id: {node['id']}")
            lines.append(f"  说明: {node['description']}")
            append_text_decision_metadata(lines, node)
            if node["designNote"]:
                lines.append(f"  设计描述: {node['designNote']}")
            if node["riskNote"]:
                lines.append(f"  风险说明: {node['riskNote']}")
            if node["notApplicableReason"]:
                lines.append(f"  不适用原因: {node['notApplicableReason']}")
            for item in node["checklist"]:
                mark = "完成" if item["done"] else "未完成"
                lines.append(f"    [{mark}] {item['label']} ({item['outputKey']})")
                if item.get("templateRef"):
                    lines.append(f"      本节点采用共享元模板 {item['templateRef']},具体内容需在 L5 补充。")
                if item.get("description"):
                    lines.append(f"      说明: {item['description']}")
                for group in item.get("optionGroups", []):
                    lines.append(f"      {group_title(group)} ({group['outputKey']}):")
                    if group.get("designQuestion"):
                        lines.append(f"        设计问题: {group['designQuestion']}")
                    for option in group.get("options", []):
                        option_mark = "完成" if option.get("selected") else "未选"
                        suffix = option_status_suffix(option)
                        suffix_text = f", {suffix}" if suffix else ""
                        lines.append(f"        [{option_mark}] {option['label']} ({option['outputKey']}{suffix_text})")
                for conflict in conflict_lines(item):
                    lines.append(f"      软冲突: {conflict}")
            append_text_design_entities(lines, node, indent="  ")
            lines.append("")
    if include_gameplay_global_view:
        append_text_gameplay_global_view(lines, payload)
    append_text_quality_violations(lines, payload)
    append_text_cross_layer_violations(lines, payload)
    return "\n".join(lines)


def profile_payload(payload):
    metadata = payload.get("documentMetadata", {})
    return {
        "schemaVersion": EXPORT_SCHEMA_VERSION,
        "projectName": payload.get("projectName", ""),
        "exportedAt": payload.get("exportedAt", ""),
        "document_type": metadata.get("document_type", ""),
        "taxonomy_version": metadata.get("taxonomy_version", ""),
        "taxonomy_hash": metadata.get("taxonomy_hash", ""),
        "profile": payload.get("profile", {}),
        "profileDisplay": payload.get("profileDisplay", {}),
        "case_genre": metadata.get("case_genre", []),
        "case_applicability": metadata.get("case_applicability", []),
        "not_applicable_to": metadata.get("not_applicable_to", []),
    }


def coverage_payload(payload):
    metadata = payload.get("documentMetadata", {})
    return {
        "schemaVersion": EXPORT_SCHEMA_VERSION,
        "projectName": payload.get("projectName", ""),
        "exportedAt": payload.get("exportedAt", ""),
        "document_type": metadata.get("document_type", ""),
        "taxonomy_version": metadata.get("taxonomy_version", ""),
        "taxonomy_hash": metadata.get("taxonomy_hash", ""),
        "coverageMetrics": payload.get("coverageMetrics", {}),
        "projectCoverage": payload.get("projectCoverage", {}),
        "structureCoverage": payload.get("structureCoverage", {}),
        "concretenessCoverage": payload.get("concretenessCoverage", {}),
        "consistencyScore": payload.get("consistencyScore", {}),
        "qualityBadge": payload.get("qualityBadge", ""),
        "qualityCriticalCount": payload.get("qualityCriticalCount", 0),
    }


def write_archive_sidecars(payload, target_dir):
    target = Path(target_dir)
    base = safe_file_name(payload.get("projectName", "commercial-game-design"))
    sidecars = {
        f"{base}.full.json": payload,
        f"{base}.profile.json": profile_payload(payload),
        f"{base}.coverage.json": coverage_payload(payload),
    }
    written = []
    for file_name, data in sidecars.items():
        path = target / file_name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def write_export(engine, project_state, target_dir, export_format, export_scope="decision", include_gameplay_global_view=False):
    payload = build_payload(engine, project_state)
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    fmt = export_format.lower()
    scope = (export_scope or "decision").lower()
    suffix_map = {
        "markdown": "md",
        "json": "json",
        "txt": "txt",
        "text": "text",
        "prompt": "prompt.txt",
    }
    suffix = suffix_map.get(fmt, "txt")
    scope_suffix = "full" if scope == "archive" and fmt != "json" else "decision"
    if fmt == "json":
        path = target / f"{safe_file_name(payload['projectName'])}.{suffix}"
    else:
        path = target / f"{safe_file_name(payload['projectName'])}.{scope_suffix}.{suffix}"
    if fmt == "json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "markdown":
        text = (
            render_archive_markdown(payload, include_gameplay_global_view=include_gameplay_global_view)
            if scope == "archive"
            else render_markdown(payload, include_gameplay_global_view=include_gameplay_global_view)
        )
        path.write_text(text, encoding="utf-8")
        if scope == "archive":
            write_archive_sidecars(payload, target)
    elif fmt == "prompt":
        text = (
            render_archive_text(payload, include_gameplay_global_view=include_gameplay_global_view)
            if scope == "archive"
            else render_prompt(payload, include_gameplay_global_view=include_gameplay_global_view)
        )
        path.write_text(text, encoding="utf-8")
    else:
        text = (
            render_archive_text(payload, include_gameplay_global_view=include_gameplay_global_view)
            if scope == "archive"
            else render_text(payload, include_gameplay_global_view=include_gameplay_global_view)
        )
        path.write_text(text, encoding="utf-8")
    return path
