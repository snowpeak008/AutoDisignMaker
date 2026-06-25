"""Contracts and constants for Step 02 L5 entity supplement."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

PROMPT_PATH = Path(__file__).with_name("prompts") / "supplement.txt"
FALLBACK_ENTITIES_PATH = (
    Path(__file__).with_name("data") / "genre_fallback_entities.json"
)
VALID_ENTITY_KINDS = {
    "weapon",
    "character",
    "enemy",
    "ability",
    "room",
    "resource",
    "ui",
    "scene",
    "system",
    "config",
    "audio",
}
DEFAULT_TARGET_KINDS = ["weapon", "character", "ability", "room", "enemy"]
DEFAULT_MIN_PER_KIND = {
    "weapon": 3,
    "character": 1,
    "ability": 5,
    "room": 3,
    "enemy": 3,
}
NODE_BY_KIND = {
    "weapon": "combat_node",
    "enemy": "combat_node",
    "ability": "ability_node",
    "room": "room_node",
    "character": "character_node",
    "resource": "resource_node",
    "ui": "ui_node",
    "scene": "room_node",
    "system": "build_node",
    "config": "meta_node",
    "audio": "ui_node",
}


def text(value: Any) -> str:
    """Return a stripped string for loose parsed values."""
    return str(value or "").strip()


def field(item: Any, name: str, default: Any = "") -> Any:
    """Read a field from dict-like or object-like parsed selections."""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def selection_label(item: Any) -> str:
    """Return a readable selection label."""
    label = field(item, "label", "")
    if label:
        return text(label)
    item_type = text(field(item, "item_type"))
    option = text(field(item, "option"))
    return f"{item_type}：{option}" if item_type else option


@dataclass
class SupplementRequest:
    """Structured request sent to the L5 supplement model."""

    project_name: str
    genre: str
    core_loop: list[str]
    systems: list[dict[str, Any]]
    existing_entities: list[dict[str, Any]]
    l4_decisions: dict[str, Any]
    target_kinds: list[str]
    min_per_kind: dict[str, int]
    missing_node_ids: list[str]
    known_node_ids: dict[str, str]
    request_hash: str = ""
    schema_version: int = 1


@dataclass
class SupplementResult:
    """Merged L5 entities plus execution metadata."""

    entities: list[dict[str, Any]]
    added_count: int
    completed_count: int
    cache_hit: bool
    adapter_used: str
    fallback_used: bool
    mode: str = "complete_approximate"
    error: str = ""
    supplement_basis_samples: list[str] = dataclass_field(default_factory=list)
