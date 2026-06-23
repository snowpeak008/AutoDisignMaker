from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

from core.io import now_iso
from pipeline.step_02_design_review_freeze.helpers import extract_l5_entities


FUZZY_MATCH_MIN_SCORE = 0.4
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", re.IGNORECASE)

DOMAIN_TOKEN_GROUPS = (
    {"combat", "weapon", "attack", "hit", "damage", "战斗", "武器", "攻击", "命中", "伤害"},
    {"ability", "skill", "cooldown", "技能", "祝福", "冷却", "效果"},
    {"enemy", "boss", "encounter", "敌人", "首领", "遭遇"},
    {"room", "level", "scene", "environment", "房间", "关卡", "场景"},
    {"resource", "currency", "economy", "reward", "资源", "货币", "经济", "奖励"},
    {"ui", "hud", "menu", "feedback", "界面", "图标", "反馈", "提示"},
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(value: str) -> set[str]:
    """Return lowercase word and known domain tokens from mixed Chinese/English text."""
    lower = value.lower()
    result = {match.group(0).lower() for match in TOKEN_PATTERN.finditer(lower)}
    for group in DOMAIN_TOKEN_GROUPS:
        result.update(token for token in group if token in lower)
    return result


def _domain_group_score(left: set[str], right: set[str]) -> float:
    """Return a semantic score when two token sets share a domain group."""
    for group in DOMAIN_TOKEN_GROUPS:
        if left & group and right & group:
            return 0.6
    return 0.0


class EntityToRequirementConverter:
    """Convert design entities into implementation-level program requirements."""

    SCHEMA_ROUTES = {
        "character": "角色行为、状态和交互",
        "enemy": "敌人行为、攻击模式和生成条件",
        "weapon": "武器输入、命中、伤害和反馈",
        "ability": "技能触发、效果、冷却和组合规则",
        "room": "房间生成、遭遇配置和出口规则",
        "resource": "资源产出、消耗、存储和展示",
        "ui": "界面状态、输入反馈和信息层级",
        "scene": "场景视觉、环境交互和氛围构建",
        "config": "配置参数、数据表和平衡调整接口",
        "audio": "音效触发条件、音量控制和混音规则",
        "system": "系统初始化、事件管理和模块间通信",
        "narrative": "叙事触发条件、对话树和剧情状态",
    }
    MULTI_REQ_TEMPLATES = {
        "weapon": [
            ("input_response", "输入响应、攻击触发和手感反馈"),
            ("hit_resolution", "命中检测、伤害计算和击退效果"),
            ("visual_audio", "攻击动画、命中特效和音效触发"),
        ],
        "ability": [
            ("trigger_cooldown", "施放条件、冷却管理和资源消耗"),
            ("effect_execution", "目标选取、效果计算和状态施加"),
            ("visual_feedback", "施放动画、命中特效和 UI 图标更新"),
        ],
        "character": [
            ("attribute_init", "属性数据结构、基础值和成长曲线"),
            ("state_behavior", "状态机、行为驱动和决策逻辑"),
            ("damage_lifecycle", "受击反应、死亡处理和重生/复活逻辑"),
        ],
        "room": [
            ("generation_rules", "生成规则、遭遇配置和出口逻辑"),
            ("path_choice", "房间路径选择、状态记录和奖励承接"),
        ],
    }

    def convert(self, parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert every extracted entity into one or more requirements."""
        requirements: list[dict[str, Any]] = []
        for entity in extract_l5_entities(parsed):
            route = self._route_for(entity)
            for suffix, description in self._templates_for(entity, route):
                requirement_id = f"ENT-REQ-{len(requirements) + 1:03d}"
                label = _text(entity.get("label")) or _text(entity.get("entity_id"))
                requirements.append(
                    {
                        "id": requirement_id,
                        "requirement": f"实现 L5实体“{label}”的{description}。",
                        "entity_id": entity.get("entity_id"),
                        "entity_label": entity.get("label"),
                        "entity_kind": entity.get("kind"),
                        "entity_schema": entity.get("schema"),
                        "selection_id": entity.get("source_selection_id"),
                        "source_refs": [entity.get("source")] if entity.get("source") else [],
                        "phase": self._phase_for(entity),
                        "system_ids": [],
                        "system_binding": {},
                        "inputs": ["entity_definition", entity.get("node_id") or "design_node"],
                        "outputs": [self._output_for(entity, suffix)],
                        "dependencies": [entity.get("node_id")] if entity.get("node_id") else [],
                        "acceptance": f"实体“{label}”有可执行数据结构、运行时行为和至少一条验证路径。",
                        "trace_kind": "design_entity",
                    }
                )
        return requirements

    def _route_for(self, entity: dict[str, Any]) -> str:
        """Return the implementation route for one entity."""
        text = " ".join(_text(entity.get(key)).lower() for key in ("kind", "schema", "label"))
        for token, route in self.SCHEMA_ROUTES.items():
            if token in text:
                return route
        return "通用数据、行为和验收规则"

    def _templates_for(self, entity: dict[str, Any], route: str) -> list[tuple[str, str]]:
        """Return one or more requirement templates for an entity."""
        kind = _text(entity.get("kind")).lower()
        return self.MULTI_REQ_TEMPLATES.get(kind, [("core_behavior", route)])

    def _phase_for(self, entity: dict[str, Any]) -> str:
        """Infer the implementation phase for one requirement."""
        text = " ".join(
            _text(entity.get(key)).lower() for key in ("kind", "schema", "label", "node_id")
        )
        if any(
            token in text
            for token in ("release", "launch", "analytics", "telemetry", "发布", "上线", "埋点")
        ):
            return "launch_ops"
        if any(token in text for token in ("social", "guild", "friend", "社交", "好友", "公会")):
            return "social"
        if any(token in text for token in ("resource", "currency", "economy", "资源", "货币")):
            return "economy"
        if any(
            token in text for token in ("upgrade", "progress", "unlock", "升级", "成长", "解锁")
        ):
            return "progression"
        if any(token in text for token in ("room", "enemy", "encounter", "房间", "敌人")):
            return "content_ops"
        return "core_playable"

    def _output_for(self, entity: dict[str, Any], suffix: str = "core_behavior") -> str:
        """Return a deterministic output artifact path for one requirement."""
        schema = _text(entity.get("schema")).replace(".", "_") or "entity"
        label = _text(entity.get("label")).replace(" ", "_") or _text(entity.get("entity_id"))
        return f"{schema}/{label}.{suffix}.asset"


class SystemBinder:
    """Bind generated requirements to the closest known system."""

    def bind(
        self, requirements: list[dict[str, Any]], system_graph: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Attach system binding metadata to requirements in place."""
        nodes = [node for node in system_graph.get("nodes", []) if isinstance(node, dict)]
        for requirement in requirements:
            binding = self._best_binding(requirement, nodes)
            requirement["system_binding"] = binding
            requirement["system_ids"] = [binding["system_id"]] if binding.get("system_id") else []
        return requirements

    def _best_binding(
        self, requirement: dict[str, Any], nodes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Return the best dependency, semantic, or fuzzy binding for one requirement."""
        dependency_ids = {
            _text(item) for item in requirement.get("dependencies", []) if _text(item)
        }
        for node in nodes:
            node_id = _text(node.get("id"))
            if node_id and node_id in dependency_ids:
                return {"system_id": node_id, "confidence": 1.0, "method": "dependency_id"}
        if dependency_ids:
            return {
                "system_id": sorted(dependency_ids)[0],
                "confidence": 0.85,
                "method": "design_node_dependency",
            }
        req_text = (
            _text(requirement.get("requirement")) + " " + _text(requirement.get("entity_label"))
        )
        best_id = ""
        best_score = 0.0
        req_tokens = _tokens(req_text)
        for node in nodes:
            node_text = " ".join(_text(node.get(key)) for key in ("name", "id", "responsibility"))
            node_tokens = _tokens(node_text)
            overlap = len(req_tokens & node_tokens) / max(min(len(req_tokens), len(node_tokens)), 1)
            semantic = _domain_group_score(req_tokens, node_tokens)
            score = max(
                SequenceMatcher(None, req_text.lower(), node_text.lower()).ratio(),
                overlap,
                semantic,
            )
            if score > best_score:
                best_score = score
                best_id = _text(node.get("id"))
        if best_score >= FUZZY_MATCH_MIN_SCORE:
            return {
                "system_id": best_id,
                "confidence": round(best_score, 4),
                "method": "fuzzy_name",
            }
        return {"system_id": "", "confidence": 0.0, "method": "unmatched"}


def build_requirement_quality_report(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """Build aggregate quality metrics for generated program requirements."""
    total = len(requirements)
    bound = sum(1 for item in requirements if item.get("system_ids"))
    traced = sum(1 for item in requirements if item.get("source_refs"))
    system_counts = Counter(
        system_id
        for item in requirements
        for system_id in item.get("system_ids", [])
        if _text(system_id)
    )
    placeholders = [
        item.get("id")
        for item in requirements
        if any(
            token in _text(item.get("requirement"))
            for token in ("待定义", "待完善", "placeholder", "TODO")
        )
    ]
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "requirement_count": total,
        "system_binding_rate": round(bound / total, 4) if total else 0.0,
        "traceability_rate": round(traced / total, 4) if total else 0.0,
        "placeholder_rate": round(len(placeholders) / total, 4) if total else 0.0,
        "placeholder_requirement_ids": placeholders,
        "bound_system_count": len(system_counts),
        "average_requirements_per_bound_system": (
            round(total / len(system_counts), 4) if system_counts else 0.0
        ),
        "requirements_per_system": dict(sorted(system_counts.items())),
    }
