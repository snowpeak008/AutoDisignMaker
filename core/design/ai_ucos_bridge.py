"""Bridge between AI interview and ucos memory system.

Records interview turns, AI reasoning, and design decisions into ucos so that
the cognitive memory system accumulates knowledge across sessions.

Three categories are written per completed turn:
  1. Raw turn replay   → ucos/knowledge/episodic/turns/
  2. AI routing context→ ucos/knowledge/short_term/    (decays with time)
  3. Design decisions  → ucos/knowledge/semantic/staging/ (high-confidence inferences)
  4. Full design event → ucos/knowledge/episodic/episodes/ (on full_project_output only)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

HIGH_CONFIDENCE_THRESHOLD: float = 0.75
SHORT_TERM_DECAY_RATE: float = 0.08
SHORT_TERM_IMPORTANCE: float = 0.6


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def record_interview_turn(
    runtime_root: Path,
    turn_id: str,
    user_text: str,
    payload: dict[str, Any],
    project_memory_id: str,
    evaluation_batch_id: str,
) -> None:
    """Record a completed AI interview turn into ucos memory.

    Called after a successful AI response has been validated and applied.
    Only successful turns (validationResult.ok = True) should be passed here.

    Args:
        runtime_root: The design workbench runtime root (sandbox/workspace).
        turn_id: Unique identifier for this turn.
        user_text: The user's original message for this turn.
        payload: The validated AI response payload.
        project_memory_id: Project-scoped memory identifier.
        evaluation_batch_id: Batch identifier for this evaluation session.
    """
    if not turn_id:
        return

    knowledge_dir = _resolve_ucos_knowledge_dir(runtime_root)
    now = _now_iso()
    mode = str(payload.get("mode", "") or "")
    inferences = list(payload.get("inferences", []) or [])

    # 1. Raw turn replay: store conversation record in episodic/turns/
    _write_episodic_turn(
        knowledge_dir=knowledge_dir,
        turn_id=turn_id,
        user_text=user_text,
        payload=payload,
        project_memory_id=project_memory_id,
        evaluation_batch_id=evaluation_batch_id,
        now=now,
    )

    # 2. AI routing context: short-term memory capturing which design nodes were explored
    router_decision = payload.get("routerDecision") or {}
    if router_decision and isinstance(router_decision, dict):
        _write_short_term_router_context(
            knowledge_dir=knowledge_dir,
            turn_id=turn_id,
            user_text=user_text,
            router_decision=router_decision,
            now=now,
        )

    # 3. High-confidence design decisions: promote to semantic memory as verifiable facts
    high_confidence_inferences = _filter_high_confidence(inferences, HIGH_CONFIDENCE_THRESHOLD)
    for inference in high_confidence_inferences:
        _write_semantic_inference(
            knowledge_dir=knowledge_dir,
            turn_id=turn_id,
            inference=inference,
            now=now,
        )

    # 4. Full design generation: create a structured episode when the AI produces
    #    a complete project output — this marks a significant memory milestone.
    is_design_generation = mode in ("full_project_output", "partial_project_output")
    if is_design_generation and payload.get("fullProjectOutput"):
        _write_design_generation_episode(
            knowledge_dir=knowledge_dir,
            turn_id=turn_id,
            user_text=user_text,
            payload=payload,
            project_memory_id=project_memory_id,
            now=now,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers: path resolution
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_ucos_knowledge_dir(runtime_root: Path) -> Path:
    """Resolve the ucos knowledge directory from the design workbench runtime root.

    The design workbench runtime_root is sandbox/workspace; the ucos directory
    lives at the project root (two levels up from runtime_root).
    Falls back to runtime_root itself if the ucos directory is not found.
    """
    candidate = runtime_root.parent.parent
    ucos_dir = candidate / "ucos" / "knowledge"
    if ucos_dir.exists():
        return ucos_dir
    # Fallback: search upward for a directory that contains ucos/
    for parent in runtime_root.parents:
        if (parent / "ucos" / "knowledge").exists():
            return parent / "ucos" / "knowledge"
    return runtime_root / "ucos" / "knowledge"


def _safe_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write data as JSON to path, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, default: Any) -> Any:
    """Read a JSON file, returning default on any error."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers: data extraction
# ──────────────────────────────────────────────────────────────────────────────

def _filter_high_confidence(
    inferences: list[dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    """Return only inferences whose confidence meets or exceeds the threshold."""
    result = []
    for inference in inferences:
        if not isinstance(inference, dict):
            continue
        try:
            confidence = float(inference.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence >= threshold:
            result.append(inference)
    return result


def _extract_project_name(full_project_output: dict[str, Any]) -> str:
    """Extract the project name from a fullProjectOutput payload."""
    project_state_raw = full_project_output.get("projectStateJson", "")
    if not isinstance(project_state_raw, str):
        return ""
    try:
        project_state = json.loads(project_state_raw)
        return str(project_state.get("projectName", "") or "")
    except (json.JSONDecodeError, AttributeError):
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers: ucos write operations
# ──────────────────────────────────────────────────────────────────────────────

def _write_episodic_turn(
    knowledge_dir: Path,
    turn_id: str,
    user_text: str,
    payload: dict[str, Any],
    project_memory_id: str,
    evaluation_batch_id: str,
    now: str,
) -> None:
    """Write the raw turn replay to ucos/knowledge/episodic/turns/.

    Uses project_memory_id and evaluation_batch_id as directory components to
    group turns by project and evaluation batch, mirroring the ai_runtime layout.
    Merges with any existing file so incremental fields (e.g., response) are appended.
    """
    project_id = str(project_memory_id or "unknown_project")
    batch_id = str(evaluation_batch_id or "unknown_batch")
    path = (
        knowledge_dir
        / "episodic"
        / "turns"
        / project_id
        / batch_id
        / f"{turn_id}.json"
    )
    existing = _read_json(path, {})
    existing.update({
        "turnId": turn_id,
        "updatedAt": now,
        "createdAt": existing.get("createdAt", now),
        "userText": str(user_text or ""),
        "mode": str(payload.get("mode", "") or ""),
        "response": {
            "mode": str(payload.get("mode", "") or ""),
            "questionGroup": payload.get("questionGroup"),
            "inferences": payload.get("inferences", []),
            "assistantMessage": str(payload.get("assistantMessage", "") or ""),
        },
    })
    _safe_write_json(path, existing)


def _write_short_term_router_context(
    knowledge_dir: Path,
    turn_id: str,
    user_text: str,
    router_decision: dict[str, Any],
    now: str,
) -> None:
    """Write the AI's routing decision to short-term memory.

    Router decisions capture which design nodes the AI considered exploring,
    providing context for which areas of the design framework are active.
    Short-term entries decay over time via MemoryEngine.decay_pass().
    """
    candidate_nodes = router_decision.get("candidateNodes", [])
    candidate_names = [
        node.get("name", node.get("id", ""))
        for node in candidate_nodes
        if isinstance(node, dict)
    ]
    stm_id = f"stm_router_{turn_id[:16]}"
    content_summary = (
        f"用户输入：{str(user_text or '')[:200]}；"
        f"候选节点：{', '.join(candidate_names)}"
    )
    entry = {
        "schema_version": "1.0",
        "stm_id": stm_id,
        "type": "ai_routing_context",
        "title": f"AI 路由决策：{', '.join(candidate_names[:3])}",
        "content": content_summary,
        "source": {
            "type": "ai_interview",
            "session_id": "",
            "file_ref": f"episodic/turns/.../{turn_id}.json",
        },
        "tags": ["ai_interview", "router_decision"] + candidate_names[:5],
        "importance": SHORT_TERM_IMPORTANCE,
        "created_at": now,
        "last_accessed": now,
        "decay_rate": SHORT_TERM_DECAY_RATE,
        "current_relevance": SHORT_TERM_IMPORTANCE,
        "consolidate_to_episodic": False,
    }
    path = knowledge_dir / "short_term" / "entries" / f"{stm_id}.json"
    _safe_write_json(path, entry)


def _write_semantic_inference(
    knowledge_dir: Path,
    turn_id: str,
    inference: dict[str, Any],
    now: str,
) -> None:
    """Write a high-confidence design decision to semantic staging.

    Semantic facts represent stable, verifiable knowledge extracted from
    interview turns. They require human review (review_required=True) before
    being promoted from staging to the main semantic knowledge base.
    """
    node_id = str(inference.get("nodeId", "") or "")
    fact_id = f"sf_interview_{turn_id[:16]}_{node_id[:16]}"
    fact = {
        "schema_version": "1.0",
        "fact_id": fact_id,
        "type": "design_decision_inference",
        "domain": "game_design",
        "subject": node_id,
        "content": {
            "nodeId": node_id,
            "checklist": inference.get("checklist", []),
            "options": inference.get("options", []),
            "confidence": inference.get("confidence", 0),
            "reason": str(inference.get("reason", "") or ""),
        },
        "source": {
            "type": "ai_interview_inference",
            "ref": turn_id,
            "episode_id": "",
        },
        "confidence": float(inference.get("confidence", 0) or 0),
        "review_required": True,
        "version": 1,
        "last_verified": now,
        "tags": ["ai_interview", "design_inference", node_id],
        "created_at": now,
    }
    path = knowledge_dir / "semantic" / "staging" / f"staged_{fact_id}.json"
    _safe_write_json(path, fact)


def _write_design_generation_episode(
    knowledge_dir: Path,
    turn_id: str,
    user_text: str,
    payload: dict[str, Any],
    project_memory_id: str,
    now: str,
) -> None:
    """Write a full design generation event as an episodic memory episode.

    Episodes represent meaningful, bounded events — in this case, the AI
    producing a complete game design output. The episode captures the key
    decisions made and links back to the originating turn.
    """
    episode_id = f"ep_design_{turn_id[:20]}"
    full_output = payload.get("fullProjectOutput") or {}
    project_name = _extract_project_name(full_output) if isinstance(full_output, dict) else ""
    inferences = list(payload.get("inferences", []) or [])
    key_decisions = [
        {"summary": str(inf.get("reason", "") or inf.get("nodeId", ""))[:200]}
        for inf in inferences[:10]
        if isinstance(inf, dict)
    ]
    episode = {
        "schema_version": "1.0",
        "episode_id": episode_id,
        "title": f"设计内容生成：{project_name or '游戏设计项目'}",
        "domain": "game_design",
        "goal": f"基于用户输入生成完整游戏设计方案。用户输入：{str(user_text or '')[:200]}",
        "reason": "full_project_output",
        "key_decisions": key_decisions,
        "outcome": {
            "status": "success",
            "result_summary": f"生成完整设计方案，项目：{project_name}",
        },
        "lessons": [],
        "related_episodes": [],
        "skill_ids": [],
        "pattern_ids_extracted": [],
        "failure_ids_extracted": [],
        "reflection_done": False,
        "created_at": now,
        "source_files": [],
        "project_memory_id": str(project_memory_id or ""),
        "turn_id": turn_id,
    }
    path = knowledge_dir / "episodic" / "episodes" / f"{episode_id}.json"
    _safe_write_json(path, episode)
