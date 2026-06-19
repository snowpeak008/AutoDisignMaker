import re


def text_tokens(value):
    text = str(value or "").lower()
    ascii_tokens = re.findall(r"[a-z0-9_]{2,}", text)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_tokens = []
    for chunk in cjk_chunks:
        cjk_tokens.extend(chunk[index:index + 2] for index in range(max(1, len(chunk) - 1)))
    return {token for token in ascii_tokens + cjk_tokens if token}


def recent_question_target_ids(ai_state, limit=3):
    target_ids = []
    for entry in ai_state.get("recentQuestionTargets", [])[-limit:]:
        if isinstance(entry, dict):
            target_ids.extend(str(item) for item in entry.get("nodeIds", []) if item)
        elif isinstance(entry, str):
            target_ids.append(entry)
    return set(target_ids)


def applicability_entry(ai_state, node_id):
    entry = (ai_state.get("applicabilityScores", {}) or {}).get(node_id, {})
    try:
        score = float(entry.get("score", 0.5))
    except (TypeError, ValueError):
        score = 0.5
    try:
        evidence_count = int(entry.get("evidenceCount", 0) or 0)
    except (TypeError, ValueError):
        evidence_count = 0
    return score, evidence_count


def candidate_node_ids(engine, project_state, ai_state, user_text, limit=5):
    focus_domains = set(engine.profile_focus_domains(project_state))
    if not focus_domains:
        focus_domains = {domain_doc["domain"]["id"] for domain_doc in engine.domains[:4]}
    user_tokens = text_tokens(user_text)
    recent_targets = recent_question_target_ids(ai_state)
    scored = []
    for node in engine.nodes:
        node_id = node["id"]
        node_state = project_state.get("nodes", {}).get(node_id, {})
        effective = engine.effective_node_state(node, project_state)
        score = 0.0
        if node.get("domain") in focus_domains:
            score += 3.0
        applicability_score, evidence_count = applicability_entry(ai_state, node_id)
        score += applicability_score * 2.0
        if evidence_count and 0.35 <= applicability_score < 0.75:
            score += 1.5
        if node_state.get("riskNote", "").strip():
            score += 2.0
        if engine.node_has_l4_gap(node, project_state):
            score += 1.25
        if user_tokens:
            node_tokens = text_tokens(engine.node_search_index.get(node_id, ""))
            score += min(len(user_tokens & node_tokens) * 0.35, 3.0)
        if effective == "not_started":
            score += 0.5
        elif effective == "completed":
            score -= 1.0
        elif effective == "not_applicable":
            score -= 3.0
        if node_id in recent_targets:
            score -= 2.5
        scored.append((score, node_id))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    chosen = [node_id for score, node_id in scored if score > -2.0][:limit]
    if len(chosen) < limit:
        for node in engine.nodes:
            if node["id"] not in chosen and node.get("domain") in focus_domains:
                chosen.append(node["id"])
            if len(chosen) >= limit:
                break
    return chosen[:limit]
