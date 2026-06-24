from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", re.IGNORECASE)
DEFAULT_SYSTEM_ID = "SYS-UNKNOWN"

DOMAIN_KEYWORDS = {
    "combat": {
        "combat",
        "attack",
        "damage",
        "weapon",
        "fight",
        "hit",
        "战斗",
        "攻击",
        "伤害",
        "武器",
    },
    "progression": {
        "progression",
        "unlock",
        "upgrade",
        "level",
        "talent",
        "成长",
        "解锁",
        "升级",
    },
    "ui": {
        "ui",
        "hud",
        "display",
        "menu",
        "interface",
        "button",
        "界面",
        "菜单",
        "显示",
    },
    "objective": {"objective", "goal", "win", "lose", "escape", "目标", "胜利", "失败"},
    "settlement": {
        "settlement",
        "reward",
        "loot",
        "drop",
        "currency",
        "奖励",
        "掉落",
        "货币",
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(value: str) -> set[str]:
    lower = value.lower()
    tokens = {match.group(0).lower() for match in TOKEN_PATTERN.finditer(lower)}
    for keywords in DOMAIN_KEYWORDS.values():
        tokens.update(token for token in keywords if token in lower)
    return tokens


class RequirementBindingEngine:
    """Bind requirements to systems with dependency, semantic, and fallback rules."""

    def __init__(self, contract: dict[str, Any]) -> None:
        self.entities = [
            entity
            for entity in contract.get("entities", [])
            if isinstance(entity, dict)
        ]
        self.systems = [
            system for system in contract.get("systems", []) if isinstance(system, dict)
        ]
        self._build_indexes()

    def _build_indexes(self) -> None:
        self.node_to_systems: dict[str, list[str]] = defaultdict(list)
        self.entity_to_systems: dict[str, list[str]] = defaultdict(list)
        self.source_to_entities: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.system_map = {
            self._system_id(system): system
            for system in self.systems
            if self._system_id(system)
        }
        for system in self.systems:
            system_id = self._system_id(system)
            if not system_id:
                continue
            for key in ("node_id", "system_id"):
                value = _text(system.get(key))
                if value:
                    self.node_to_systems[value].append(system_id)
            for dep in system.get("dependencies", []):
                if _text(dep):
                    self.node_to_systems[_text(dep)].append(system_id)
            for entity_id in system.get("related_entities", []):
                if _text(entity_id):
                    self.entity_to_systems[_text(entity_id)].append(system_id)
        for entity in self.entities:
            source = _text(entity.get("source"))
            if source:
                self.source_to_entities[source].append(entity)

    def bind_missing(self, requirements: list[dict[str, Any]]) -> dict[str, Any]:
        """Bind only requirements missing system_ids and return aggregate stats."""
        auto_bound = 0
        for requirement in requirements:
            if requirement.get("system_ids"):
                continue
            binding = self.bind_requirement(requirement)
            requirement["system_ids"] = binding["system_ids"]
            requirement["system_binding"] = binding
            requirement["binding_method"] = binding["method"]
            if binding["method"] != "already_bound":
                auto_bound += 1
        stats = self.binding_stats(requirements)
        stats["auto_bound"] = auto_bound
        return stats

    def bind_requirement(self, requirement: dict[str, Any]) -> dict[str, Any]:
        """Return binding metadata with at least one system id."""
        for method in (
            self._bind_by_dependency,
            self._bind_by_source_entity,
            self._bind_by_semantic_match,
            self._bind_by_default,
        ):
            system_ids = method(requirement)
            if system_ids:
                return {
                    "system_ids": sorted(set(system_ids)),
                    "method": method.__name__.removeprefix("_bind_by_"),
                    "confidence": 1.0 if method is self._bind_by_dependency else 0.72,
                }
        return {
            "system_ids": [DEFAULT_SYSTEM_ID],
            "method": "unknown_fallback",
            "confidence": 0.1,
        }

    def binding_stats(self, requirements: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(requirements)
        bound = sum(1 for requirement in requirements if requirement.get("system_ids"))
        return {
            "total": total,
            "bound": bound,
            "unbound": total - bound,
            "binding_rate": round(bound / total, 4) if total else 0.0,
            "system_count": len(self.systems),
        }

    def _bind_by_dependency(self, requirement: dict[str, Any]) -> list[str]:
        matched: list[str] = []
        for dep in requirement.get("dependencies", []):
            matched.extend(self.node_to_systems.get(_text(dep), []))
        entity_id = _text(requirement.get("entity_id"))
        if entity_id:
            matched.extend(self.entity_to_systems.get(entity_id, []))
        return matched

    def _bind_by_source_entity(self, requirement: dict[str, Any]) -> list[str]:
        matched: list[str] = []
        for source_ref in requirement.get("source_refs", []):
            source_text = _text(source_ref)
            for entity_source, entities in self.source_to_entities.items():
                if not source_text or source_text != entity_source:
                    continue
                for entity in entities:
                    entity_id = _text(entity.get("entity_id"))
                    matched.extend(self.entity_to_systems.get(entity_id, []))
                    matched.extend(
                        self.node_to_systems.get(_text(entity.get("node_id")), [])
                    )
        return matched

    def _bind_by_semantic_match(self, requirement: dict[str, Any]) -> list[str]:
        req_text = " ".join(
            _text(requirement.get(key))
            for key in ("requirement", "entity_label", "entity_kind", "phase")
        )
        req_tokens = _tokens(req_text)
        best_id = ""
        best_score = 0.0
        for system in self.systems:
            system_id = self._system_id(system)
            system_text = " ".join(
                _text(system.get(key))
                for key in ("system_name", "system_id", "node_id", "node_type")
            )
            system_tokens = _tokens(system_text)
            overlap = len(req_tokens & system_tokens) / max(
                min(len(req_tokens), len(system_tokens)), 1
            )
            domain_score = self._domain_score(req_tokens, system_tokens)
            score = max(
                SequenceMatcher(None, req_text.lower(), system_text.lower()).ratio(),
                overlap,
                domain_score,
            )
            if system_id and score > best_score:
                best_id = system_id
                best_score = score
        return [best_id] if best_score >= 0.35 and best_id else []

    def _bind_by_default(self, requirement: dict[str, Any]) -> list[str]:
        req_tokens = _tokens(
            " ".join(_text(requirement.get(key)) for key in ("requirement", "phase"))
        )
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if req_tokens & keywords:
                matched = self._find_systems_by_keyword(domain, keywords)
                if matched:
                    return matched
        first = self._system_id(self.systems[0]) if self.systems else ""
        return [first] if first else []

    def _find_systems_by_keyword(self, domain: str, keywords: set[str]) -> list[str]:
        matched = []
        for system in self.systems:
            system_id = self._system_id(system)
            text = " ".join(
                _text(system.get(key)).lower() for key in ("system_name", "node_id")
            )
            if system_id and (
                domain in text or any(keyword in text for keyword in keywords)
            ):
                matched.append(system_id)
        return matched

    def _domain_score(self, left: set[str], right: set[str]) -> float:
        for keywords in DOMAIN_KEYWORDS.values():
            if left & keywords and right & keywords:
                return 0.6
        return 0.0

    def _system_id(self, system: dict[str, Any]) -> str:
        return _text(system.get("system_id") or system.get("node_id"))
