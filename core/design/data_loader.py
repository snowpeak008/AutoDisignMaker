import json
import re
import sys
from copy import deepcopy
from pathlib import Path

from core.design.entity_schema import EntitySchemaRegistry
from core.design.node_role import count_role_classes, normalize_role_class


MDA_LAYER_LABELS = {
    "aesthetics": "体验目标",
    "dynamics": "玩家动态",
    "mechanics": "机制抓手",
    "constraints": "边界约束",
    "evidence": "验收信号",
}

OPTION_RELATION_TYPES = {"soft_conflict", "hard_exclusive"}
_ENTITY_SCHEMA_REGISTRY = None
_TEMPLATE_CACHE = None


def source_project_root():
    return Path(__file__).resolve().parents[1]


def runtime_project_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "sandbox" / "workspace"
    try:
        from core.paths import WORKSPACE_DIR

        return WORKSPACE_DIR
    except ImportError:
        pass
    return source_project_root() / "sandbox" / "workspace"


def bundled_data_dir():
    bundle_root = Path(getattr(sys, "_MEIPASS", runtime_project_root()))
    design_data = bundle_root / "knowledge" / "design_data"
    return design_data if design_data.exists() else bundle_root / "data"


def project_root():
    return runtime_project_root()


def data_dir():
    try:
        from core.paths import KNOWLEDGE_DIR
        design_data = KNOWLEDGE_DIR / "design_data"
        if design_data.exists():
            return design_data
    except ImportError:
        pass
    root = runtime_project_root()
    local_data = root / "knowledge" / "design_data"
    if local_data.exists():
        return local_data
    legacy_data = root / "data" / "design"
    if legacy_data.exists():
        return legacy_data
    return bundled_data_dir()


def domains_dir():
    return data_dir() / "domains"


def templates_dir():
    return data_dir() / "templates"


def gameplay_system_options_path():
    return data_dir() / "gameplay_system_options.json"


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def camel_case(value):
    parts = [part for part in re.split(r"[^0-9A-Za-z]+", str(value)) if part]
    if not parts:
        return ""
    head = parts[0].lower()
    tail = [part[:1].upper() + part[1:] for part in parts[1:]]
    return "".join([head, *tail])


def normalize_legacy_ids(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def normalize_group_options(group):
    options = []
    for option in group.get("options", []):
        if isinstance(option, dict):
            option_id = option.get("id") or option.get("label", "")
            label = option.get("label") or option_id
            description = option.get("description", "")
            output_key = option.get("outputKey") or camel_case(option_id)
        else:
            option_id = str(option)
            label = str(option)
            description = ""
            output_key = camel_case(option_id)
        options.append({
            "id": str(option_id),
            "label": str(label),
            "description": str(description),
            "outputKey": str(output_key),
        })
    group["options"] = options


def normalize_option_ref(value):
    if isinstance(value, dict):
        group_id = value.get("groupId") or value.get("group") or value.get("group_id")
        option_id = value.get("optionId") or value.get("option") or value.get("option_id")
    elif isinstance(value, str) and "." in value:
        group_id, option_id = value.split(".", 1)
    else:
        return None
    group_id = str(group_id or "").strip()
    option_id = str(option_id or "").strip()
    if not group_id or not option_id:
        return None
    return {"groupId": group_id, "optionId": option_id}


def load_templates():
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is not None:
        return _TEMPLATE_CACHE
    templates = {}
    root = templates_dir()
    if root.exists():
        for path in sorted(root.glob("*.json")):
            payload = load_json(path)
            template_id = str(payload.get("id") or path.stem)
            payload.setdefault("id", template_id)
            templates[template_id] = payload
    _TEMPLATE_CACHE = templates
    return templates


def resolve_template_ref(item):
    template_ref = item.get("templateRef") or item.get("template_ref")
    if not template_ref:
        return []
    template_ref = str(template_ref)
    item["templateRef"] = template_ref
    templates = load_templates()
    template = templates.get(template_ref)
    if not template:
        item.setdefault("optionGroups", [])
        item.setdefault("optionRelations", [])
        return [f"templateRef {template_ref!r} does not exist"]
    if not item.get("optionGroups"):
        item["optionGroups"] = deepcopy(template.get("optionGroups", []))
    if not item.get("optionRelations"):
        item["optionRelations"] = deepcopy(template.get("optionRelations", []))
    return []


def normalize_option_relations(item):
    relations = []
    for relation in item.get("optionRelations", []):
        if not isinstance(relation, dict):
            continue
        relation_type = str(relation.get("type", "soft_conflict"))
        source = normalize_option_ref(relation.get("source"))
        targets = [
            target
            for target in (normalize_option_ref(value) for value in relation.get("targets", []))
            if target
        ]
        if relation_type not in OPTION_RELATION_TYPES or not source or not targets:
            continue
        relation_id = relation.get("id") or f"{relation_type}_{source['groupId']}_{source['optionId']}"
        relations.append({
            "id": str(relation_id),
            "type": relation_type,
            "source": source,
            "targets": targets,
            "reason": str(relation.get("reason", "")),
            "severity": str(relation.get("severity", "warning")),
        })
    item["optionRelations"] = relations


def entity_schema_registry():
    global _ENTITY_SCHEMA_REGISTRY
    if _ENTITY_SCHEMA_REGISTRY is None:
        _ENTITY_SCHEMA_REGISTRY = EntitySchemaRegistry()
    return _ENTITY_SCHEMA_REGISTRY


def entity_validation_error(path, message, schema_id=""):
    return {
        "severity": "WARNING",
        "path": path,
        "message": message,
        "schemaId": schema_id,
    }


def normalize_design_entities(owner, owner_path, registry=None):
    registry = registry or entity_schema_registry()
    raw_entities = owner.get("designEntities", [])
    errors = []
    if raw_entities in (None, ""):
        raw_entities = []
    if not isinstance(raw_entities, list):
        owner["designEntities"] = []
        errors.append(entity_validation_error(f"{owner_path}.designEntities", "designEntities must be an array"))
        owner["entityValidationErrors"] = errors
        return errors

    entities = []
    for index, entity in enumerate(raw_entities):
        entity_path = f"{owner_path}.designEntities[{index}]"
        if not isinstance(entity, dict):
            errors.append(entity_validation_error(entity_path, "entity must be an object"))
            continue
        entities.append(entity)
        for error in registry.validate(entity):
            suffix = error.path[1:] if error.path.startswith("$") else f".{error.path}"
            errors.append(entity_validation_error(f"{entity_path}{suffix}", error.message, error.schema_id))
    owner["designEntities"] = entities
    owner["entityValidationErrors"] = errors
    return errors


def normalize_option_groups(item):
    groups = []
    for group in item.get("optionGroups", []):
        if not isinstance(group, dict):
            continue
        group_id = group.get("id") or group.get("label", "")
        label = group.get("label") or group_id
        mda_layer = str(group.get("mdaLayer", ""))
        try:
            progression_step = int(group.get("progressionStep", 0) or 0)
        except (TypeError, ValueError):
            progression_step = 0
        normalized = {
            "id": str(group_id),
            "label": str(label),
            "description": str(group.get("description", "")),
            "outputKey": str(group.get("outputKey") or camel_case(group_id)),
            "selectionMode": group.get("selectionMode", "multi"),
            "required": bool(group.get("required", False)),
            "allowPrimary": bool(group.get("allowPrimary", False)),
            "mdaLayer": mda_layer,
            "mdaLayerLabel": str(group.get("mdaLayerLabel") or MDA_LAYER_LABELS.get(mda_layer, "")),
            "progressionStep": progression_step,
            "relation": str(group.get("relation", "")),
            "designQuestion": str(group.get("designQuestion", "")),
            "options": group.get("options", []),
        }
        if normalized["selectionMode"] not in ("single", "multi"):
            normalized["selectionMode"] = "multi"
        normalize_group_options(normalized)
        groups.append(normalized)
    item["optionGroups"] = groups


def normalize_checklist(node):
    checklist = []
    template_warnings = []
    for index, item in enumerate(node.get("checklist", []), start=1):
        legacy_id = f"{node['id']}_item_{index}"
        if isinstance(item, dict):
            item_id = item.get("id") or legacy_id
            label = item.get("label") or item_id
            description = item.get("description", "")
            output_key = item.get("outputKey") or camel_case(item_id)
            legacy_ids = normalize_legacy_ids(item.get("legacyIds"))
            template_ref = item.get("templateRef") or item.get("template_ref") or ""
            if legacy_id != item_id and legacy_id not in legacy_ids:
                legacy_ids.append(legacy_id)
            template_warnings.extend(resolve_template_ref(item))
        else:
            item_id = legacy_id
            label = str(item)
            description = ""
            output_key = camel_case(item_id)
            legacy_ids = []
            template_ref = ""
        checklist.append({
            "id": str(item_id),
            "label": str(label),
            "description": str(description),
            "outputKey": str(output_key),
            "legacyIds": legacy_ids,
            "templateRef": str(template_ref),
            "optionGroups": item.get("optionGroups", []) if isinstance(item, dict) else [],
            "optionRelations": item.get("optionRelations", []) if isinstance(item, dict) else [],
        })
        normalize_option_groups(checklist[-1])
        normalize_option_relations(checklist[-1])
    node["checklist"] = checklist
    if template_warnings:
        node["_templateWarnings"] = template_warnings


def normalize_domain(domain_doc):
    domain = domain_doc.get("domain", {})
    domain_doc.setdefault("schemaVersion", "0.1.0")
    domain.setdefault("priority", "P0")
    domain.setdefault("activation", "always")
    domain_doc["domain"] = domain
    role_class_warnings = []
    entity_validation_warnings = []
    template_warnings = []
    registry = entity_schema_registry()
    for node in domain_doc.get("nodes", []):
        node.setdefault("requires", [])
        node.setdefault("unlocks", [])
        node.setdefault("recommendedBefore", [])
        node.setdefault("requiresAny", [])
        node.setdefault("conflictsWith", [])
        node.setdefault("domain", domain.get("id", ""))
        role_class, warning = normalize_role_class(node.get("roleClass"))
        node["roleClass"] = role_class
        if warning:
            role_class_warnings.append(f"{domain.get('id', '')}.{node.get('id', '')}: {warning}")
        entity_errors = normalize_design_entities(
            node,
            f"{domain.get('id', '')}.{node.get('id', '')}",
            registry=registry,
        )
        for error in entity_errors:
            entity_validation_warnings.append(f"{error['path']}: {error['message']}")
        normalize_checklist(node)
        for warning in node.get("_templateWarnings", []):
            template_warnings.append(f"{domain.get('id', '')}.{node.get('id', '')}: {warning}")
    if role_class_warnings:
        domain_doc["_roleClassWarnings"] = role_class_warnings
    if entity_validation_warnings:
        domain_doc["_entityValidationWarnings"] = entity_validation_warnings
    if template_warnings:
        domain_doc["_templateWarnings"] = template_warnings
    coverage = domain_doc.setdefault("coverageStandard", {})
    coverage.setdefault("domain", domain.get("id", ""))
    coverage.setdefault("unit", "nodes_and_checklist")
    coverage.setdefault("requiredItems", [node["id"] for node in domain_doc.get("nodes", [])])
    coverage.setdefault("expected", len(coverage.get("requiredItems", [])))
    coverage.setdefault("formula", "completed_or_partial_nodes / applicable_required_items")
    return domain_doc


def load_domain_order():
    path = data_dir() / "domain_order.json"
    if not path.exists():
        return []
    payload = load_json(path)
    return payload.get("domainOrder", [])


def load_domains(path=None):
    root = Path(path) if path else domains_dir()
    domains = []
    for file_path in sorted(root.glob("*.json")):
        domains.append(normalize_domain(load_json(file_path)))

    order = load_domain_order()
    if order:
        rank = {domain_id: index for index, domain_id in enumerate(order)}
        domains.sort(key=lambda item: rank.get(item.get("domain", {}).get("id", ""), 999))
    return domains


def load_gameplay_system_options():
    path = gameplay_system_options_path()
    if not path.exists():
        return []
    payload = load_json(path)
    options = payload.get("options", [])
    normalized = []
    seen = set()
    for option in options:
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("id") or "").strip()
        if not option_id or option_id in seen:
            continue
        seen.add(option_id)
        normalized.append({
            "id": option_id,
            "name": str(option.get("name") or option_id).strip(),
            "category": str(option.get("category") or "preset").strip() or "preset",
            "mapping_desc": str(option.get("mapping_desc") or option.get("mappingDesc") or "").strip(),
        })
    return normalized


def validate_gameplay_system_options(options):
    errors = []
    seen = set()
    for option in options:
        option_id = option.get("id", "")
        if not option_id:
            errors.append("玩法系统预设存在空 id。")
            continue
        if option_id in seen:
            errors.append(f"玩法系统预设 id 重复：{option_id}")
        seen.add(option_id)
        if not option.get("name", "").strip():
            errors.append(f"玩法系统预设 {option_id} 缺少 name。")
        if not option.get("category", "").strip():
            errors.append(f"玩法系统预设 {option_id} 缺少 category。")
        if not option.get("mapping_desc", "").strip():
            errors.append(f"玩法系统预设 {option_id} 缺少 mapping_desc。")
    return errors


def validate_domains(domains):
    errors = []
    domain_ids = set()
    node_ids = set()

    for domain_doc in domains:
        domain = domain_doc.get("domain", {})
        domain_id = domain.get("id")
        if not domain_id:
            errors.append("存在缺少 domain.id 的领域文件。")
            continue
        if domain_id in domain_ids:
            errors.append(f"重复 domain id：{domain_id}")
        domain_ids.add(domain_id)

        for node in domain_doc.get("nodes", []):
            node_id = node.get("id")
            if not node_id:
                errors.append(f"领域 {domain_id} 存在缺少 id 的节点。")
                continue
            if node_id in node_ids:
                errors.append(f"重复节点 id：{node_id}")
            node_ids.add(node_id)
            if node.get("domain") != domain_id:
                errors.append(f"节点 {node_id} 的 domain 与文件 domain 不一致。")

    relation_fields = ("requires", "unlocks", "recommendedBefore", "requiresAny", "conflictsWith")
    for domain_doc in domains:
        domain_id = domain_doc.get("domain", {}).get("id", "")
        coverage = domain_doc.get("coverageStandard", {})
        for required_id in coverage.get("requiredItems", []):
            if required_id not in node_ids:
                errors.append(f"领域 {domain_id} 的 coverage requiredItems 引用了不存在节点：{required_id}")
        for node in domain_doc.get("nodes", []):
            for field_name in relation_fields:
                for relation_id in node.get(field_name, []):
                    if relation_id not in node_ids:
                        errors.append(f"节点 {node['id']} 的 {field_name} 引用了不存在节点：{relation_id}")
            checklist_ids = set()
            output_keys = set()
            for item in node.get("checklist", []):
                item_id = item.get("id")
                output_key = item.get("outputKey")
                if item_id in checklist_ids:
                    errors.append(f"节点 {node['id']} 存在重复 checklist id：{item_id}")
                checklist_ids.add(item_id)
                if not item.get("label", "").strip():
                    errors.append(f"节点 {node['id']} 的 checklist {item_id} 缺少 label。")
                if not item.get("description", "").strip():
                    errors.append(f"节点 {node['id']} 的 checklist {item_id} 缺少 description。")
                if not output_key:
                    errors.append(f"节点 {node['id']} 的 checklist {item_id} 缺少 outputKey。")
                elif output_key in output_keys:
                    errors.append(f"节点 {node['id']} 存在重复 checklist outputKey：{output_key}")
                output_keys.add(output_key)
                group_ids = set()
                group_output_keys = set()
                option_refs = set()
                relation_ids = set()
                for group in item.get("optionGroups", []):
                    group_id = group.get("id")
                    group_output_key = group.get("outputKey")
                    if not group_id:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} 存在空 optionGroup id。")
                    elif group_id in group_ids:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} 存在重复 optionGroup id：{group_id}")
                    group_ids.add(group_id)
                    if not group.get("label", "").strip():
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 缺少 label。")
                    if not group.get("mdaLayer"):
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 缺少 mdaLayer。")
                    elif group.get("mdaLayer") not in MDA_LAYER_LABELS:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 的 mdaLayer 非法：{group.get('mdaLayer')}")
                    if not group.get("progressionStep"):
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 缺少 progressionStep。")
                    if not group.get("relation"):
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 缺少 relation。")
                    if not group.get("designQuestion"):
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 缺少 designQuestion。")
                    if not group_output_key:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 缺少 outputKey。")
                    elif group_output_key in group_output_keys:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} 存在重复 optionGroup outputKey：{group_output_key}")
                    group_output_keys.add(group_output_key)
                    option_ids = set()
                    option_output_keys = set()
                    for option in group.get("options", []):
                        option_id = option.get("id")
                        option_output_key = option.get("outputKey")
                        if not option_id:
                            errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 存在空 option id。")
                        elif option_id in option_ids:
                            errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 存在重复 option id：{option_id}")
                        option_ids.add(option_id)
                        if not option.get("label", "").strip():
                            errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} / option {option_id} 缺少 label。")
                        if not option_output_key:
                            errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} / option {option_id} 缺少 outputKey。")
                        elif option_output_key in option_output_keys:
                            errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionGroup {group_id} 存在重复 option outputKey：{option_output_key}")
                        option_output_keys.add(option_output_key)
                        option_refs.add((group_id, option_id))
                for relation in item.get("optionRelations", []):
                    relation_id = relation.get("id", "")
                    if not relation_id:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} 存在空 optionRelation id。")
                    elif relation_id in relation_ids:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} 存在重复 optionRelation id：{relation_id}")
                    relation_ids.add(relation_id)
                    if relation.get("type") not in OPTION_RELATION_TYPES:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionRelation {relation_id} 类型非法：{relation.get('type')}")
                    source = relation.get("source", {})
                    source_ref = (source.get("groupId"), source.get("optionId"))
                    if source_ref not in option_refs:
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionRelation {relation_id} source 引用了不存在选项：{source_ref}")
                    if not relation.get("reason", "").strip():
                        errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionRelation {relation_id} 缺少 reason。")
                    for target in relation.get("targets", []):
                        target_ref = (target.get("groupId"), target.get("optionId"))
                        if target_ref not in option_refs:
                            errors.append(f"节点 {node['id']} 的 checklist {item_id} / optionRelation {relation_id} target 引用了不存在选项：{target_ref}")
    return errors


def load_project_data():
    domains = load_domains()
    gameplay_options = load_gameplay_system_options()
    role_class_warnings = [
        warning
        for domain_doc in domains
        for warning in domain_doc.get("_roleClassWarnings", [])
    ]
    entity_validation_warnings = [
        warning
        for domain_doc in domains
        for warning in domain_doc.get("_entityValidationWarnings", [])
    ]
    template_warnings = [
        warning
        for domain_doc in domains
        for warning in domain_doc.get("_templateWarnings", [])
    ]
    return {
        "program": {
            "id": "commercial_game_design_decision_tool",
            "name": "完整商业游戏设计决策工具",
            "description": "全领域游戏设计决策、节点补全和框架补全工作台。"
        },
        "domains": domains,
        "gameplaySystemOptions": gameplay_options,
        "_meta": {
            "validationErrors": validate_domains(domains) + validate_gameplay_system_options(gameplay_options),
            "validationWarnings": role_class_warnings + entity_validation_warnings + template_warnings,
            "entityValidationWarnings": entity_validation_warnings,
            "templateWarnings": template_warnings,
            "templateReuse": scan_template_reuse(domains),
            "roleClassCounts": count_role_classes(domains),
            "runtimeRoot": str(runtime_project_root()),
            "dataSource": str(data_dir())
        }
    }


def scan_template_reuse(domains):
    group_refs = {}
    template_refs = {}
    for domain_doc in domains:
        domain_id = domain_doc.get("domain", {}).get("id", "")
        for node in domain_doc.get("nodes", []):
            for item in node.get("checklist", []):
                item_path = f"{domain_id}.{node.get('id', '')}.{item.get('id', '')}"
                template_ref = item.get("templateRef", "")
                if template_ref:
                    template_refs.setdefault(template_ref, []).append(item_path)
                for group in item.get("optionGroups", []):
                    group_refs.setdefault(group.get("id", ""), []).append({
                        "path": item_path,
                        "templateRef": template_ref,
                    })
    shared_groups = []
    for group_id, refs in sorted(group_refs.items()):
        if len(refs) < 2:
            continue
        declared = sum(1 for ref in refs if ref.get("templateRef"))
        shared_groups.append({
            "groupId": group_id,
            "count": len(refs),
            "declaredTemplateRefs": declared,
            "undeclaredRefs": len(refs) - declared,
        })
    return {
        "templateRefs": {key: len(value) for key, value in sorted(template_refs.items())},
        "sharedOptionGroups": shared_groups,
    }
