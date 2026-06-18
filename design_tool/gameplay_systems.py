import re
from copy import deepcopy


GAMEPLAY_SYSTEM_SCHEMA_VERSION = "1.0"
CUSTOM_CATEGORY = "custom"
WEIGHT_TYPE_PERCENT = "percent"

DEFAULT_INTERVIEW_QUESTIONS = [
    "除了上方已选系统，你的玩法是否还有玩家会反复接触的独立规则模块？",
    "这些补充系统主要解决什么体验、目标、约束或商业需求？",
    "补充系统是否需要独立占比，还是应并入某个已选系统？",
]


def slugify_system_id(value, existing_ids=None):
    existing_ids = set(existing_ids or [])
    text = str(value or "").strip().lower()
    ascii_text = re.sub(r"[^0-9a-z]+", "_", text).strip("_")
    if not ascii_text:
        ascii_text = "custom_system"
    if not ascii_text.startswith("custom_"):
        ascii_text = f"custom_{ascii_text}"
    candidate = ascii_text
    index = 2
    while candidate in existing_ids:
        candidate = f"{ascii_text}_{index}"
        index += 1
    return candidate


def normalize_option(option):
    option = option if isinstance(option, dict) else {}
    option_id = str(option.get("id") or "").strip()
    name = str(option.get("name") or option_id).strip()
    category = str(option.get("category") or "preset").strip() or "preset"
    mapping_desc = str(option.get("mapping_desc") or option.get("mappingDesc") or "").strip()
    return {
        "id": option_id,
        "name": name,
        "category": category,
        "mapping_desc": mapping_desc,
    }


def normalize_options(options):
    normalized = []
    seen = set()
    for option in options or []:
        item = normalize_option(option)
        if not item["id"] or item["id"] in seen:
            continue
        seen.add(item["id"])
        normalized.append(item)
    return normalized


def empty_state():
    return {
        "schemaVersion": GAMEPLAY_SYSTEM_SCHEMA_VERSION,
        "selected": [],
        "custom": [],
        "weights": {},
        "coreLoops": {},
        "interview": {
            "questions": deepcopy(DEFAULT_INTERVIEW_QUESTIONS),
            "answers": [],
            "parsedSystemIds": [],
        },
    }


def normalize_weight(value):
    if isinstance(value, dict):
        raw_weight = value.get("weight", "")
        weight_type = str(value.get("weight_type") or value.get("weightType") or WEIGHT_TYPE_PERCENT)
    else:
        raw_weight = value
        weight_type = WEIGHT_TYPE_PERCENT
    if raw_weight in (None, ""):
        return {"weight": "", "weight_type": weight_type}
    try:
        number = float(raw_weight)
    except (TypeError, ValueError):
        return {"weight": "", "weight_type": weight_type}
    number = max(0.0, min(100.0, number))
    if number.is_integer():
        number = int(number)
    return {"weight": number, "weight_type": weight_type}


def normalize_custom_system(raw, existing_ids=None):
    raw = raw if isinstance(raw, dict) else {"name": raw}
    existing_ids = set(existing_ids or [])
    name = str(raw.get("name") or raw.get("label") or "").strip()
    system_id = str(raw.get("id") or "").strip()
    if not system_id:
        system_id = slugify_system_id(name, existing_ids)
    mapping_desc = str(raw.get("mapping_desc") or raw.get("mappingDesc") or "").strip()
    if not mapping_desc:
        mapping_desc = "用户手动补充的玩法系统，需在后续设计中明确规则、边界和验收信号。"
    return {
        "id": system_id,
        "name": name or system_id,
        "category": CUSTOM_CATEGORY,
        "mapping_desc": mapping_desc,
    }


def normalize_state(state, preset_options=None):
    preset_options = normalize_options(preset_options or [])
    preset_ids = {option["id"] for option in preset_options}
    normalized = empty_state()
    incoming = state if isinstance(state, dict) else {}
    normalized["schemaVersion"] = GAMEPLAY_SYSTEM_SCHEMA_VERSION

    custom = []
    existing_ids = set(preset_ids)
    for raw_custom in incoming.get("custom", []) or []:
        item = normalize_custom_system(raw_custom, existing_ids)
        if item["id"] in existing_ids:
            item["id"] = slugify_system_id(item["name"], existing_ids)
        existing_ids.add(item["id"])
        custom.append(item)
    normalized["custom"] = custom

    allowed_ids = preset_ids | {item["id"] for item in custom}
    selected = []
    for system_id in incoming.get("selected", []) or []:
        system_id = str(system_id)
        if system_id in allowed_ids and system_id not in selected:
            selected.append(system_id)
    normalized["selected"] = selected

    raw_weights = incoming.get("weights", {}) or {}
    if isinstance(raw_weights, list):
        raw_weights = {
            str(item.get("system_id") or item.get("systemId") or item.get("id")): item
            for item in raw_weights
            if isinstance(item, dict)
        }
    weights = {}
    for system_id in selected:
        weights[system_id] = normalize_weight(raw_weights.get(system_id, {}))
    normalized["weights"] = weights

    raw_loops = incoming.get("coreLoops", incoming.get("core_loops", {})) or {}
    normalized["coreLoops"] = {
        system_id: str(raw_loops.get(system_id, "") or "").strip()
        for system_id in selected
    }

    raw_interview = incoming.get("interview", {}) if isinstance(incoming.get("interview", {}), dict) else {}
    questions = raw_interview.get("questions") or DEFAULT_INTERVIEW_QUESTIONS
    normalized["interview"] = {
        "questions": [str(item) for item in questions if str(item).strip()] or deepcopy(DEFAULT_INTERVIEW_QUESTIONS),
        "answers": [str(item) for item in raw_interview.get("answers", []) if str(item).strip()],
        "parsedSystemIds": [
            str(item)
            for item in raw_interview.get("parsedSystemIds", raw_interview.get("parsed_system_ids", []))
            if str(item) in allowed_ids
        ],
    }
    return normalized


def all_options(preset_options, state):
    normalized = normalize_state(state, preset_options)
    return [*normalize_options(preset_options or []), *normalized.get("custom", [])]


def option_by_id(preset_options, state):
    return {option["id"]: option for option in all_options(preset_options, state)}


def selected_systems(preset_options, state, sort_by_weight=False):
    normalized = normalize_state(state, preset_options)
    by_id = option_by_id(preset_options, normalized)
    items = []
    for system_id in normalized.get("selected", []):
        option = by_id.get(system_id)
        if not option:
            continue
        weight_entry = normalized.get("weights", {}).get(system_id, {})
        items.append({
            **option,
            "selected": True,
            "weight": weight_entry.get("weight", ""),
            "weight_type": weight_entry.get("weight_type", WEIGHT_TYPE_PERCENT),
            "core_loop": normalized.get("coreLoops", {}).get(system_id, ""),
            "source": CUSTOM_CATEGORY if option.get("category") == CUSTOM_CATEGORY else "preset",
        })
    if sort_by_weight:
        items.sort(key=lambda item: float(item["weight"] or 0), reverse=True)
    return items


def weight_summary(state):
    weights = (state or {}).get("weights", {}) if isinstance(state, dict) else {}
    selected = (state or {}).get("selected", []) if isinstance(state, dict) else []
    total = 0.0
    missing = []
    for system_id in selected:
        weight = weights.get(system_id, {}).get("weight", "")
        if weight in ("", None):
            missing.append(system_id)
            continue
        try:
            total += float(weight)
        except (TypeError, ValueError):
            missing.append(system_id)
    status = "ok"
    if missing:
        status = "missing"
    elif total > 100:
        status = "over"
    elif total < 100:
        status = "under"
    return {
        "total": round(total, 2),
        "missing": missing,
        "status": status,
    }


def validation_messages(preset_options, state):
    normalized = normalize_state(state, preset_options)
    messages = []
    if not normalized.get("selected"):
        messages.append("至少选择一个玩法系统。")
        return messages
    summary = weight_summary(normalized)
    if summary["missing"]:
        by_id = option_by_id(preset_options, normalized)
        labels = [by_id.get(system_id, {}).get("name", system_id) for system_id in summary["missing"]]
        messages.append(f"以下玩法系统尚未填写占比：{'、'.join(labels)}。")
    if summary["status"] == "over":
        messages.append(f"玩法系统总占比为 {summary['total']}%，超过 100%。")
    elif summary["status"] == "under" and not summary["missing"]:
        messages.append(f"玩法系统总占比为 {summary['total']}%，不足 100%。")
    return messages


def parse_interview_answers_to_custom_systems(answers, preset_options=None, state=None):
    preset_options = normalize_options(preset_options or [])
    state = normalize_state(state, preset_options)
    existing_names = {option["name"].casefold() for option in all_options(preset_options, state)}
    existing_ids = {option["id"] for option in all_options(preset_options, state)}
    created = []
    text = "\n".join(str(answer or "") for answer in answers or [])
    for raw_part in re.split(r"[,\n，、；;]+", text):
        name = raw_part.strip().strip("。.!?？：:")
        name = re.sub(r"^(还需要|需要|补充|新增|包括|以及|和|与)\s*", "", name).strip()
        if name.startswith(("用于", "用来", "主要", "为了", "解决", "改变", "说明", "因为")):
            continue
        name = re.sub(r"(系统|玩法模块|模块)$", r"\1", name).strip()
        if not name or len(name) < 2 or len(name) > 30:
            continue
        if any(stop in name for stop in ("没有", "暂无", "不需要", "不用")):
            continue
        if name.casefold() in existing_names:
            continue
        item = normalize_custom_system(
            {
                "name": name,
                "mapping_desc": f"AI 访谈兜底补充：{name} 需要在后续流程中明确规则、边界、占比和核心循环。",
            },
            existing_ids,
        )
        existing_ids.add(item["id"])
        existing_names.add(item["name"].casefold())
        created.append(item)
    return created
