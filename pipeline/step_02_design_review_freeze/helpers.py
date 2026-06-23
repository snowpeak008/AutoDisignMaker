from __future__ import annotations

from typing import Any

from core.io import now_iso


def _text(value: Any) -> str:
    return str(value or "").strip()


def _field(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _label(item: Any) -> str:
    label = _field(item, "label", "")
    if label:
        return _text(label)
    item_type = _text(_field(item, "item_type"))
    option = _text(_field(item, "option"))
    return f"{item_type}: {option}" if item_type else option


def _entity_kind_for(item: Any) -> str:
    """Infer a normalized entity kind from selection text."""
    text = (_label(item) + " " + _text(_field(item, "purpose"))).lower()
    if any(token in text for token in ("ui", "hud", "menu", "界面", "图标")):
        return "ui"
    if any(
        token in text
        for token in (
            "weapon",
            "sword",
            "blade",
            "bow",
            "gun",
            "武器",
            "剑",
            "刀",
            "弓",
            "枪",
        )
    ):
        return "weapon"
    if any(
        token in text for token in ("enemy", "boss", "monster", "敌人", "首领", "怪物")
    ):
        return "enemy"
    if any(
        token in text
        for token in ("resource", "currency", "economy", "资源", "货币", "经济")
    ):
        return "resource"
    if any(token in text for token in ("item", "loot", "drop", "物品", "道具", "掉落")):
        return "resource"
    if any(
        token in text
        for token in ("skill", "ability", "attack", "技能", "攻击", "特效")
    ):
        return "ability"
    if any(token in text for token in ("room", "level", "房间", "关卡")):
        return "room"
    if any(token in text for token in ("scene", "environment", "场景", "环境")):
        return "scene"
    if any(token in text for token in ("character", "avatar", "角色", "主角", "npc")):
        return "character"
    if any(
        token in text for token in ("audio", "sound", "music", "音频", "音效", "音乐")
    ):
        return "audio"
    if any(token in text for token in ("config", "setting", "配置", "参数")):
        return "config"
    if any(token in text for token in ("system", "loop", "玩法", "系统", "循环")):
        return "system"
    return "design_selection"


def _synthetic_entities(
    parsed: dict[str, Any], *, limit: int = 47
) -> list[dict[str, Any]]:
    """Create deterministic fallback entities from non-L5 selections."""
    candidates = [
        item
        for item in parsed.get("selections", [])
        if _text(_field(item, "item_type")) != "L5实体" and _label(item)
    ]
    entities: list[dict[str, Any]] = []
    for index, item in enumerate(candidates[:limit], 1):
        dependencies = _field(item, "dependencies", [])
        if not isinstance(dependencies, list):
            dependencies = []
        kind = _entity_kind_for(item)
        node_id = _text(_field(item, "id", f"SEL-{index:03d}"))
        entities.append(
            {
                "entity_id": f"ENT-{index:03d}",
                "label": _label(item),
                "kind": kind,
                "schema": f"inferred.{kind}.v1",
                "source": _text(_field(item, "source_ref") or _field(item, "source")),
                "source_selection_id": node_id,
                "node_id": node_id,
                "dependencies": [
                    _text(value) for value in dependencies if _text(value)
                ],
                "purpose": _text(_field(item, "purpose"))
                or "由当前设计选择生成的本地实体补全。",
                "inference": {
                    "mode": "local_selection_fallback",
                    "reason": "No explicit L5实体 selections were found.",
                },
            }
        )
    return entities


def extract_l5_entities(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract explicit L5 entities, falling back to local synthetic entities."""
    entities: list[dict[str, Any]] = []
    l5_index = 0
    for item in parsed.get("selections", []):
        if _text(_field(item, "item_type")) != "L5实体":
            continue
        l5_index += 1
        dependencies = _field(item, "dependencies", [])
        if not isinstance(dependencies, list):
            dependencies = []
        purpose = _text(_field(item, "purpose"))
        schema = ""
        kind = ""
        status = ""
        for part in purpose.replace(";", "；").split("；"):
            cleaned = part.strip()
            if cleaned.startswith("schema="):
                schema = cleaned.removeprefix("schema=").strip()
            elif cleaned.startswith("kind="):
                kind = cleaned.removeprefix("kind=").strip()
            elif cleaned.startswith("status="):
                status = cleaned.removeprefix("status=").strip()
        entity = {
            "entity_id": f"ENT-{l5_index:03d}",
            "label": _text(_field(item, "option")) or _label(item),
            "kind": kind or _entity_kind_for(item),
            "schema": schema or "unknown",
            "status": status or "precise",
            "source": _text(_field(item, "source_ref") or _field(item, "source")),
            "source_selection_id": _text(_field(item, "id", f"SEL-{l5_index:03d}")),
            "node_id": _text(dependencies[0]) if dependencies else "",
            "dependencies": [_text(value) for value in dependencies if _text(value)],
            "purpose": purpose,
        }
        entities.append(entity)
    return entities or _synthetic_entities(parsed)


def should_supplement(
    entities: list[dict[str, Any]],
    entity_coverage_rate: float,
    adapter_name: str,
) -> bool:
    """Return True when Step 02 should request AI L5 entity supplement."""
    if not adapter_name or adapter_name == "none":
        return False
    if any(_text(entity.get("status")) == "approximate" for entity in entities):
        return True
    real_l5 = [
        entity for entity in entities if not isinstance(entity.get("inference"), dict)
    ]
    return entity_coverage_rate < 0.60 and len(real_l5) < 10


def _expected_node_count(parsed: dict[str, Any], entities: list[dict[str, Any]]) -> int:
    """Return the trusted expected node count, or 0 when unavailable."""
    summary = parsed.get("design_summary")
    if isinstance(summary, dict):
        try:
            count = int(summary.get("node_count", 0))
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            return count

    for key in ("design_node_count", "expected_total", "expected_total_nodes"):
        try:
            count = int(parsed.get(key, 0))
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            return count

    if any(isinstance(entity.get("inference"), dict) for entity in entities):
        candidates = [
            item
            for item in parsed.get("selections", [])
            if _text(_field(item, "item_type")) != "L5实体" and _label(item)
        ]
        return len(candidates)

    return 0


class EntityValidator:
    """Validate extracted design entities and coverage."""

    def validate(
        self, parsed: dict[str, Any], *, supplement_adapter: Any = None
    ) -> dict[str, Any]:
        """Build the entity coverage report for Step 02."""
        entities = extract_l5_entities(parsed)
        expected_total = _expected_node_count(parsed, entities)
        pre_covered_nodes = len(
            {item["node_id"] for item in entities if item.get("node_id")}
        )
        pre_coverage_rate = (
            pre_covered_nodes / expected_total if expected_total else 0.0
        )
        supplement_meta: dict[str, Any] | None = None
        adapter_name = _text(getattr(supplement_adapter, "adapter_name", ""))
        if supplement_adapter and should_supplement(
            entities, pre_coverage_rate, adapter_name
        ):
            result = supplement_adapter.supplement(entities, parsed)
            entities = result.entities
            supplement_meta = {
                "triggered": True,
                "mode": result.mode,
                "entities_added": result.added_count,
                "entities_completed": result.completed_count,
                "cache_hit": result.cache_hit,
                "adapter": result.adapter_used,
                "fallback_used": result.fallback_used,
                "supplement_basis_samples": result.supplement_basis_samples,
            }
            if result.error:
                supplement_meta["error"] = result.error
        elif supplement_adapter:
            supplement_meta = {
                "triggered": False,
                "mode": "skipped",
                "entities_added": 0,
                "entities_completed": 0,
                "cache_hit": False,
                "adapter": adapter_name or "none",
                "fallback_used": False,
                "supplement_basis_samples": [],
            }
        concrete_nodes = sorted(
            {item["node_id"] for item in entities if item.get("node_id")}
        )
        expected_total = _expected_node_count(parsed, entities)
        missing_count = max(expected_total - len(concrete_nodes), 0)
        missing_entities = [
            {
                "node_id": f"UNMAPPED-NODE-{index:03d}",
                "reason": "No L5 entity mapped to this expected design node.",
            }
            for index in range(1, missing_count + 1)
        ]
        invalid_entities = [
            {
                "entity_id": item["entity_id"],
                "label": item["label"],
                "reason": "missing label, kind, or schema",
            }
            for item in entities
            if not item.get("label")
            or not item.get("kind")
            or item.get("schema") == "unknown"
        ]
        covered_nodes = len(concrete_nodes)
        total_nodes = expected_total
        coverage_rate = covered_nodes / total_nodes if total_nodes else 0.0
        report = {
            "schema_version": 1,
            "generated_at": now_iso(),
            "source": _text(parsed.get("source")),
            "entities": entities,
            "entity_count": len(entities),
            "concrete_node_count": total_nodes,
            "covered_concrete_nodes": covered_nodes,
            "entity_coverage_rate": round(coverage_rate, 4),
            "target_coverage_rate": 0.8,
            "missing_entities": missing_entities,
            "invalid_entities": invalid_entities,
        }
        if supplement_meta is not None:
            report["ai_supplement"] = supplement_meta
        return report


class GraphGenerator:
    """Generate entity dependency graph and cycle diagnostics."""

    def generate(
        self, system_graph: dict[str, Any], entity_report: dict[str, Any]
    ) -> dict[str, Any]:
        """Build a graph linking systems, design nodes, and entities."""
        nodes = [
            {
                "id": _text(node.get("id")),
                "name": _text(node.get("name")),
                "type": "system",
                "source": _text(node.get("source")),
            }
            for node in system_graph.get("nodes", [])
            if isinstance(node, dict) and _text(node.get("id"))
        ]
        node_ids = {node["id"] for node in nodes}
        edges = [
            {
                "from": _text(edge.get("from")),
                "to": _text(edge.get("to")),
                "relation": _text(edge.get("relation")) or "depends_on",
                "source": _text(edge.get("source")),
            }
            for edge in system_graph.get("edges", [])
            if isinstance(edge, dict)
            and _text(edge.get("from"))
            and _text(edge.get("to"))
        ]
        for entity in entity_report.get("entities", []):
            entity_id = _text(entity.get("entity_id"))
            if not entity_id:
                continue
            nodes.append(
                {
                    "id": entity_id,
                    "name": _text(entity.get("label")),
                    "type": "entity",
                    "source": _text(entity.get("source")),
                }
            )
            node_id = _text(entity.get("node_id"))
            if node_id:
                if node_id not in node_ids:
                    nodes.append(
                        {
                            "id": node_id,
                            "name": node_id,
                            "type": "design_node",
                            "source": "L5实体依赖",
                        }
                    )
                    node_ids.add(node_id)
                edges.append(
                    {
                        "from": node_id,
                        "to": entity_id,
                        "relation": "defines_entity",
                        "source": entity.get("source", ""),
                    }
                )
        cycles = self._cycles([node["id"] for node in nodes], edges)
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "nodes": nodes,
            "edges": edges,
            "cycles": cycles,
            "cycle_free": not cycles,
        }

    def _cycles(
        self, node_ids: list[str], edges: list[dict[str, Any]]
    ) -> list[list[str]]:
        """Return detected directed cycles without duplicating the closing node."""
        graph: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            graph.setdefault(_text(edge.get("from")), []).append(_text(edge.get("to")))
        visiting: set[str] = set()
        visited: set[str] = set()
        cycles: list[list[str]] = []

        def visit(node_id: str, path: list[str]) -> None:
            if node_id in visiting:
                if node_id in path:
                    cycles.append(path[path.index(node_id) :])
                return
            if node_id in visited:
                return
            visiting.add(node_id)
            for target in graph.get(node_id, []):
                visit(target, path + [target])
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in node_ids:
            visit(node_id, [node_id])
        return cycles


class PhaseClassifier:
    """Classify entities into implementation phases."""

    def classify(self, entity_report: dict[str, Any]) -> dict[str, Any]:
        """Return phase buckets for every design entity."""
        phases: dict[str, list[dict[str, Any]]] = {
            "core_playable": [],
            "progression": [],
            "economy": [],
            "content_ops": [],
            "social": [],
            "launch_ops": [],
        }
        for entity in entity_report.get("entities", []):
            phase = self._phase_for(entity)
            phases.setdefault(phase, []).append(
                {
                    "entity_id": entity.get("entity_id"),
                    "label": entity.get("label"),
                    "kind": entity.get("kind"),
                    "node_id": entity.get("node_id"),
                    "reason": "deterministic_entity_keyword_classification",
                }
            )
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "phases": phases,
        }

    def _phase_for(self, entity: dict[str, Any]) -> str:
        """Infer the implementation phase for one entity."""
        text = " ".join(
            _text(entity.get(key)).lower()
            for key in ("label", "kind", "schema", "node_id")
        )
        if any(
            token in text
            for token in (
                "release",
                "launch",
                "analytics",
                "telemetry",
                "release_build",
                "build_pipeline",
                "运营",
                "发布",
                "上线",
                "埋点",
                "数据分析",
            )
        ):
            return "launch_ops"
        if any(
            token in text
            for token in ("currency", "economy", "resource", "货币", "资源")
        ):
            return "economy"
        if any(
            token in text
            for token in ("progress", "upgrade", "unlock", "成长", "升级", "解锁")
        ):
            return "progression"
        if any(
            token in text
            for token in ("room", "enemy", "encounter", "content", "房间", "敌人")
        ):
            return "content_ops"
        if any(token in text for token in ("social", "guild", "friend", "社交")):
            return "social"
        return "core_playable"
