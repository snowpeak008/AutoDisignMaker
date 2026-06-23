"""Export design-tool data into the DevFlow Concept package format."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT, ensure_directory_exists


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict[str, Any] | list[Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_design_summary() -> dict[str, Any]:
    from core.design.data_loader import load_project_data

    data = load_project_data()
    domains = data.get("domains", [])
    if not isinstance(domains, list):
        domains = []

    domain_names: list[str] = []
    node_count = 0
    checklist_count = 0
    option_group_count = 0
    for item in domains:
        if not isinstance(item, dict):
            continue
        domain = item.get("domain", {})
        if isinstance(domain, dict):
            name = str(domain.get("name") or domain.get("id") or "").strip()
            if name:
                domain_names.append(name)
        nodes = item.get("nodes", [])
        if isinstance(nodes, list):
            node_count += len(nodes)
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                checklist = node.get("checklist", [])
                if isinstance(checklist, list):
                    checklist_count += len(checklist)
                    for entry in checklist:
                        if isinstance(entry, dict) and isinstance(entry.get("optionGroups"), list):
                            option_group_count += len(entry["optionGroups"])

    meta = data.get("_meta", {})
    raw_data_source = str(meta.get("dataSource") or "") if isinstance(meta, dict) else ""
    data_source = raw_data_source
    if raw_data_source:
        try:
            source_path = Path(raw_data_source).resolve()
            data_source = str(source_path.relative_to(PROJECT_ROOT))
        except (OSError, ValueError):
            data_source = raw_data_source
    return {
        "domain_count": len(domains),
        "domain_names": domain_names,
        "node_count": node_count,
        "checklist_count": checklist_count,
        "option_group_count": option_group_count,
        "validation_errors": len(meta.get("validationErrors", [])) if isinstance(meta, dict) else 0,
        "validation_warnings": (
            len(meta.get("validationWarnings", [])) if isinstance(meta, dict) else 0
        ),
        "data_source": data_source,
    }


def _design_entity_summary(project_state: dict[str, Any]) -> dict[str, int]:
    nodes = project_state.get("nodes") or {}
    if not isinstance(nodes, dict):
        return {"design_entity_node_count": 0, "design_entity_count": 0}
    entity_node_count = 0
    entity_count = 0
    for node_state in nodes.values():
        if not isinstance(node_state, dict):
            continue
        entities = node_state.get("designEntities", [])
        if not isinstance(entities, list) or not entities:
            continue
        entity_node_count += 1
        entity_count += sum(1 for entity in entities if isinstance(entity, dict))
    return {
        "design_entity_node_count": entity_node_count,
        "design_entity_count": entity_count,
    }


def _entity_summary_fields(entity: dict[str, Any]) -> str:
    summary_parts: list[str] = []
    for key in ("device", "mapping", "role", "behavior", "resource", "output", "trigger", "effect"):
        value = entity.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (dict, list)):
            value_text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            value_text = str(value)
        summary_parts.append(f"{key}={value_text[:120]}")
    return "；".join(summary_parts)


def _append_l5_design_entities(lines: list[str], node_id: str, node_state: dict[str, Any]) -> None:
    entities = node_state.get("designEntities", [])
    if not isinstance(entities, list) or not entities:
        return
    lines.append(f"- L5节点: {node_id}")
    lines.append(f"  目的：该具体设计节点包含 {len(entities)} 个可追踪 L5 实体。")
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        label = str(
            entity.get("label") or entity.get("id") or entity.get("kind") or "未命名实体"
        ).strip()
        kind = str(entity.get("kind") or "").strip()
        schema = str(entity.get("schema") or entity.get("schemaVersion") or "").strip()
        entity_id = str(entity.get("id") or "").strip()
        suffix = f" ({entity_id})" if entity_id and entity_id != label else ""
        lines.append(f"- L5实体: {label}{suffix}")
        purpose_parts = [
            part
            for part in (f"kind={kind}" if kind else "", f"schema={schema}" if schema else "")
            if part
        ]
        summary = _entity_summary_fields(entity)
        if summary:
            purpose_parts.append(summary)
        lines.append(f"  目的：{'；'.join(purpose_parts) or 'L5 concrete design entity'}")
        lines.append(f"  依赖：{node_id}")
        lines.append("  解锁：program_requirements、art_requirements")


def _concept_markdown_from_project_state(project_state: dict[str, Any]) -> str:
    """Step 00 — 项目愿景 + 核心体验（10-15条，电梯简报级别）。"""
    project_name = str(project_state.get("projectName") or "未命名游戏项目")
    profile = project_state.get("profile") or {}
    gameplay = project_state.get("gameplaySystems") or {}

    lines = [
        f"# {project_name} — Design Concept",
        "",
        "Generated by AutoDesignMaker D4 DevFlow handoff.",
        "",
        "## Layer 1 项目愿景",
        "Submitted / accepted",
    ]

    field_labels = {
        "targetScale": "项目规模",
        "businessModel": "商业模式",
        "platformScope": "平台范围",
        "regionScope": "地区范围",
        "socialModel": "社交模式",
        "operationModel": "运营模式",
    }
    for key, label in field_labels.items():
        value = profile.get(key)
        if value and value not in ("unknown", ""):
            lines.append(f"- {label}: {value}")
            lines.append(f"  目的：{project_name} 项目配置项。")
    target_bits = []
    if profile.get("contentRating"):
        target_bits.append(f"内容评级 {profile['contentRating']}")
    if profile.get("targetSessionBand"):
        target_bits.append(f"单局时长 {profile['targetSessionBand']}")
    if target_bits:
        lines.append(f"- 目标玩家: {'，'.join(target_bits)}")
        lines.append(f"  目的：{project_name} 的受众和游玩场景约束。")

    lines.extend(["", "## Layer 2 核心体验", "Submitted / accepted"])
    selected = gameplay.get("selected", [])
    core_loops = gameplay.get("coreLoops", {})
    if selected:
        for sid in selected[:5]:
            loop = core_loops.get(sid, "")
            lines.append(f"- 核心循环: {sid}{(' → ' + loop) if loop else ''}")
            lines.append(f"  目的：{project_name} 核心玩法循环。")
    else:
        lines.append(f"- 游戏类型: {project_name}")
        lines.append(f"  目的：待完善的游戏设计。")
        if _design_entity_summary(project_state)["design_entity_count"]:
            lines.append(
                "- 核心循环: 进入挑战 → 执行核心动作 → 处理遭遇 → 选择奖励 → 构筑成长 → 进入下一挑战"
            )
            lines.append(f"  目的：{project_name} 从 L5 实体层推导的最小可执行循环。")
            lines.append("- 压力来源: 高密度遭遇、失败成本、阶段首领和资源取舍")
            lines.append(f"  目的：{project_name} 的主要决策压力来自实体驱动的战斗和成长约束。")
            lines.append("- 奖励节奏: 每轮遭遇后给出短期奖励，并通过永久成长形成重玩动机")
            lines.append(f"  目的：{project_name} 用即时奖励和局外成长连接短期反馈与长期目标。")

    return "\n".join(lines) + "\n"


def _framework_markdown_from_project_state(project_state: dict[str, Any]) -> str:
    """Step 01 — Layer 1-2 摘要 + Layer 3 完整玩法系统图（20-40条）。"""
    project_name = str(project_state.get("projectName") or "未命名游戏项目")
    gameplay = project_state.get("gameplaySystems") or {}
    profile = project_state.get("profile") or {}

    lines = [
        f"# {project_name} — Gameplay Framework",
        "",
        "Generated by AutoDesignMaker D4 DevFlow handoff.",
        "",
    ]

    # 摘要：继承 Layer 1-2
    lines.extend(["## Layer 1 项目愿景", "Submitted / accepted"])
    for key, label in [
        ("targetScale", "项目规模"),
        ("businessModel", "商业模式"),
        ("platformScope", "平台范围"),
    ]:
        value = profile.get(key)
        if value and value not in ("unknown", ""):
            lines.append(f"- {label}: {value}")
            lines.append(f"  目的：{project_name} 项目定位。")

    lines.extend(["", "## Layer 2 核心体验", "Submitted / accepted"])
    selected = gameplay.get("selected", [])
    core_loops = gameplay.get("coreLoops", {})
    weights = gameplay.get("weights", {})
    if selected:
        loops = [core_loops.get(sid, "") for sid in selected if core_loops.get(sid)]
        if loops:
            lines.append(f"- 核心循环: {' → '.join(loops[:3])}")
            lines.append(f"  目的：{project_name} 玩法循环链路。")

    # 完整玩法系统 → Layer 3
    lines.extend(["", "## Layer 3 系统图", "Submitted / accepted"])
    if selected:
        for sid in selected:
            weight = (weights.get(sid) or {}).get("weight", "")
            loop = core_loops.get(sid, "")
            desc = f"{sid}" + (f" 占比{weight}%" if weight else "") + (f" | {loop}" if loop else "")
            lines.append(f"- system_layer: {desc}")
            lines.append(f"  目的：{project_name} 玩法系统模块。")
            lines.append(f"  解锁：gameplay_requirements")
    else:
        lines.append(f"- system_layer: {project_name} 基础玩法系统")
        lines.append(f"  目的：待定义。")

    return "\n".join(lines) + "\n"


def _design_markdown_from_project_state(project_state: dict[str, Any]) -> str:
    """Step 02 — Layer 1-3 摘要 + Layer 4 完整域决策（全量数据）。"""
    project_name = str(project_state.get("projectName") or "未命名游戏项目")
    profile = project_state.get("profile") or {}
    nodes = project_state.get("nodes") or {}
    gameplay = project_state.get("gameplaySystems") or {}

    lines = [
        f"# {project_name} — Full Design Specification",
        "",
        "Generated by AutoDesignMaker D4 DevFlow handoff.",
        "",
    ]

    # Layer 1-3 摘要
    lines.extend(["## Layer 1 项目愿景", "Submitted / accepted"])
    for key, label in [
        ("targetScale", "项目规模"),
        ("businessModel", "商业模式"),
        ("platformScope", "平台范围"),
        ("socialModel", "社交模式"),
    ]:
        value = profile.get(key)
        if value and value not in ("unknown", ""):
            lines.append(f"- {label}: {value}")
            lines.append(f"  目的：{project_name} 项目配置。")

    lines.extend(["", "## Layer 2 核心体验", "Submitted / accepted"])
    selected = gameplay.get("selected", [])
    core_loops = gameplay.get("coreLoops", {})
    for sid in selected[:8]:
        loop = core_loops.get(sid, "")
        lines.append(f"- 核心循环: {sid}" + (f" → {loop}" if loop else ""))
        lines.append(f"  目的：{project_name} 核心玩法。")

    lines.extend(["", "## Layer 3 系统图", "Submitted / accepted"])
    for sid in selected:
        lines.append(f"- system_layer: {sid}")
        lines.append(f"  目的：{project_name} 玩法系统。")

    # Layer 4：全量节点决策
    lines.extend(["", "## Layer 4 设计决策", "Submitted / accepted"])
    completed = {
        node_id: state
        for node_id, state in nodes.items()
        if isinstance(state, dict) and state.get("decisionState") in ("completed", "selected")
    }
    for node_id, state in completed.items():
        note = str(state.get("designNote") or "").strip()
        risk = str(state.get("riskNote") or "").strip()
        lines.append(f"- {node_id}: {note or '已完成'}")
        lines.append(f"  目的：{project_name} 设计决策节点。")
        if risk:
            lines.append(f"  约束：{risk}")

    # Layer 5：资源与表现
    art_keywords = {"表现", "ui", "视觉", "美术", "界面", "特效", "场景"}
    art_nodes = [
        (nid, s) for nid, s in completed.items() if any(k in nid.lower() for k in art_keywords)
    ]
    if art_nodes:
        lines.extend(["", "## Layer 5 资源图", "Submitted / accepted"])
        for node_id, state in art_nodes[:20]:
            note = str(state.get("designNote") or "").strip()
            lines.append(f"- 资源: {note or node_id}")
            lines.append(f"  目的：{project_name} 美术资源需求。")
            lines.append(f"  依赖：{node_id}")
    else:
        lines.extend(["", "## Layer 5 资源图", "Submitted / accepted"])
        lines.append(f"- 资源: {project_name} 美术资源")
        lines.append(f"  目的：{project_name} 视觉资源需求。")

        lines.extend(["", "## Layer 6 表现层", "Submitted / accepted"])
        lines.append(f"- 表现: {project_name} UI 与视觉")
        lines.append(f"  目的：{project_name} 界面与视觉表现。")

    entity_nodes = [
        (node_id, node_state)
        for node_id, node_state in nodes.items()
        if isinstance(node_state, dict)
        and isinstance(node_state.get("designEntities"), list)
        and node_state.get("designEntities")
    ]
    if entity_nodes:
        lines.extend(["", "## Layer 5 L5实体", "Submitted / accepted"])
        for node_id, node_state in entity_nodes:
            _append_l5_design_entities(lines, node_id, node_state)

    return "\n".join(lines) + "\n"


def _write_layer_package(
    package_dir,
    source_type,
    attachment_name,
    markdown_content,
    summary,
    project_state,
):
    from pathlib import Path

    attachments_dir = package_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    attachment_rel = f"attachments/{attachment_name}"
    (attachments_dir / attachment_name).write_text(markdown_content, encoding="utf-8")
    created_at = _now_iso()
    project_name = str(project_state.get("projectName") or "未命名游戏项目")
    _write_json(
        package_dir / "package_manifest.json",
        {
            "schema_version": 1,
            "project": project_name,
            "project_id": "devflow",
            "package_id": f"source:{source_type}",
            "package_type": source_type,
            "package_type_id": source_type.lower(),
            "source_id": source_type,
            "source_ids": [source_type],
            "stage": 0,
            "stage_slug": "idea_intake",
            "stage_title": "Initial Idea Intake",
            "version": 2,
            "generated_by": "autodesignmaker.export_adapter",
            "design_summary": summary,
        },
    )
    _write_json(
        package_dir / "operator_submission.json",
        {
            "schema_version": 1,
            "project": project_name,
            "step": 0,
            "slug": "idea_intake",
            "title": "Initial Idea Intake",
            "created_at": created_at,
            "approved": True,
            "notes": f"AutoDesignMaker D4 exported {source_type} package.",
            "attachments": [attachment_rel],
            "primary_attachment": attachment_rel,
            "package_type": source_type,
            "source_id": source_type,
            "source_ids": [source_type],
        },
    )
    _write_json(
        package_dir / "human_approval.json",
        {
            "schema_version": 1,
            "approved": True,
            "approved_at": created_at,
            "reviewer": "AutoDesignMaker D4",
            "source_attachment": attachment_rel,
        },
    )
    _write_json(
        package_dir / "selected_play_prototype.json",
        {
            "schema_version": 1,
            "id": f"ADM-{source_type.upper()}-001",
            "selected": True,
            "description": project_name,
            "source_attachment": attachment_rel,
        },
    )
    (package_dir / "selected_play_prototype.md").write_text(
        "# Selected Prototype\n\n" + project_name + "\n", encoding="utf-8"
    )
    (package_dir / "human_review.md").write_text("# Human Review\n\nApproved.\n", encoding="utf-8")

    (package_dir / "stage_input.md").write_text(markdown_content, encoding="utf-8")


def export_concept_package(*, target_dir: Path | None = None) -> dict[str, Any]:
    """Export three tiered source packages from the saved design state.

    Generates:
      - devflow_Concept_v2/  → Step 00 (project vision + core experience)
      - devflow_GameplayFramework_v2/ → Step 01 (gameplay systems)
      - devflow_Design_v2/  → Step 02 (full design decisions)
    """
    from core.paths import SOURCE_ARTIFACTS_DIR
    from core.design.data_loader import runtime_project_root
    from core.save import manager as save_manager
    from core.engines.execution_objects.integration import load_execution_object_store
    from core.engines.execution_objects.design_project import load_latest_design_project
    from core.design.data_loader import load_project_data
    from core.design.engine import DesignEngine

    runtime_root = runtime_project_root()
    project_state: dict[str, Any] = {}
    try:
        save_manager.ensure_current_save(runtime_root)
        store = load_execution_object_store(runtime_root)
        saved_state = load_latest_design_project(store)
        if saved_state and isinstance(saved_state, dict):
            project_state = saved_state
    except Exception:
        pass
    if not project_state:
        engine = DesignEngine(load_project_data())
        project_state = engine.empty_state()

    summary = _load_design_summary()
    summary.update(_design_entity_summary(project_state))
    base_dir = target_dir or SOURCE_ARTIFACTS_DIR

    packages = {
        "Concept": ("devflow_Concept_v2", "concept.md", _concept_markdown_from_project_state),
        "GameplayFramework": (
            "devflow_GameplayFramework_v2",
            "framework.md",
            _framework_markdown_from_project_state,
        ),
        "Design": ("devflow_Design_v2", "design.md", _design_markdown_from_project_state),
    }
    results: dict[str, str] = {}
    for source_type, (pkg_name, attach_name, generator) in packages.items():
        pkg_dir = ensure_directory_exists(base_dir / pkg_name)
        _write_layer_package(
            pkg_dir, source_type, attach_name, generator(project_state), summary, project_state
        )
        results[source_type] = str(pkg_dir)

    return {
        "package_dir": results.get("Concept", ""),
        "packages": results,
        "design_summary": summary,
    }
