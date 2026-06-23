"""Pure entity helpers for Step 02 L5 supplement."""

from __future__ import annotations

import json
import re
from typing import Any

from pipeline.step_02_design_review_freeze.supplement_contracts import (
    NODE_BY_KIND,
    VALID_ENTITY_KINDS,
    text,
)


def validate_entity(entity: dict[str, Any]) -> bool:
    """Return True when a generated entity has required L5 fields."""
    if not isinstance(entity, dict):
        return False
    label = text(entity.get("label"))
    kind = text(entity.get("kind"))
    schema = text(entity.get("schema"))
    node_id = text(entity.get("node_id"))
    if not label or not kind or not schema or not node_id:
        return False
    if kind not in VALID_ENTITY_KINDS:
        return False
    return True


def normalize_entity(entity: dict[str, Any]) -> dict[str, Any]:
    """Normalize generated entity fields for downstream Step 03/04 use."""
    normalized = dict(entity)
    kind = text(normalized.get("kind")) or "resource"
    normalized["label"] = text(normalized.get("label"))
    normalized["kind"] = kind
    normalized["schema"] = text(normalized.get("schema")) or f"{kind}.v1"
    normalized["node_id"] = text(normalized.get("node_id")) or NODE_BY_KIND.get(
        kind, "design_node"
    )
    normalized["dependencies"] = [text(normalized["node_id"])]
    normalized.setdefault("status", "precise")
    normalized.setdefault("source", "ai_supplement")
    normalized.setdefault("purpose", text(normalized.get("supplement_basis")))
    return normalized


def merge_entities(
    original: list[dict[str, Any]],
    supplemented: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Merge generated entities without replacing precise user entities."""
    normalized = [
        normalize_entity(entity) for entity in supplemented if validate_entity(entity)
    ]
    used_indexes: set[int] = set()
    merged: list[dict[str, Any]] = []
    completed_count = 0

    for entity in original:
        if text(entity.get("status")) == "approximate":
            replacement_index = _matching_supplement_index(
                entity, normalized, used_indexes
            )
            if replacement_index is not None:
                replacement = dict(normalized[replacement_index])
                replacement["source_selection_id"] = entity.get(
                    "source_selection_id", ""
                )
                replacement["completed_from"] = entity.get("entity_id", "")
                merged.append(replacement)
                used_indexes.add(replacement_index)
                completed_count += 1
                continue
        merged.append(dict(entity))

    seen = {_dedupe_key(entity) for entity in merged}
    added_count = 0
    for index, entity in enumerate(normalized):
        if index in used_indexes:
            continue
        key = _dedupe_key(entity)
        if key in seen:
            continue
        merged.append(dict(entity))
        seen.add(key)
        added_count += 1

    for index, entity in enumerate(merged, 1):
        entity["entity_id"] = f"ENT-{index:03d}"
    return merged, added_count, completed_count


def parse_response_entities(output_text: str) -> list[dict[str, Any]]:
    """Parse JSON model output into validated supplement entities."""
    payload = extract_json(output_text)
    entities = (
        payload.get("supplemented_entities", []) if isinstance(payload, dict) else []
    )
    if not isinstance(entities, list):
        return []
    return [
        normalize_entity(entity)
        for entity in entities
        if isinstance(entity, dict) and validate_entity(entity)
    ]


def extract_json(output_text: str) -> dict[str, Any]:
    """Extract the first JSON object from model text."""
    try:
        payload = json.loads(output_text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output_text, flags=re.DOTALL)
    if fence:
        try:
            payload = json.loads(fence.group(1))
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
    start = output_text.find("{")
    end = output_text.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(output_text[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _matching_supplement_index(
    approximate: dict[str, Any],
    supplemented: list[dict[str, Any]],
    used_indexes: set[int],
) -> int | None:
    approximate_kind = text(approximate.get("kind"))
    approximate_label = text(approximate.get("label")).lower()
    for index, entity in enumerate(supplemented):
        if index in used_indexes:
            continue
        if text(entity.get("kind")) != approximate_kind:
            continue
        label = text(entity.get("label")).lower()
        if (
            not approximate_label
            or label in approximate_label
            or approximate_label in label
        ):
            return index
    for index, entity in enumerate(supplemented):
        if index not in used_indexes and text(entity.get("kind")) == approximate_kind:
            return index
    return None


def _dedupe_key(entity: dict[str, Any]) -> str:
    return f"{text(entity.get('kind')).lower()}::{text(entity.get('label')).lower()}"
