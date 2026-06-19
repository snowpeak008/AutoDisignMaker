"""Profile-to-content consistency lint for ADR 0009 M4."""

import json
from pathlib import Path

from core.design.data_loader import data_dir


DEFAULT_RULES_FILE = "cross_layer_rules.json"


def rules_path():
    return data_dir() / DEFAULT_RULES_FILE


def load_cross_layer_rules(path=None):
    target = Path(path) if path else rules_path()
    if not target.exists():
        return {"schemaVersion": "1.0", "rules": []}
    return json.loads(target.read_text(encoding="utf-8"))


class CrossLayerRuleSet:
    def __init__(self, path=None):
        self.path = Path(path) if path else rules_path()
        self.payload = load_cross_layer_rules(self.path)
        self.rules = list(self.payload.get("rules", []))

    def lint(self, engine, project_state):
        profile = project_state.get("profile", {})
        selected = selected_option_contexts(engine, project_state)
        violations = []
        for rule in self.rules:
            if not rule_matches_profile(rule, profile):
                continue
            hit_options = []
            for option_id in rule.get("forbidsOptionId", []):
                hit_options.extend(selected.get(option_id, []))
            if not hit_options:
                continue
            violations.append({
                "ruleId": rule.get("id", ""),
                "severity": rule.get("severity", "WARNING"),
                "reason": rule.get("reason", ""),
                "condition": rule.get("if", {}),
                "hitOptionIds": sorted({item["optionId"] for item in hit_options}),
                "hitOptions": hit_options,
            })
        return violations


def rule_matches_profile(rule, profile):
    conditions = rule.get("if", {})
    for key, expected_values in conditions.items():
        if not key.startswith("profile."):
            return False
        field = key.split(".", 1)[1]
        actual = profile.get(field, "unknown")
        if not value_matches(actual, expected_values):
            return False
    return True


def value_matches(actual, expected_values):
    if not isinstance(expected_values, list):
        expected_values = [expected_values]
    return actual in {str(value) for value in expected_values}


def selected_option_contexts(engine, project_state):
    selected = {}
    nodes_state = project_state.get("nodes", {})
    for domain_doc in engine.domains:
        domain = domain_doc.get("domain", {})
        for node in domain_doc.get("nodes", []):
            node_state = nodes_state.get(node["id"], {})
            checklist_options = node_state.get("checklistOptions", {})
            for item in node.get("checklist", []):
                item_options = checklist_options.get(item["id"], {})
                for group in item.get("optionGroups", []):
                    group_state = item_options.get(group["id"], {})
                    selected_ids = set(group_state.get("selected", []))
                    if not selected_ids:
                        continue
                    for option in group.get("options", []):
                        option_id = option.get("id", "")
                        if option_id not in selected_ids:
                            continue
                        selected.setdefault(option_id, []).append({
                            "domainId": domain.get("id", ""),
                            "domainName": domain.get("name", ""),
                            "nodeId": node.get("id", ""),
                            "nodeName": node.get("name", ""),
                            "itemId": item.get("id", ""),
                            "itemLabel": item.get("label", ""),
                            "groupId": group.get("id", ""),
                            "groupLabel": group.get("label", ""),
                            "optionId": option_id,
                            "optionLabel": option.get("label", option_id),
                        })
    return selected
