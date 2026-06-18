import hashlib
import json
import shutil
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from design_tool.data_loader import runtime_project_root


PROMPT_FRAMEWORK_SCHEMA_VERSION = "1.0"
PROMPT_FRAMEWORK_VERSION = "1"
MAX_DIRECT_DEPENDENCIES = 2
MAX_DEPENDENCY_DEPTH = 2

MODULE_IDS = [
    "questioning",
    "followup",
    "routing",
    "interpretation",
    "mapping",
    "confidence",
    "readiness",
    "output",
    "memory_influence",
]

FORBIDDEN_PROMPT_BOUNDARY_TEXT = (
    "修改设计选项",
    "更改设计选项",
    "修改领域",
    "更改领域",
    "新增领域",
    "删除领域",
    "新增节点",
    "删除节点",
    "新增 L4",
    "新增L4",
    "删除 L4",
    "删除L4",
    "修改 L4",
    "修改L4",
    "修改 MDA",
    "修改MDA",
    "编辑文件",
    "写入文件",
    "直接改文件",
    "data/domains",
)

DISCLOSURE_DIRECTIVES = (
    "告诉用户正在验证",
    "向用户说明正在验证",
    "告诉用户历史记忆",
    "展示记忆信号",
    "显示暂存信号",
)


DEFAULT_MODULES = {
    "questioning": {
        "title": "问题措辞",
        "dependencies": [],
        "rules": [
            {
                "id": "role_and_goal",
                "text": "你是商业游戏设计 AI 访谈助手，通过间接追问帮助设计者完成设计。",
            },
            {
                "id": "indirect_questions",
                "text": "不要直接询问每个选项怎么选；用场景、取舍、约束和例子追问。",
            },
            {
                "id": "max_group_size",
                "text": "每个追问问题组最多 4 个问题，并且问题必须有顺序。",
            },
            {
                "id": "non_consecutive_review",
                "text": "当相近问题频繁出现时，用非连续、隐晦的追问复核提问弱点，不要告诉用户正在验证历史记忆。",
            },
        ],
    },
    "followup": {
        "title": "追问策略",
        "dependencies": ["questioning"],
        "rules": [
            {
                "id": "clarify_before_mapping",
                "text": "含糊、矛盾或证据不足时，先澄清设计意图，再映射到框架选项。",
            },
            {
                "id": "avoid_repeated_near_questions",
                "text": "避免连续追问同一含义的问题；必要复核必须间隔其他主题或批次。",
            },
        ],
    },
    "routing": {
        "title": "路线规划",
        "dependencies": ["questioning"],
        "rules": [
            {
                "id": "mda_route",
                "text": "访谈路线按体验目标、玩家动态、机制抓手、边界约束、验收信号推进，并结合项目画像和节点适用性排序。",
            },
            {
                "id": "natural_language_reorder",
                "text": "如果用户自然语言纠偏，先确认重排路线，不要让用户手动选择节点。",
            },
        ],
    },
    "interpretation": {
        "title": "意图解释",
        "dependencies": ["questioning"],
        "rules": [
            {
                "id": "interpret_context",
                "text": "解释用户回答时优先识别目标玩家、核心体验、商业约束、制作约束和风险信号。",
            },
            {
                "id": "do_not_use_framework_terms_as_user_terms",
                "text": "不要要求用户使用领域、节点、MDA 或 L4 等框架术语；AI 负责把自然语言转为结构化推断。",
            },
        ],
    },
    "mapping": {
        "title": "映射规则",
        "dependencies": ["interpretation"],
        "rules": [
            {
                "id": "map_to_existing_options_only",
                "text": "只能把用户意图映射到现有领域、节点、checklist、L4 选项和关系；不得新增或修改设计选项框架。",
            },
            {
                "id": "map_with_reason",
                "text": "每个映射必须给出简短理由，并能追溯到用户回答或明确项目上下文。",
            },
        ],
    },
    "confidence": {
        "title": "置信度",
        "dependencies": [],
        "rules": [
            {
                "id": "high_confidence_threshold",
                "text": "低置信内容不得写入项目输出；0.75 及以上才可作为高置信内容。",
            },
            {
                "id": "conservative_when_ambiguous",
                "text": "当一个回答可能映射到多个选项时，降低置信度并继续澄清，不要强行落选项。",
            },
        ],
    },
    "readiness": {
        "title": "生成就绪",
        "dependencies": ["confidence"],
        "rules": [
            {
                "id": "ask_before_output",
                "text": "当接近可以生成完整方案，先询问设计者是否输出。",
            },
            {
                "id": "ten_group_checkpoint",
                "text": "每十个追问问题组必须执行生成就绪检查点，判断是否继续追问或准备输出。",
            },
        ],
    },
    "output": {
        "title": "结构化输出",
        "dependencies": ["confidence"],
        "rules": [
            {
                "id": "codex_no_file_edit",
                "text": "Codex 后端不得修改文件，只返回符合 schema 的结构化 JSON。",
            },
            {
                "id": "full_project_json_strings",
                "text": "全项目输出必须返回 projectStateJson 和 confidenceMapJson 字符串，并由工具侧校验后应用。",
            },
            {
                "id": "option_differences",
                "text": "全项目输出必须用 optionDifferences 说明当前项目与 AI 输出之间的选项差异。",
            },
        ],
    },
    "memory_influence": {
        "title": "记忆影响",
        "dependencies": ["questioning", "confidence"],
        "rules": [
            {
                "id": "hidden_memory",
                "text": "记忆影响必须完全隐式，不得向用户说明正在验证历史记忆、暂存信号或提示词框架版本。",
            },
            {
                "id": "staged_signal_low_weight",
                "text": "暂存信号只能低权重影响澄清问题或保守映射，不能直接决定选项、提高置信度或替用户回答。",
            },
        ],
    },
}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def prompt_framework_dir(runtime_root=None):
    return Path(runtime_root or runtime_project_root()) / "data" / "design" / "prompt_framework"


def framework_memory_dir(runtime_root=None):
    return Path(runtime_root or runtime_project_root()) / "ucos" / "knowledge" / "framework_signals"


def stable_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value):
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def bump_version(value):
    text = str(value or "0")
    parts = text.split(".")
    if parts and all(part.isdigit() for part in parts):
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    return f"{text}.1"


def module_path(root, module_id):
    return prompt_framework_dir(root) / "modules" / f"{module_id}.json"


def make_default_module(module_id, index):
    payload = deepcopy(DEFAULT_MODULES[module_id])
    return {
        "schemaVersion": PROMPT_FRAMEWORK_SCHEMA_VERSION,
        "moduleId": module_id,
        "moduleVersion": PROMPT_FRAMEWORK_VERSION,
        "title": payload["title"],
        "order": index,
        "dependencies": payload.get("dependencies", []),
        "rules": payload.get("rules", []),
        "validationConstraints": {
            "forbidDesignOptionChanges": True,
            "forbidBackendParameterChanges": True,
            "maxDirectDependencies": MAX_DIRECT_DEPENDENCIES,
            "maxDependencyDepth": MAX_DEPENDENCY_DEPTH,
        },
    }


def ensure_default_prompt_framework(runtime_root=None):
    root = prompt_framework_dir(runtime_root)
    modules_dir = root / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    created_any = False
    modules = []
    for index, module_id in enumerate(MODULE_IDS, start=1):
        path = modules_dir / f"{module_id}.json"
        if not path.exists():
            write_json(path, make_default_module(module_id, index))
            created_any = True
        module = load_json(path)
        modules.append({
            "moduleId": module_id,
            "path": f"modules/{module_id}.json",
            "moduleVersion": str(module.get("moduleVersion", PROMPT_FRAMEWORK_VERSION)),
            "hash": stable_hash(module),
            "dependencies": list(module.get("dependencies", [])),
        })
    manifest_path = root / "manifest.json"
    if not manifest_path.exists() or created_any:
        manifest = {
            "schemaVersion": PROMPT_FRAMEWORK_SCHEMA_VERSION,
            "frameworkVersion": PROMPT_FRAMEWORK_VERSION,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "moduleOrder": MODULE_IDS,
            "modules": modules,
            "limits": {
                "maxDirectDependencies": MAX_DIRECT_DEPENDENCIES,
                "maxDependencyDepth": MAX_DEPENDENCY_DEPTH,
            },
        }
        manifest["hash"] = stable_hash({key: value for key, value in manifest.items() if key != "hash"})
        write_json(manifest_path, manifest)
    return root


def load_manifest(runtime_root=None):
    root = ensure_default_prompt_framework(runtime_root)
    return load_json(root / "manifest.json")


def load_modules(runtime_root=None):
    root = ensure_default_prompt_framework(runtime_root)
    manifest = load_manifest(runtime_root)
    modules = {}
    for module_info in manifest.get("modules", []):
        module_id = module_info.get("moduleId")
        if module_id:
            modules[module_id] = load_json(root / module_info.get("path", f"modules/{module_id}.json"))
    return modules


def prompt_version_snapshot(runtime_root=None):
    manifest = load_manifest(runtime_root)
    return {
        "frameworkVersion": str(manifest.get("frameworkVersion", PROMPT_FRAMEWORK_VERSION)),
        "modules": {
            module.get("moduleId"): str(module.get("moduleVersion", ""))
            for module in manifest.get("modules", [])
            if module.get("moduleId")
        },
        "manifestHash": manifest.get("hash", ""),
    }


def dependency_depth(module_id, dependency_map, seen=None):
    seen = set(seen or [])
    if module_id in seen:
        return MAX_DEPENDENCY_DEPTH + 1
    seen.add(module_id)
    deps = dependency_map.get(module_id, [])
    if not deps:
        return 0
    return 1 + max(dependency_depth(dep, dependency_map, seen.copy()) for dep in deps)


def has_cycle(module_id, dependency_map, visiting=None, visited=None):
    visiting = set(visiting or [])
    visited = set(visited or [])
    if module_id in visiting:
        return True
    if module_id in visited:
        return False
    visiting.add(module_id)
    for dep in dependency_map.get(module_id, []):
        if has_cycle(dep, dependency_map, visiting, visited):
            return True
    visiting.remove(module_id)
    visited.add(module_id)
    return False


def validate_prompt_framework(runtime_root=None, root_override=None):
    root = Path(root_override) if root_override else ensure_default_prompt_framework(runtime_root)
    errors = []
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return ["缺少提示词框架清单 manifest.json。"]
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as error:
        return [f"提示词框架清单无法读取：{error}"]
    modules_info = manifest.get("modules", [])
    module_order = manifest.get("moduleOrder", [])
    if module_order != [info.get("moduleId") for info in modules_info]:
        errors.append("manifest 的 moduleOrder 与 modules 顺序不一致。")
    modules = {}
    dependency_map = {}
    for module_info in modules_info:
        module_id = module_info.get("moduleId", "")
        if module_id not in MODULE_IDS:
            errors.append(f"未知提示词模块：{module_id}")
            continue
        path = root / module_info.get("path", f"modules/{module_id}.json")
        if not path.exists():
            errors.append(f"缺少提示词模块文件：{path}")
            continue
        try:
            module = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"提示词模块 {module_id} 无法读取：{error}")
            continue
        modules[module_id] = module
        if module.get("moduleId") != module_id:
            errors.append(f"提示词模块 {module_id} 的 moduleId 不一致。")
        if not module.get("moduleVersion"):
            errors.append(f"提示词模块 {module_id} 缺少 moduleVersion。")
        if stable_hash(module) != module_info.get("hash"):
            errors.append(f"提示词模块 {module_id} hash 与 manifest 不一致。")
        deps = list(module.get("dependencies", []))
        dependency_map[module_id] = deps
        if len(deps) > MAX_DIRECT_DEPENDENCIES:
            errors.append(f"提示词模块 {module_id} 直接依赖超过 {MAX_DIRECT_DEPENDENCIES} 个。")
        for dep in deps:
            if dep not in MODULE_IDS:
                errors.append(f"提示词模块 {module_id} 依赖未知模块：{dep}")
        rule_ids = set()
        for rule in module.get("rules", []):
            rule_id = str(rule.get("id", ""))
            if not rule_id:
                errors.append(f"提示词模块 {module_id} 存在空规则 id。")
            elif rule_id in rule_ids:
                errors.append(f"提示词模块 {module_id} 存在重复规则 id：{rule_id}")
            rule_ids.add(rule_id)
            text = str(rule.get("text", ""))
            if not text.strip():
                errors.append(f"提示词模块 {module_id} / {rule_id} 规则文本为空。")
            forbidden = validate_rule_text_boundary(text)
            if forbidden:
                errors.append(f"提示词模块 {module_id} / {rule_id} 规则文本越界：{', '.join(forbidden)}")
            for directive in DISCLOSURE_DIRECTIVES:
                if directive in text and "不得" not in text and "不要" not in text:
                    errors.append(f"提示词模块 {module_id} / {rule_id} 暴露隐式记忆行为：{directive}")
    for module_id in dependency_map:
        if has_cycle(module_id, dependency_map):
            errors.append(f"提示词模块依赖存在循环：{module_id}")
        if dependency_depth(module_id, dependency_map) > MAX_DEPENDENCY_DEPTH:
            errors.append(f"提示词模块 {module_id} 依赖深度超过 {MAX_DEPENDENCY_DEPTH}。")
    return errors


def validate_candidate_prompt_framework(runtime_root=None, root_override=None, diff=None):
    errors = validate_prompt_framework(runtime_root=runtime_root, root_override=root_override)
    root = Path(root_override) if root_override else ensure_default_prompt_framework(runtime_root)
    modules = {}
    try:
        manifest = load_json(root / "manifest.json")
        for module_info in manifest.get("modules", []):
            module_id = module_info.get("moduleId")
            if module_id:
                modules[module_id] = load_json(root / module_info.get("path", f"modules/{module_id}.json"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"候选提示词框架无法加载用于回归校验：{error}")
        return errors

    mapping_text = "\n".join(module_rules_text(modules.get("mapping", {})))
    if "现有" not in mapping_text or "不得新增" not in mapping_text:
        errors.append("映射回归失败：mapping 模块必须保留只映射到现有框架项、不得新增的约束。")

    output_text = "\n".join(module_rules_text(modules.get("output", {})))
    if "schema" not in output_text or "JSON" not in output_text:
        errors.append("输出回归失败：output 模块必须保留结构化 JSON/schema 约束。")

    memory_text = "\n".join(module_rules_text(modules.get("memory_influence", {})))
    if "隐式" not in memory_text or "不得" not in memory_text:
        errors.append("隐式性校验失败：memory_influence 模块必须保留完全隐式和不得暴露的约束。")

    if isinstance(diff, dict):
        operation = diff.get("operation", "")
        if operation in ("delete_rule", "merge_rules"):
            module_id = diff.get("targetModule", "")
            rules = modules.get(module_id, {}).get("rules", [])
            if len(rules) < 1:
                errors.append(f"固定访谈回归失败：{module_id} 模块删除/合并后规则为空。")
        if not diff.get("evidenceIds"):
            errors.append("候选提示词 diff 缺少关联证据。")
        for key in ("expectedEffect", "risk", "rollbackPoint", "reason"):
            if not str(diff.get(key, "")).strip():
                errors.append(f"候选提示词 diff 缺少 {key}。")
    if runtime_root:
        regression_path = framework_memory_dir(runtime_root) / "regression_examples.jsonl"
        if regression_path.exists():
            try:
                with regression_path.open("r", encoding="utf-8") as file:
                    for line_no, line in enumerate(file, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        example = json.loads(line)
                        for field in ("inputSummary", "expectedFollowupType", "forbiddenBehavior", "expectedMappingConstraints"):
                            if field not in example:
                                errors.append(f"结构化回归样例第 {line_no} 行缺少 {field}。")
            except (OSError, json.JSONDecodeError) as error:
                errors.append(f"结构化回归样例无法读取：{error}")
    return errors


def module_rules_text(module):
    lines = []
    for rule in module.get("rules", []):
        text = str(rule.get("text", "")).strip()
        if text:
            lines.append(text)
    return lines


def compose_prompt_framework(runtime_root=None):
    manifest = load_manifest(runtime_root)
    modules = load_modules(runtime_root)
    ordered_modules = []
    rules = []
    for module_id in manifest.get("moduleOrder", []):
        module = modules.get(module_id)
        if not module:
            continue
        ordered_modules.append({
            "moduleId": module_id,
            "title": module.get("title", module_id),
            "moduleVersion": str(module.get("moduleVersion", "")),
            "dependencies": module.get("dependencies", []),
            "rules": module.get("rules", []),
        })
        rules.extend(module_rules_text(module))
    return {
        "snapshot": prompt_version_snapshot(runtime_root),
        "rules": rules,
        "modules": ordered_modules,
    }


def compose_prompt_prefix(runtime_root=None):
    framework = compose_prompt_framework(runtime_root)
    lines = [
        "以下为当前锁定的 AI 提问提示词框架。它只约束 AI 如何提问、解释、映射和判断置信度；不得修改设计选项框架。",
        f"frameworkVersion: {framework['snapshot'].get('frameworkVersion', '')}",
    ]
    for module in framework["modules"]:
        lines.append(f"\n[{module['moduleId']} v{module.get('moduleVersion', '')}] {module.get('title', '')}")
        for rule in module.get("rules", []):
            lines.append(f"- {rule.get('id', '')}: {rule.get('text', '')}")
    return "\n".join(lines)


def sync_manifest_hashes(root):
    root = Path(root)
    manifest = load_json(root / "manifest.json")
    modules = []
    for module_id in manifest.get("moduleOrder", MODULE_IDS):
        path = root / "modules" / f"{module_id}.json"
        module = load_json(path)
        modules.append({
            "moduleId": module_id,
            "path": f"modules/{module_id}.json",
            "moduleVersion": str(module.get("moduleVersion", "")),
            "hash": stable_hash(module),
            "dependencies": list(module.get("dependencies", [])),
        })
    manifest["modules"] = modules
    manifest["updatedAt"] = now_iso()
    manifest["hash"] = stable_hash({key: value for key, value in manifest.items() if key != "hash"})
    write_json(root / "manifest.json", manifest)
    return manifest


def copy_prompt_framework(src_root, target_root):
    src_root = Path(src_root)
    target_root = Path(target_root)
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(src_root, target_root)


def rule_index(module, rule_id):
    for index, rule in enumerate(module.get("rules", [])):
        if rule.get("id") == rule_id:
            return index
    return -1


def validate_rule_text_boundary(text):
    normalized = str(text or "")
    hits = []
    for item in FORBIDDEN_PROMPT_BOUNDARY_TEXT:
        index = normalized.find(item)
        if index < 0:
            continue
        window = normalized[max(0, index - 8):index + len(item) + 8]
        if any(marker in window for marker in ("不得", "不要", "不能", "禁止")):
            continue
        hits.append(item)
    return hits


def validate_structured_diff(diff):
    errors = []
    if not isinstance(diff, dict):
        return ["提示词候选 diff 不是 JSON 对象。"]
    module_id = diff.get("targetModule", "")
    operation = diff.get("operation", "")
    if module_id not in MODULE_IDS:
        errors.append(f"提示词候选目标模块非法：{module_id}")
    if operation not in ("add_rule", "edit_rule", "delete_rule", "merge_rules"):
        errors.append(f"提示词候选操作非法：{operation}")
    if operation in ("add_rule", "edit_rule", "merge_rules"):
        candidate_texts = []
        if isinstance(diff.get("newRule"), dict):
            candidate_texts.append(diff["newRule"].get("text", ""))
        if diff.get("newRuleText"):
            candidate_texts.append(diff.get("newRuleText", ""))
        for text in candidate_texts:
            forbidden = validate_rule_text_boundary(text)
            if forbidden:
                errors.append(f"提示词候选越界：规则文本包含 {', '.join(forbidden)}")
    return errors


def apply_structured_diff_to_module(module, diff):
    operation = diff.get("operation")
    rules = module.setdefault("rules", [])
    if operation == "add_rule":
        new_rule = deepcopy(diff.get("newRule") or {})
        if not new_rule.get("id") or not new_rule.get("text"):
            return ["新增规则缺少 id 或 text。"]
        if rule_index(module, new_rule["id"]) >= 0:
            return [f"新增规则 id 已存在：{new_rule['id']}"]
        rules.append({"id": str(new_rule["id"]), "text": str(new_rule["text"])})
    elif operation == "edit_rule":
        target_rule_id = diff.get("targetRuleId", "")
        index = rule_index(module, target_rule_id)
        if index < 0:
            return [f"编辑目标规则不存在：{target_rule_id}"]
        rules[index]["text"] = str(diff.get("newRuleText") or diff.get("newRule", {}).get("text", ""))
        if not rules[index]["text"].strip():
            return [f"编辑目标规则文本为空：{target_rule_id}"]
    elif operation == "delete_rule":
        target_rule_id = diff.get("targetRuleId", "")
        index = rule_index(module, target_rule_id)
        if index < 0:
            return [f"删除目标规则不存在：{target_rule_id}"]
        del rules[index]
    elif operation == "merge_rules":
        source_rule_ids = list(diff.get("sourceRuleIds", []))
        new_rule = deepcopy(diff.get("newRule") or {})
        if len(source_rule_ids) < 2:
            return ["合并规则至少需要两个 sourceRuleIds。"]
        if not new_rule.get("id") or not new_rule.get("text"):
            return ["合并后的新规则缺少 id 或 text。"]
        missing = [rule_id for rule_id in source_rule_ids if rule_index(module, rule_id) < 0]
        if missing:
            return [f"合并源规则不存在：{', '.join(missing)}"]
        module["rules"] = [rule for rule in rules if rule.get("id") not in set(source_rule_ids)]
        module["rules"].append({"id": str(new_rule["id"]), "text": str(new_rule["text"])})
    return []


def create_candidate_from_diff(runtime_root, diff, candidate_id=None):
    errors = validate_structured_diff(diff)
    if errors:
        return "", errors
    source_root = ensure_default_prompt_framework(runtime_root)
    candidate_id = candidate_id or f"candidate_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    candidate_root = framework_memory_dir(runtime_root) / "candidates" / candidate_id / "prompt_framework"
    copy_prompt_framework(source_root, candidate_root)
    module_id = diff["targetModule"]
    module_file = candidate_root / "modules" / f"{module_id}.json"
    module = load_json(module_file)
    apply_errors = apply_structured_diff_to_module(module, diff)
    if apply_errors:
        return str(candidate_root), apply_errors
    module["moduleVersion"] = bump_version(module.get("moduleVersion"))
    module["updatedAt"] = now_iso()
    write_json(module_file, module)
    manifest = load_json(candidate_root / "manifest.json")
    manifest["frameworkVersion"] = bump_version(manifest.get("frameworkVersion"))
    manifest["candidate"] = {
        "candidateId": candidate_id,
        "createdAt": now_iso(),
        "structuredDiff": diff,
    }
    write_json(candidate_root / "manifest.json", manifest)
    sync_manifest_hashes(candidate_root)
    return str(candidate_root), validate_candidate_prompt_framework(runtime_root=runtime_root, root_override=candidate_root, diff=diff)


def version_records_dir(runtime_root):
    return framework_memory_dir(runtime_root) / "versions"


def promote_candidate(runtime_root, candidate_root, metadata=None):
    candidate_root = Path(candidate_root)
    metadata = metadata or {}
    errors = validate_candidate_prompt_framework(runtime_root=runtime_root, root_override=candidate_root, diff=metadata.get("structuredDiff"))
    if errors:
        return "", errors
    current_root = ensure_default_prompt_framework(runtime_root)
    candidate_manifest = load_json(candidate_root / "manifest.json")
    version_id = f"prompt_framework_{candidate_manifest.get('frameworkVersion', 'unknown')}_{uuid.uuid4().hex[:8]}"
    record_dir = version_records_dir(runtime_root) / version_id
    record_dir.mkdir(parents=True, exist_ok=True)
    previous_dir = record_dir / "previous_prompt_framework"
    new_dir = record_dir / "new_prompt_framework"
    copy_prompt_framework(current_root, previous_dir)
    copy_prompt_framework(candidate_root, new_dir)
    previous_snapshot = prompt_version_snapshot(runtime_root)
    if current_root.exists():
        shutil.rmtree(current_root)
    shutil.copytree(candidate_root, current_root)
    new_snapshot = prompt_version_snapshot(runtime_root)
    record = {
        "versionId": version_id,
        "createdAt": now_iso(),
        "type": "promotion",
        "previousSnapshot": previous_snapshot,
        "newSnapshot": new_snapshot,
        "metadata": deepcopy(metadata or {}),
        "rollbackTarget": str(previous_dir),
    }
    write_json(record_dir / "record.json", record)
    return version_id, []


def rollback_to_previous(runtime_root, version_id=None, reason=""):
    records_root = version_records_dir(runtime_root)
    if not records_root.exists():
        return "", ["没有可回滚的提示词框架版本。"]
    candidates = sorted(records_root.glob("prompt_framework_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if version_id:
        candidates = [records_root / version_id]
    for record_dir in candidates:
        record_path = record_dir / "record.json"
        previous_dir = record_dir / "previous_prompt_framework"
        if record_path.exists() and previous_dir.exists():
            current_root = ensure_default_prompt_framework(runtime_root)
            rollback_id = f"rollback_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
            before_snapshot = prompt_version_snapshot(runtime_root)
            if current_root.exists():
                shutil.rmtree(current_root)
            shutil.copytree(previous_dir, current_root)
            after_snapshot = prompt_version_snapshot(runtime_root)
            write_json(records_root / rollback_id / "record.json", {
                "versionId": rollback_id,
                "createdAt": now_iso(),
                "type": "rollback",
                "rolledBackPromotion": record_dir.name,
                "reason": reason,
                "beforeSnapshot": before_snapshot,
                "afterSnapshot": after_snapshot,
            })
            return rollback_id, []
    return "", ["没有找到可用的回滚目标。"]
