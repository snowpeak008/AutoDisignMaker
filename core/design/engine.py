from copy import deepcopy

from core.design.ai_interview import empty_ai_interview_state, normalize_ai_interview_state
from core.design.cross_layer_lint import CrossLayerRuleSet, rule_matches_profile
from core.design.entity_schema import EntitySchemaRegistry
from core.design.gameplay_systems import (
    all_options as gameplay_all_options,
    empty_state as empty_gameplay_systems_state,
    normalize_state as normalize_gameplay_systems_state,
    selected_systems as selected_gameplay_systems,
    validation_messages as gameplay_system_validation_messages,
    weight_summary as gameplay_system_weight_summary,
)
from core.design.profile_schema import PROFILE_DEFAULTS


NODE_STATES = ("not_started", "selected", "completed", "risk", "not_applicable")

STATE_LABELS = {
    "not_started": "未选择",
    "selected": "已确认",
    "completed": "已完成",
    "risk": "有风险",
    "not_applicable": "不适用",
}


class DesignEngine:
    def __init__(self, data):
        self.data = data
        self.domains = data.get("domains", [])
        self.gameplay_system_options = data.get("gameplaySystemOptions", [])
        self.entity_schema_registry = EntitySchemaRegistry()
        self.cross_layer_rules = CrossLayerRuleSet()
        self.domain_by_id = {item["domain"]["id"]: item for item in self.domains}
        self.nodes = []
        for domain_doc in self.domains:
            self.nodes.extend(domain_doc.get("nodes", []))
        self.node_by_id = {node["id"]: node for node in self.nodes}
        self.node_search_index = {
            node["id"]: self.build_node_search_index(node)
            for node in self.nodes
        }

    def build_node_search_index(self, node):
        parts = [node.get("id", ""), node.get("name", ""), node.get("description", "")]
        for item in node.get("checklist", []):
            parts.extend([
                item.get("id", ""),
                item.get("label", ""),
                item.get("description", ""),
                item.get("outputKey", ""),
            ])
            for group in item.get("optionGroups", []):
                parts.extend([
                    group.get("id", ""),
                    group.get("label", ""),
                    group.get("description", ""),
                    group.get("outputKey", ""),
                    group.get("mdaLayer", ""),
                    group.get("mdaLayerLabel", ""),
                    group.get("relation", ""),
                    group.get("designQuestion", ""),
                ])
                for option in group.get("options", []):
                    parts.extend([
                        option.get("id", ""),
                        option.get("label", ""),
                        option.get("description", ""),
                        option.get("outputKey", ""),
                    ])
            for relation in item.get("optionRelations", []):
                source = relation.get("source", {})
                parts.extend([
                    relation.get("id", ""),
                    relation.get("type", ""),
                    relation.get("reason", ""),
                    source.get("groupId", ""),
                    source.get("optionId", ""),
                ])
                for target in relation.get("targets", []):
                    parts.extend([target.get("groupId", ""), target.get("optionId", "")])
        return " ".join(str(part) for part in parts).lower()

    def first_domain_id(self):
        return self.domains[0]["domain"]["id"] if self.domains else ""

    def domain_nodes(self, domain_id):
        return [node for node in self.nodes if node.get("domain") == domain_id]

    def empty_state(self):
        nodes = {}
        for node in self.nodes:
            nodes[node["id"]] = {
                "decisionState": "not_started",
                "designNote": "",
                "riskNote": "",
                "notApplicableReason": "",
                "designEntities": [],
                "entityValidationErrors": [],
                "checklist": {item["id"]: False for item in node.get("checklist", [])},
                "checklistOptions": self.empty_checklist_options(node),
            }
        return {
            "projectName": "未命名游戏设计项目",
            "profile": deepcopy(PROFILE_DEFAULTS),
            "nodes": nodes,
            "gameplaySystems": empty_gameplay_systems_state(),
            "aiInterview": empty_ai_interview_state(),
        }

    def empty_checklist_options(self, node):
        checklist_options = {}
        for item in node.get("checklist", []):
            item_options = {}
            for group in item.get("optionGroups", []):
                item_options[group["id"]] = {"selected": [], "primary": ""}
            if item_options:
                checklist_options[item["id"]] = item_options
        return checklist_options

    def normalize_state(self, state):
        normalized = deepcopy(state or {})
        normalized.setdefault("projectName", "未命名游戏设计项目")
        profile = deepcopy(PROFILE_DEFAULTS)
        profile.update(normalized.get("profile", {}))
        normalized["profile"] = profile
        normalized.setdefault("nodes", {})
        normalized["gameplaySystems"] = normalize_gameplay_systems_state(
            normalized.get("gameplaySystems"),
            self.gameplay_system_options,
        )
        normalized["aiInterview"] = normalize_ai_interview_state(normalized.get("aiInterview"))
        for node in self.nodes:
            node_state = normalized["nodes"].setdefault(node["id"], {})
            node_state.setdefault("decisionState", "not_started")
            if node_state["decisionState"] not in NODE_STATES:
                node_state["decisionState"] = "not_started"
            node_state.setdefault("designNote", "")
            node_state.setdefault("riskNote", "")
            node_state.setdefault("notApplicableReason", "")
            if "designEntities" not in node_state and "design_entities" in node_state:
                node_state["designEntities"] = node_state.get("design_entities")
            node_state.pop("design_entities", None)
            node_state.pop("entity_validation_errors", None)
            design_entities, entity_errors = self.normalize_node_design_entities(
                node_state.get("designEntities", []),
                node["id"],
            )
            node_state["designEntities"] = design_entities
            node_state["entityValidationErrors"] = entity_errors
            node_state.setdefault("checklist", {})
            node_state.setdefault("checklistOptions", {})
            checklist_state = node_state["checklist"]
            for item in node.get("checklist", []):
                item_id = item["id"]
                if item_id not in checklist_state:
                    for legacy_id in item.get("legacyIds", []):
                        if legacy_id in checklist_state:
                            checklist_state[item_id] = bool(checklist_state[legacy_id])
                            break
                checklist_state.setdefault(item_id, False)
                for legacy_id in item.get("legacyIds", []):
                    if legacy_id != item_id:
                        checklist_state.pop(legacy_id, None)
                item_options = node_state["checklistOptions"].setdefault(item_id, {})
                allowed_group_ids = {group["id"] for group in item.get("optionGroups", [])}
                for stale_group_id in list(item_options):
                    if stale_group_id not in allowed_group_ids:
                        item_options.pop(stale_group_id, None)
                for group in item.get("optionGroups", []):
                    group_state = item_options.setdefault(group["id"], {})
                    selected = group_state.get("selected", [])
                    if not isinstance(selected, list):
                        selected = [selected] if selected else []
                    allowed = {option["id"] for option in group.get("options", [])}
                    selected = [option_id for option_id in selected if option_id in allowed]
                    if group.get("selectionMode") == "single":
                        selected = selected[:1]
                    primary = group_state.get("primary", "")
                    if primary not in selected:
                        primary = ""
                    group_state["selected"] = selected
                    group_state["primary"] = primary
        return normalized

    def gameplay_systems_state(self, project_state):
        state = normalize_gameplay_systems_state(
            (project_state or {}).get("gameplaySystems"),
            self.gameplay_system_options,
        )
        if isinstance(project_state, dict):
            project_state["gameplaySystems"] = state
        return state

    def gameplay_all_options(self, project_state):
        return gameplay_all_options(self.gameplay_system_options, self.gameplay_systems_state(project_state))

    def gameplay_selected_systems(self, project_state, sort_by_weight=False):
        return selected_gameplay_systems(
            self.gameplay_system_options,
            self.gameplay_systems_state(project_state),
            sort_by_weight=sort_by_weight,
        )

    def gameplay_weight_summary(self, project_state):
        return gameplay_system_weight_summary(self.gameplay_systems_state(project_state))

    def gameplay_validation_messages(self, project_state):
        return gameplay_system_validation_messages(
            self.gameplay_system_options,
            self.gameplay_systems_state(project_state),
        )

    def normalize_node_design_entities(self, raw_entities, node_id):
        errors = []
        if raw_entities in (None, ""):
            raw_entities = []
        if not isinstance(raw_entities, list):
            return [], [self.entity_validation_error(node_id, "designEntities", "designEntities must be an array")]

        entities = []
        for index, entity in enumerate(raw_entities):
            entity_path = f"designEntities[{index}]"
            if not isinstance(entity, dict):
                errors.append(self.entity_validation_error(node_id, entity_path, "entity must be an object"))
                continue
            entities.append(entity)
            for error in self.entity_schema_registry.validate(entity):
                suffix = error.path[1:] if error.path.startswith("$") else f".{error.path}"
                errors.append(self.entity_validation_error(node_id, f"{entity_path}{suffix}", error.message, error.schema_id))
        return entities, errors

    def entity_validation_error(self, node_id, path, message, schema_id=""):
        return {
            "severity": "WARNING",
            "nodeId": node_id,
            "path": path,
            "message": message,
            "schemaId": schema_id,
        }

    def node_design_entities(self, node, project_state):
        node_state = project_state.get("nodes", {}).get(node["id"], {})
        return deepcopy(node.get("designEntities", [])) + deepcopy(node_state.get("designEntities", []))

    def node_entity_validation_errors(self, node, project_state):
        node_state = project_state.get("nodes", {}).get(node["id"], {})
        return deepcopy(node.get("entityValidationErrors", [])) + deepcopy(node_state.get("entityValidationErrors", []))

    def cross_layer_violations(self, project_state):
        return self.cross_layer_rules.lint(self, project_state)

    def set_node_state(self, project_state, node_id, decision_state):
        node_state = project_state["nodes"].setdefault(node_id, {})
        if decision_state in NODE_STATES:
            node_state["decisionState"] = decision_state

    def effective_node_state(self, node, project_state):
        node_state = project_state["nodes"].get(node["id"], {})
        if node_state.get("decisionState") == "not_applicable":
            return "not_applicable"

        checklist = node.get("checklist", [])
        done = sum(1 for item in checklist if node_state.get("checklist", {}).get(item["id"]))
        if checklist and done == len(checklist):
            return "completed"
        if done > 0 or node_state.get("designNote", "").strip():
            return "selected"
        return "not_started"

    def refresh_node_state(self, project_state, node_id):
        node = self.node_by_id.get(node_id)
        if not node:
            return
        node_state = project_state["nodes"].setdefault(node_id, {})
        if node_state.get("decisionState") == "not_applicable":
            return
        node_state["decisionState"] = self.effective_node_state(node, project_state)

    def set_checklist_item(self, project_state, node_id, item_id, checked):
        node_state = project_state["nodes"].setdefault(node_id, {})
        if checked and node_state.get("decisionState") == "not_applicable":
            node_state["decisionState"] = "not_started"
            node_state["notApplicableReason"] = ""
        checklist = node_state.setdefault("checklist", {})
        checklist[item_id] = bool(checked)
        if not checked:
            item_options = node_state.setdefault("checklistOptions", {}).get(item_id, {})
            for group_state in item_options.values():
                group_state["selected"] = []
                group_state["primary"] = ""
        self.refresh_node_state(project_state, node_id)

    def item_by_id(self, node_id, item_id):
        node = self.node_by_id.get(node_id)
        if not node:
            return None
        for item in node.get("checklist", []):
            if item.get("id") == item_id:
                return item
        return None

    def group_by_id(self, node_id, item_id, group_id):
        item = self.item_by_id(node_id, item_id)
        if not item:
            return None
        for group in item.get("optionGroups", []):
            if group.get("id") == group_id:
                return group
        return None

    def option_by_id(self, group, option_id):
        for option in group.get("options", []):
            if option.get("id") == option_id:
                return option
        return None

    def option_ref_label(self, item, group_id, option_id):
        for group in item.get("optionGroups", []):
            if group.get("id") != group_id:
                continue
            option = self.option_by_id(group, option_id)
            if option:
                return f"{group.get('label', group_id)} / {option.get('label', option_id)}"
        return f"{group_id} / {option_id}"

    def selected_option_refs(self, project_state, node_id, item_id):
        node_state = project_state["nodes"].get(node_id, {})
        item_options = node_state.get("checklistOptions", {}).get(item_id, {})
        refs = set()
        for group_id, group_state in item_options.items():
            for option_id in group_state.get("selected", []):
                refs.add((group_id, option_id))
        return refs

    def option_group_state(self, project_state, node_id, item_id, group_id):
        node_state = project_state["nodes"].setdefault(node_id, {})
        checklist_options = node_state.setdefault("checklistOptions", {})
        item_options = checklist_options.setdefault(item_id, {})
        return item_options.setdefault(group_id, {"selected": [], "primary": ""})

    def set_option_group_option(self, project_state, node_id, item_id, group_id, option_id, checked):
        group = self.group_by_id(node_id, item_id, group_id)
        if not group:
            return
        allowed = {option["id"] for option in group.get("options", [])}
        if option_id not in allowed:
            return
        state = self.option_group_state(project_state, node_id, item_id, group_id)
        selected = list(state.get("selected", []))
        if checked:
            if group.get("selectionMode") == "single":
                selected = [option_id]
            elif option_id not in selected:
                selected.append(option_id)
        else:
            selected = [item for item in selected if item != option_id]
        state["selected"] = selected
        if state.get("primary") not in selected:
            state["primary"] = selected[0] if len(selected) == 1 and group.get("allowPrimary") else ""
        node_state = project_state["nodes"].setdefault(node_id, {})
        if selected:
            node_state.setdefault("checklist", {})[item_id] = True
        self.refresh_node_state(project_state, node_id)

    def set_option_group_primary(self, project_state, node_id, item_id, group_id, option_id):
        group = self.group_by_id(node_id, item_id, group_id)
        if not group or not group.get("allowPrimary"):
            return
        state = self.option_group_state(project_state, node_id, item_id, group_id)
        selected = state.get("selected", [])
        state["primary"] = option_id if option_id in selected else ""

    def active_option_conflicts(self, project_state, node_id, item_id, group_id=None):
        item = self.item_by_id(node_id, item_id)
        if not item:
            return []
        selected_refs = self.selected_option_refs(project_state, node_id, item_id)
        conflicts = []
        for relation in item.get("optionRelations", []):
            if relation.get("type") != "soft_conflict":
                continue
            source = relation.get("source", {})
            source_ref = (source.get("groupId"), source.get("optionId"))
            if source_ref not in selected_refs:
                continue
            for target in relation.get("targets", []):
                target_ref = (target.get("groupId"), target.get("optionId"))
                if target_ref not in selected_refs:
                    continue
                if group_id and group_id not in (source_ref[0], target_ref[0]):
                    continue
                conflicts.append({
                    "id": relation.get("id", ""),
                    "type": relation.get("type", ""),
                    "severity": relation.get("severity", "warning"),
                    "reason": relation.get("reason", ""),
                    "source": {"groupId": source_ref[0], "optionId": source_ref[1], "label": self.option_ref_label(item, *source_ref)},
                    "target": {"groupId": target_ref[0], "optionId": target_ref[1], "label": self.option_ref_label(item, *target_ref)},
                })
        return conflicts

    def active_domain_option_conflicts(self, project_state, domain_id=None):
        conflicts = []
        for node in self.nodes:
            if domain_id and node.get("domain") != domain_id:
                continue
            for item in node.get("checklist", []):
                for conflict in self.active_option_conflicts(project_state, node["id"], item["id"]):
                    conflicts.append({
                        "nodeId": node["id"],
                        "nodeName": node.get("name", node["id"]),
                        "itemId": item["id"],
                        "itemLabel": item.get("label", item["id"]),
                        **conflict,
                    })
        return conflicts

    def state_score(self, decision_state):
        if decision_state == "completed":
            return 1.0
        if decision_state in ("selected", "risk"):
            return 0.5
        return 0.0

    def node_progress(self, node, project_state):
        node_state = project_state["nodes"].get(node["id"], {})
        checklist = node.get("checklist", [])
        if node_state.get("decisionState") == "not_applicable":
            return {"done": 0, "total": 0, "percent": 0}
        total = len(checklist)
        done = sum(1 for item in checklist if node_state.get("checklist", {}).get(item["id"]))
        percent = round((done / total) * 100) if total else 0
        return {"done": done, "total": total, "percent": percent}

    def item_l4_progress(self, node, item, project_state):
        node_state = project_state["nodes"].get(node["id"], {})
        if node_state.get("decisionState") == "not_applicable":
            return {"done": 0, "total": 0, "percent": 0, "complete": True, "missingGroups": []}
        if not node_state.get("checklist", {}).get(item["id"]):
            return {"done": 0, "total": 0, "percent": 0, "complete": True, "missingGroups": []}

        required_groups = [group for group in item.get("optionGroups", []) if group.get("required")]
        item_options = node_state.get("checklistOptions", {}).get(item["id"], {})
        done = 0
        missing = []
        for group in required_groups:
            selected = item_options.get(group["id"], {}).get("selected", [])
            if selected:
                done += 1
            else:
                missing.append(group.get("label", group["id"]))
        total = len(required_groups)
        percent = round((done / total) * 100) if total else 100
        return {
            "done": done,
            "total": total,
            "percent": percent,
            "complete": done == total,
            "missingGroups": missing,
        }

    def node_l4_progress(self, node, project_state):
        node_state = project_state["nodes"].get(node["id"], {})
        if node_state.get("decisionState") == "not_applicable":
            return {"done": 0, "total": 0, "percent": 0, "complete": True, "missingItems": []}
        done = 0
        total = 0
        missing_items = []
        for item in node.get("checklist", []):
            progress = self.item_l4_progress(node, item, project_state)
            done += progress["done"]
            total += progress["total"]
            if progress["total"] and not progress["complete"]:
                missing_items.append({
                    "itemId": item["id"],
                    "itemLabel": item.get("label", item["id"]),
                    "missingGroups": progress["missingGroups"],
                })
        percent = round((done / total) * 100) if total else 0
        return {
            "done": done,
            "total": total,
            "percent": percent,
            "complete": not missing_items,
            "missingItems": missing_items,
        }

    def node_has_l4_gap(self, node, project_state):
        return bool(self.node_l4_progress(node, project_state)["missingItems"])

    def domain_l4_progress(self, domain_id, project_state):
        done = 0
        total = 0
        gap_nodes = 0
        for node in self.domain_nodes(domain_id):
            progress = self.node_l4_progress(node, project_state)
            done += progress["done"]
            total += progress["total"]
            if progress["missingItems"]:
                gap_nodes += 1
        percent = round((done / total) * 100) if total else 0
        return {"done": done, "total": total, "percent": percent, "gapNodes": gap_nodes}

    def project_l4_progress(self, project_state):
        done = 0
        total = 0
        gap_nodes = 0
        for domain_doc in self.domains:
            progress = self.domain_l4_progress(domain_doc["domain"]["id"], project_state)
            done += progress["done"]
            total += progress["total"]
            gap_nodes += progress["gapNodes"]
        percent = round((done / total) * 100) if total else 0
        return {"done": done, "total": total, "percent": percent, "gapNodes": gap_nodes}

    def domain_coverage(self, domain_id, project_state):
        domain_doc = self.domain_by_id.get(domain_id)
        if not domain_doc:
            return {"nodePercent": 0, "checklistPercent": 0, "doneNodes": 0, "totalNodes": 0, "doneChecklist": 0, "totalChecklist": 0}

        required_ids = domain_doc.get("coverageStandard", {}).get("requiredItems", [])
        applicable_nodes = []
        done_node_score = 0.0
        done_checklist = 0
        total_checklist = 0
        for node_id in required_ids:
            node = self.node_by_id.get(node_id)
            if not node:
                continue
            node_state = project_state["nodes"].get(node_id, {})
            effective_state = self.effective_node_state(node, project_state)
            if effective_state == "not_applicable":
                continue
            applicable_nodes.append(node)
            done_node_score += self.state_score(effective_state)
            progress = self.node_progress(node, project_state)
            done_checklist += progress["done"]
            total_checklist += progress["total"]

        total_nodes = len(applicable_nodes)
        node_percent = round((done_node_score / total_nodes) * 100) if total_nodes else 0
        checklist_percent = round((done_checklist / total_checklist) * 100) if total_checklist else 0
        return {
            "nodePercent": node_percent,
            "checklistPercent": checklist_percent,
            "doneNodes": done_node_score,
            "totalNodes": total_nodes,
            "doneChecklist": done_checklist,
            "totalChecklist": total_checklist,
        }

    def project_coverage(self, project_state):
        node_score = 0.0
        total_nodes = 0
        done_checklist = 0
        total_checklist = 0
        for domain_doc in self.domains:
            coverage = self.domain_coverage(domain_doc["domain"]["id"], project_state)
            node_score += coverage["doneNodes"]
            total_nodes += coverage["totalNodes"]
            done_checklist += coverage["doneChecklist"]
            total_checklist += coverage["totalChecklist"]
        return {
            "nodePercent": round((node_score / total_nodes) * 100) if total_nodes else 0,
            "checklistPercent": round((done_checklist / total_checklist) * 100) if total_checklist else 0,
            "doneNodes": node_score,
            "totalNodes": total_nodes,
            "doneChecklist": done_checklist,
            "totalChecklist": total_checklist,
        }

    def node_has_valid_design_entity(self, node, project_state):
        for entity in self.node_design_entities(node, project_state):
            if not self.entity_schema_registry.validate(entity):
                return True
        return False

    def concreteness_coverage(self, project_state):
        concrete_roles = {"system_concrete", "content_concrete"}
        total = 0
        done = 0
        gap_nodes = []
        for node in self.nodes:
            if node.get("roleClass") not in concrete_roles:
                continue
            if self.effective_node_state(node, project_state) == "not_applicable":
                continue
            total += 1
            if self.node_has_valid_design_entity(node, project_state):
                done += 1
            else:
                gap_nodes.append(node["id"])
        return {
            "percent": round((done / total) * 100) if total else 100,
            "doneNodes": done,
            "totalNodes": total,
            "gapNodes": len(gap_nodes),
            "gapNodeIds": gap_nodes,
        }

    def consistency_score(self, project_state):
        profile = project_state.get("profile", {})
        applicable = [
            rule for rule in self.cross_layer_rules.rules
            if rule_matches_profile(rule, profile)
        ]
        violations = self.cross_layer_violations(project_state)
        critical_count = sum(1 for item in violations if item.get("severity") == "CRITICAL")
        applicable_count = len(applicable)
        score = 100 if applicable_count == 0 else round(max(0, (1 - critical_count / applicable_count) * 100))
        return {
            "score": score,
            "applicableRuleCount": applicable_count,
            "criticalViolationCount": critical_count,
            "violationCount": len(violations),
        }

    def compute_quality_badge(self, project_state):
        concreteness = self.concreteness_coverage(project_state)
        consistency = self.consistency_score(project_state)
        if concreteness["doneNodes"] == 0:
            return "L4_only_filled"
        if concreteness["percent"] == 100 and consistency["criticalViolationCount"] == 0:
            return "L5_complete_consistent"
        return "L5_partial"

    def quality_violations(self, project_state):
        violations = []
        for node in self.nodes:
            if node.get("roleClass") not in {"system_concrete", "content_concrete"}:
                continue
            if self.effective_node_state(node, project_state) == "not_applicable":
                continue
            if self.node_has_valid_design_entity(node, project_state):
                continue
            violations.append({
                "id": f"missing_l5_entity_{node['id']}",
                "type": "missing_l5_entity",
                "severity": "CRITICAL",
                "nodeId": node["id"],
                "nodeName": node.get("name", node["id"]),
                "roleClass": node.get("roleClass", ""),
                "message": "concrete 节点缺少 schema-valid L5 designEntities。",
            })

        for violation in self.cross_layer_violations(project_state):
            if violation.get("severity") != "CRITICAL":
                continue
            violations.append({
                "id": f"cross_layer_{violation.get('ruleId', '')}",
                "type": "cross_layer",
                "severity": "CRITICAL",
                "ruleId": violation.get("ruleId", ""),
                "message": violation.get("reason", ""),
                "hitOptionIds": violation.get("hitOptionIds", []),
            })

        template_reuse = self.data.get("_meta", {}).get("templateReuse", {})
        for item in template_reuse.get("sharedOptionGroups", []):
            group_id = item.get("groupId", "")
            if item.get("undeclaredRefs", 0) < 5:
                continue
            violations.append({
                "id": f"undeclared_template_reuse_{group_id}",
                "type": "undeclared_template_reuse",
                "severity": "CRITICAL",
                "groupId": group_id,
                "message": f"optionGroup {group_id} 被复用 {item.get('count', 0)} 次,但仍有 {item.get('undeclaredRefs', 0)} 处未声明 templateRef。",
            })
        return violations

    def quality_metrics(self, project_state):
        structure = self.project_coverage(project_state)
        violations = self.quality_violations(project_state)
        return {
            "qualityBadge": self.compute_quality_badge(project_state),
            "structureCoverage": structure,
            "concretenessCoverage": self.concreteness_coverage(project_state),
            "consistencyScore": self.consistency_score(project_state),
            "qualityViolations": violations,
            "qualityCriticalCount": sum(1 for item in violations if item.get("severity") == "CRITICAL"),
        }

    def missing_items(self, domain_id, project_state):
        missing = []
        for node in self.domain_nodes(domain_id):
            node_state = project_state["nodes"].get(node["id"], {})
            effective_state = self.effective_node_state(node, project_state)
            if effective_state == "not_applicable":
                continue
            if effective_state in ("not_started", ""):
                missing.append(f"{node['name']}：节点未确认")
            for item in node.get("checklist", []):
                if not node_state.get("checklist", {}).get(item["id"]):
                    missing.append(f"{node['name']} / {item['label']}")
                else:
                    l4_progress = self.item_l4_progress(node, item, project_state)
                    if l4_progress["missingGroups"]:
                        missing.append(f"{node['name']} / {item['label']}：L4 未完整（{', '.join(l4_progress['missingGroups'])}）")
        return missing

    def risk_items(self, project_state):
        risks = []
        for node in self.nodes:
            node_state = project_state["nodes"].get(node["id"], {})
            if node_state.get("riskNote", "").strip() and self.effective_node_state(node, project_state) != "not_applicable":
                risks.append({
                    "node": node,
                    "riskNote": node_state.get("riskNote", ""),
                })
        return risks

    def profile_focus_domains(self, project_state):
        profile = project_state.get("profile", {})
        focus = set()
        if profile.get("businessModel") in ("free_to_play", "subscription", "premium_with_dlc"):
            focus.update(["economy_monetization_design", "balance_design", "data_validation_design", "compliance_risk_design"])
        if profile.get("operationModel") == "live_service":
            focus.update(["retention_lifecycle_design", "liveops_version_design", "launch_readiness_design"])
        if profile.get("socialModel") in ("multiplayer", "community_driven"):
            focus.update(["social_community_design", "compliance_risk_design"])
        if profile.get("regionScope") in ("multi_region", "global"):
            focus.update(["release_growth_design", "compliance_risk_design"])
        if profile.get("targetScale") in ("3a", "large_service"):
            focus.update(["documentation_collaboration_design", "data_validation_design", "launch_readiness_design"])
        return focus
