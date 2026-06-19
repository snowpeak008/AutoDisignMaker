from core.design.ai_route_planner import text_tokens
from core.design.framework_memory import append_memory_log, memory_paths, read_jsonl, signal_key


def short_text(value, limit=120):
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit]


def scored_signal(row, query_tokens, candidate_ids):
    text = " ".join([
        str(row.get("targetModule", "")),
        str(row.get("signalType", "")),
        str(row.get("summary", "")),
        str(row.get("shortExcerpt", "")),
        " ".join(str(item) for item in row.get("relatedIds", []) or []),
    ])
    row_tokens = text_tokens(text)
    overlap = len(query_tokens & row_tokens) if query_tokens and row_tokens else 0
    candidate_hit = 0
    haystack = text.lower()
    for node_id in candidate_ids or []:
        if str(node_id).lower() in haystack:
            candidate_hit += 1
    weight = 0.0
    try:
        weight = float(row.get("weight", 0.0) or 0.0)
    except (TypeError, ValueError):
        weight = 0.0
    return (overlap * 2.0) + (candidate_hit * 3.0) + min(weight, 1.0)


def retrieved_memory_context(runtime_root, project_state, user_text="", candidate_ids=None, limit=3):
    paths = memory_paths(runtime_root)
    staged = read_jsonl(paths["staged"])
    if not staged:
        return {
            "visibility": "hidden",
            "policy": "no_staged_signal",
            "signals": [],
        }
    candidate_ids = list(candidate_ids or [])
    query_tokens = text_tokens(" ".join([str(user_text or ""), " ".join(candidate_ids)]))
    seen = set()
    scored = []
    for row in reversed(staged):
        key = signal_key(row.get("targetModule", ""), row.get("signalType", ""), row.get("targetRuleId", ""), "")
        if key in seen:
            continue
        seen.add(key)
        scored.append((scored_signal(row, query_tokens, candidate_ids), row))
    scored.sort(key=lambda item: item[0], reverse=True)
    signals = []
    for _, row in scored[:limit]:
        signals.append({
            "signalId": row.get("eventId", ""),
            "targetModule": row.get("targetModule", ""),
            "signalType": row.get("signalType", ""),
            "summary": short_text(row.get("summary", ""), 120),
            "instruction": "仅可低权重影响澄清问题或保守映射；不得提高置信度、直接落选项或向用户暴露记忆。",
        })
    if signals:
        append_memory_log(
            runtime_root,
            project_state,
            action="retrieved_memory_context_injected",
            memorySignalIds=[item.get("signalId", "") for item in signals],
            decision="low_weight_prompt_context",
            reasonSummary="暂存信号按本轮用户输入和候选节点相关性筛选后隐式注入。",
            result=f"{len(signals)} staged signals",
        )
    return {
        "visibility": "hidden",
        "policy": "retrieved_top_k_low_weight_only",
        "signals": signals,
    }
