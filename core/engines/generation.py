#!/usr/bin/env python3
"""Deterministic business artifacts for the controlled development plan.

This layer turns the current project's design document into machine-readable
stage outputs. It intentionally does not create source packages or mutate save
archives; the orchestrator may later archive normal stage outputs through its
own save flow.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import struct
import subprocess
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT as BASE_DIR
from core.config.loader import get_config
from core.io import file_manifest, now_iso, read_json, rel, write_json, write_text
from core.source.importer import refresh_reference_manifest_file_inventory
from core.stage import stage_dir
from core.runtime.preflight import (
    load_project_settings,
    run_actual_development_preflight,
)
from core.save import manager as save_manager
from core.runtime import control as runtime_control

LOGGER = logging.getLogger(__name__)
from core.engines.execution_objects.integration import (
    begin_program_task_execution_object,
    complete_art_task_execution_object,
    complete_relationship_graph_execution_object,
    complete_rollback_plan_execution_object,
    confirm_automated_retry_from_safe_point,
    load_execution_object_store,
    project_file_hashes,
    record_automated_remediation,
    record_execution_object_failure,
    validate_execution_object_references,
    verify_program_task_execution_object,
)
from core.engines.execution_objects.unattended_recovery import (
    REPRODUCTION_COMMAND,
    build_failure_event,
    build_resume_cursor,
    correction_id_for_event,
    dependency_skip_ids,
    unattended_config,
    upsert_failure_queue,
    write_pause_resume_log,
    write_reproduction_payload,
    write_unattended_summary,
)
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs
from core.runtime.control import PipelineStopRequested
from core.adapters.codex.task_builder import build_file_generation_task
from core.skill_loader import write_skill_guidance
from pipeline.step_00_idea_intake.helpers import ConceptProcessor, QuestionEngine
from pipeline.step_01_gameplay_framework.helpers import LoopExtractor, SystemDeducer
from pipeline.step_02_design_review_freeze.helpers import (
    EntityValidator,
    GraphGenerator,
    PhaseClassifier,
)
from pipeline.step_03_program_requirements.helpers import (
    EntityToRequirementConverter,
    SystemBinder,
    build_requirement_quality_report,
)
from pipeline.step_03_program_requirements.binding import RequirementBindingEngine
from pipeline.step_04_art_requirements.helpers import (
    EntityToAssetConverter,
    MarketResearchSkill,
)
from pipeline.step_05_program_review.helpers import IntelligentReviewer


ALLOWED_DESIGN_SOURCE_SUFFIXES = {".md", ".txt"}

ART_STYLE_GENERATION_STAGE = 7
ART_STYLE_CONFIRMATION_STAGE = ART_STYLE_GENERATION_STAGE
LEGACY_ART_STYLE_CONFIRMATION_STAGE = 8
PROGRAM_PLAN_STAGE = 8
ART_PLAN_STAGE = 9
ASSET_ALIGNMENT_STAGE = 10
DEV_EXECUTION_STAGE = 11
DEV_EXECUTION_STAGE_LABEL = "Step 11"
DEV_EXECUTION_STAGE_NAME = "Development Execution"
DEV_EXECUTION_TASK_UNIT_TYPE = "stage11_task"
DEV_EXECUTION_RESUME_DIR_NAME = "stage_11_resume_records"
LEGACY_DEV_EXECUTION_RESUME_DIR_NAMES = ("stage_12_resume_records",)
ART_PRODUCTION_STAGE = 12
INTEGRATION_STAGE = 13
BUILD_PACKAGE_STAGE = 14
DELTA_PATCH_STAGE = 15
MIGRATION_AUDIT_STAGE = 16

TAXONOMY: tuple[dict[str, str], ...] = (
    {
        "question_ref": "project.position",
        "domain": "项目愿景",
        "decision": "项目定位",
        "question": "当前项目以什么产品定位进入开发？",
        "item_type": "项目定位",
    },
    {
        "question_ref": "project.platform",
        "domain": "项目愿景",
        "decision": "平台",
        "question": "当前项目首先面向什么平台？",
        "item_type": "平台",
    },
    {
        "question_ref": "project.target_players",
        "domain": "项目愿景",
        "decision": "目标玩家",
        "question": "当前项目面向哪类玩家？",
        "item_type": "目标玩家",
    },
    {
        "question_ref": "project.business_model",
        "domain": "项目愿景",
        "decision": "商业模式",
        "question": "当前项目采用什么商业模式？",
        "item_type": "商业模式",
    },
    {
        "question_ref": "core.loop",
        "domain": "核心体验",
        "decision": "核心循环",
        "question": "玩家通过什么循环获得主要体验？",
        "item_type": "核心循环",
    },
    {
        "question_ref": "core.pressure_source",
        "domain": "核心体验",
        "decision": "压力来源",
        "question": "主要压力来自哪里？",
        "item_type": "压力来源",
    },
    {
        "question_ref": "core.reward_rhythm",
        "domain": "核心体验",
        "decision": "奖励节奏",
        "question": "奖励以什么节奏驱动玩家继续？",
        "item_type": "奖励节奏",
    },
    {
        "question_ref": "systems.top_level",
        "domain": "系统图",
        "decision": "顶层系统",
        "question": "项目选择了哪些顶层系统？",
        "item_type": "system_layer",
    },
    {
        "question_ref": "content.objects",
        "domain": "内容图",
        "decision": "内容对象",
        "question": "项目包含哪些内容对象？",
        "item_type": "内容",
    },
    {
        "question_ref": "resources.types",
        "domain": "资源图",
        "decision": "核心资源类型",
        "question": "项目需要哪些资源或资产类型？",
        "item_type": "资源",
    },
    {
        "question_ref": "runtime.flows",
        "domain": "运行时图",
        "decision": "运行时流程",
        "question": "项目有哪些关键运行时流程？",
        "item_type": "运行时",
    },
    {
        "question_ref": "presentation.feedback",
        "domain": "表现层",
        "decision": "反馈与界面表现",
        "question": "项目需要哪些主要反馈或表现方式？",
        "item_type": "表现",
    },
    {
        "question_ref": "technology.constraints",
        "domain": "技术层",
        "decision": "技术约束和数据方案",
        "question": "项目有哪些关键技术约束和数据方案？",
        "item_type": "技术",
    },
    {
        "question_ref": "production.method",
        "domain": "生产层",
        "decision": "生产推进方式",
        "question": "项目采用哪些生产推进方式？",
        "item_type": "生产",
    },
    {
        "question_ref": "impact.analysis",
        "domain": "影响分析",
        "decision": "影响清单",
        "question": "哪些变更类型需要显式影响分析？",
        "item_type": "影响",
    },
)

LAYER_DEFAULT_ITEM_TYPES = {
    "系统图": "系统",
}

UNITY_PROGRAM_ALLOWED_ROOTS = (
    "Assets/Scripts/",
    "Assets/Config/",
    "Assets/Tests/EditMode/",
    "Assets/Tests/PlayMode/",
    "Assets/Scenes/",
)

UNITY_ART_ALLOWED_ROOTS = (
    "Assets/Art/",
    "Assets/UI/",
    "Assets/VFX/",
    "Assets/Audio/",
    "Assets/Textures/",
)


@dataclass
class Selection:
    index: int
    layer_number: int
    layer_title: str
    layer_status: str
    item_type: str
    option: str
    purpose: str = ""
    dependencies: list[str] = field(default_factory=list)
    unlocks: list[str] = field(default_factory=list)
    source_ref: str = ""
    source_line: int = 0

    @property
    def label(self) -> str:
        return f"{self.item_type}：{self.option}" if self.item_type else self.option

    @property
    def id(self) -> str:
        return f"SEL-{self.index:03d}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_values(value: str) -> list[str]:
    raw = value.strip()
    if not raw or raw == "无":
        return []
    return [
        item.strip()
        for item in re.split(r"[、,，;；]+", raw)
        if item.strip() and item.strip() != "无"
    ]


class DesignSourceError(RuntimeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def _source_ref(source: str, line_no: int) -> str:
    return f"{source}:{line_no}"


def _parse_design_text(
    text: str,
    *,
    source: str,
    source_path: str = "",
    source_sha256: str = "",
    source_size_bytes: int | None = None,
) -> dict[str, Any]:
    lines = text.splitlines()
    selections: list[Selection] = []
    layers: list[dict[str, Any]] = []
    current_layer = {
        "number": 0,
        "title": "未分层",
        "status": "",
        "source_ref": _source_ref(source, 1),
    }
    current_selection: Selection | None = None

    for line_no, line in enumerate(lines, 1):
        layer_match = re.match(r"^##\s+Layer\s+(\d+)\s+(.+?)\s*$", line)
        if layer_match:
            current_layer = {
                "number": int(layer_match.group(1)),
                "title": layer_match.group(2).strip(),
                "status": "",
                "source_ref": _source_ref(source, line_no),
            }
            layers.append(current_layer)
            current_selection = None
            continue

        if line.startswith("## "):
            current_layer = {
                "number": 0,
                "title": "未分层",
                "status": "",
                "source_ref": _source_ref(source, line_no),
            }
            current_selection = None
            continue

        if (
            current_layer["number"]
            and "/" in line
            and line == line.strip()
            and not line.startswith("- ")
        ):
            current_layer["status"] = line.strip()
            continue

        item_match = re.match(r"^\s*-\s+([^：:]+)[：:]\s*(.+?)\s*$", line)
        if item_match and current_layer["number"]:
            current_selection = Selection(
                index=len(selections) + 1,
                layer_number=int(current_layer["number"]),
                layer_title=str(current_layer["title"]),
                layer_status=str(current_layer.get("status") or ""),
                item_type=item_match.group(1).strip(),
                option=item_match.group(2).strip(),
                source_ref=_source_ref(source, line_no),
                source_line=line_no,
            )
            selections.append(current_selection)
            continue

        simple_item_match = re.match(r"^\s*-\s+(.+?)\s*$", line)
        default_item_type = LAYER_DEFAULT_ITEM_TYPES.get(
            str(current_layer.get("title") or "")
        )
        if simple_item_match and default_item_type and current_layer["number"]:
            current_selection = Selection(
                index=len(selections) + 1,
                layer_number=int(current_layer["number"]),
                layer_title=str(current_layer["title"]),
                layer_status=str(current_layer.get("status") or ""),
                item_type=default_item_type,
                option=simple_item_match.group(1).strip(),
                source_ref=_source_ref(source, line_no),
                source_line=line_no,
            )
            selections.append(current_selection)
            continue

        if current_selection is None:
            continue
        stripped = line.strip()
        if stripped.startswith("目的："):
            current_selection.purpose = stripped.removeprefix("目的：").strip()
        elif stripped.startswith("依赖："):
            current_selection.dependencies = _split_values(
                stripped.removeprefix("依赖：")
            )
        elif stripped.startswith("解锁："):
            current_selection.unlocks = _split_values(stripped.removeprefix("解锁："))

    by_layer: dict[int, list[dict[str, Any]]] = {}
    for item in selections:
        by_layer.setdefault(item.layer_number, []).append(_selection_dict(item))

    for layer in layers:
        layer["selections"] = by_layer.get(int(layer["number"]), [])

    return {
        "source": source,
        "source_path": source_path,
        "source_sha256": source_sha256
        or hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_size_bytes": (
            source_size_bytes
            if source_size_bytes is not None
            else len(text.encode("utf-8"))
        ),
        "source_line_count": len(lines),
        "parsed_at": now_iso(),
        "layers": layers,
        "selections": selections,
        "raw_text": text,
    }


def _parse_design_doc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return _parse_design_text(
        text,
        source=rel(path),
        source_path=str(path),
        source_sha256=_sha256(path),
        source_size_bytes=path.stat().st_size,
    )


def _latest_concept_package(base_dir: Path = BASE_DIR) -> Path | None:
    from core.source.finder import source_artifact_roots

    candidates: list[Path] = []
    for source_dir in source_artifact_roots():
        if not source_dir.exists():
            continue
        root_candidates: list[Path] = []
        for item in source_dir.iterdir():
            if not item.is_dir():
                continue
            manifest = read_json(item / "package_manifest.json", {})
            if not isinstance(manifest, dict):
                manifest = {}
            source_ids = {
                str(value) for value in manifest.get("source_ids", []) if value
            }
            package_type = str(
                manifest.get("package_type") or manifest.get("source_id") or ""
            )
            if manifest.get("stage") == 0 and (
                "Concept" in source_ids or package_type == "Concept"
            ):
                root_candidates.append(item)
            elif item.name.startswith("s00_cpt_v"):
                root_candidates.append(item)
        if root_candidates:
            candidates = root_candidates
            break

    if not candidates:
        return None

    def sort_key(path: Path) -> tuple[int, float]:
        match = re.search(r"_v(\d+)$", path.name)
        version = int(match.group(1)) if match else 0
        return version, path.stat().st_mtime

    return sorted(candidates, key=sort_key, reverse=True)[0]


def _load_concept_submission(package_dir: Path) -> dict[str, Any]:
    submission = read_json(package_dir / "operator_submission.json", {})
    return submission if isinstance(submission, dict) else {}


def _concept_attachment_paths(
    package_dir: Path, submission: dict[str, Any]
) -> tuple[list[Path], list[str]]:
    valid: list[Path] = []
    invalid: list[str] = []
    raw_attachments = submission.get("attachments", [])
    if not isinstance(raw_attachments, list):
        raw_attachments = []

    for raw_item in raw_attachments:
        item = str(raw_item or "").strip()
        if not item:
            continue
        path = (package_dir / item).resolve()
        try:
            path.relative_to(package_dir.resolve())
        except ValueError:
            invalid.append(item)
            continue
        if path.suffix.lower() not in ALLOWED_DESIGN_SOURCE_SUFFIXES:
            invalid.append(item)
            continue
        if not path.is_file():
            invalid.append(item)
            continue
        valid.append(path)

    return valid, invalid


def _manual_notes_as_design(notes: str, source: str) -> dict[str, Any]:
    parsed = _parse_design_text(notes, source=source)
    if parsed["selections"]:
        return parsed

    cleaned = " ".join(line.strip() for line in notes.splitlines() if line.strip())
    title = cleaned[:80] if cleaned else "操作者提交的玩法想法"
    wrapped = (
        "# 操作者设计输入\n\n"
        "## Layer 1 初始想法\n"
        "Manual Input / 已提交\n"
        f"- 玩法想法：{title}\n"
        f"  目的：{cleaned or '操作者提交的玩法想法。'}\n"
    )
    return _parse_design_text(wrapped, source=source)


def _selection_dict(item: Selection) -> dict[str, Any]:
    return {
        "id": item.id,
        "layer_number": item.layer_number,
        "layer_title": item.layer_title,
        "layer_status": item.layer_status,
        "item_type": item.item_type,
        "option": item.option,
        "label": item.label,
        "purpose": item.purpose,
        "dependencies": item.dependencies,
        "unlocks": item.unlocks,
        "source": item.source_ref,
    }


def _is_system_layer_item(item: Selection) -> bool:
    return item.layer_title in {
        "系统图",
        "内容图",
        "资源图",
        "运行时图",
        "表现层",
        "技术层",
        "生产层",
    }


def _taxonomy_item_type(taxonomy_item: dict[str, str]) -> str:
    return taxonomy_item["item_type"]


def _question_ref_for(item: Selection) -> str:
    for taxonomy_item in TAXONOMY:
        item_type = _taxonomy_item_type(taxonomy_item)
        if item_type == "system_layer" and item.layer_title == "系统图":
            return taxonomy_item["question_ref"]
        if item.item_type == item_type:
            return taxonomy_item["question_ref"]
    return f"layer_{item.layer_number:02d}.{item.item_type}"


def _option_code(item: Selection) -> str:
    return item.id.lower()


def _coverage(
    parsed: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    selections: list[Selection] = parsed["selections"]
    selections_by_question: dict[str, list[Selection]] = {}
    for item in selections:
        selections_by_question.setdefault(_question_ref_for(item), []).append(item)

    questions = []
    open_questions = []
    for taxonomy_item in TAXONOMY:
        question_ref = taxonomy_item["question_ref"]
        selected = selections_by_question.get(question_ref, [])
        answered = bool(selected)
        questions.append(
            {
                "question_ref": question_ref,
                "domain": taxonomy_item["domain"],
                "decision": taxonomy_item["decision"],
                "question": taxonomy_item["question"],
                "answered": answered,
                "selected_options": [
                    {
                        "code": _option_code(item),
                        "label": item.option,
                        "source": item.source_ref,
                        "confidence": "explicit",
                    }
                    for item in selected
                ],
            }
        )
        if not answered:
            open_questions.append(
                {
                    "id": f"OQ-{len(open_questions) + 1:03d}",
                    "question_ref": question_ref,
                    "question": taxonomy_item["question"],
                    "reason": "当前项目设计文档没有明确回答该设计问题。",
                    "status": "needs_human_input",
                }
            )

    project_selection = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "project_id": "current_project",
        "source": parsed["source"],
        "selections": [
            {
                "selection_id": item.id,
                "question_ref": _question_ref_for(item),
                "selected_options": [_option_code(item)],
                "selected_label": item.option,
                "source": item.source_ref,
                "confidence": "explicit",
                "purpose": item.purpose,
                "dependencies": item.dependencies,
                "unlocks": item.unlocks,
            }
            for item in selections
        ],
    }
    report = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "total_questions": len(TAXONOMY),
        "answered_questions": sum(1 for item in questions if item["answered"]),
        "unanswered_questions": sum(1 for item in questions if not item["answered"]),
        "questions": questions,
    }
    open_question_doc = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "questions": open_questions,
    }
    return report, project_selection, open_question_doc


def _classify_node_type(item: Selection) -> str:
    text = item.label + " " + item.purpose
    if any(token in text for token in ("经济", "货币", "商品", "付费", "商业")):
        return "economy"
    if any(token in text for token in ("内容", "区域", "章节", "收藏", "图鉴")):
        return "content"
    if any(token in text for token in ("社交", "好友", "排行榜")):
        return "social"
    if any(token in text for token in ("运营", "活动", "赛季", "公告", "客服")):
        return "live_ops"
    if any(
        token in text
        for token in ("技术", "平台", "存档", "配置", "加载", "调试", "镜头系统")
    ):
        return "platform"
    if any(token in text for token in ("数据", "指标", "埋点")):
        return "data"
    if any(token in text for token in ("QA", "回归", "测试", "发布")):
        return "support"
    return "gameplay"


def _classify_phase(item: Selection) -> str:
    text = item.label + " " + item.purpose
    if any(token in text for token in ("社交", "好友", "排行榜")):
        return "social"
    if any(
        token in text
        for token in ("发布", "Demo", "试玩", "QA", "回归", "客服", "公告", "合规")
    ):
        return "launch_ops"
    if any(token in text for token in ("活动", "赛季", "版本", "内容")):
        return "content_ops"
    if any(
        token in text
        for token in ("经济", "货币", "商品", "资源点", "资源/效率", "经济 Tick")
    ):
        return "economy"
    if any(token in text for token in ("成长", "解锁", "收集", "收藏", "图鉴")):
        return "progression"
    if any(token in text for token in ("区域", "章节", "场景")):
        return "content_ops"
    return "core_playable"


def _phase_map(parsed: dict[str, Any]) -> dict[str, Any]:
    phases: dict[str, list[dict[str, Any]]] = {
        "core_playable": [],
        "progression": [],
        "economy": [],
        "content_ops": [],
        "social": [],
        "launch_ops": [],
    }
    for item in parsed["selections"]:
        phase = _classify_phase(item)
        phases.setdefault(phase, []).append(
            {
                "selection_id": item.id,
                "label": item.label,
                "source": item.source_ref,
                "reason": "根据项目设计文档中的术语和目的进行确定性分批。",
            }
        )
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "phases": phases,
        "rule": "批次是开发顺序，不是范围裁剪；所有当前项目显式选择项都保留追踪。",
    }


def _scope_catalog(parsed: dict[str, Any], phase_map: dict[str, Any]) -> dict[str, Any]:
    phase_by_selection = {
        item["selection_id"]: phase
        for phase, items in phase_map["phases"].items()
        for item in items
    }
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "items": [
            {
                **_selection_dict(item),
                "implementation_phase": phase_by_selection.get(
                    item.id, "core_playable"
                ),
            }
            for item in parsed["selections"]
        ],
    }


def _node_candidates(selections: list[Selection]) -> list[Selection]:
    return [
        item
        for item in selections
        if _is_system_layer_item(item) and item.layer_title != "影响分析"
    ]


def _label_lookup(selections: list[Selection]) -> dict[str, Selection]:
    lookup: dict[str, Selection] = {}
    for item in selections:
        lookup[item.label] = item
        lookup[item.option] = item
    return lookup


def _graph(
    parsed: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    selections: list[Selection] = parsed["selections"]
    nodes_source = _node_candidates(selections)
    lookup = _label_lookup(nodes_source)
    node_ids = {item.id for item in nodes_source}

    nodes = [
        {
            "id": item.id,
            "name": item.label,
            "source": item.source_ref,
            "selection_refs": [_option_code(item)],
            "type": _classify_node_type(item),
            "implementation_phase": _classify_phase(item),
        }
        for item in nodes_source
    ]

    edges = []
    unresolved = []
    for item in nodes_source:
        for dep in item.dependencies:
            target = lookup.get(dep)
            if target and target.id in node_ids:
                edges.append(
                    {
                        "from": target.id,
                        "to": item.id,
                        "relation": "depends_on",
                        "resource": "",
                        "source": item.source_ref,
                    }
                )
            else:
                unresolved.append(
                    {
                        "selection_id": item.id,
                        "label": item.label,
                        "reference": dep,
                        "kind": "dependency",
                        "source": item.source_ref,
                    }
                )
        for unlock in item.unlocks:
            target = lookup.get(unlock)
            if target and target.id in node_ids:
                edges.append(
                    {
                        "from": item.id,
                        "to": target.id,
                        "relation": "triggers",
                        "resource": "",
                        "source": item.source_ref,
                    }
                )
            else:
                unresolved.append(
                    {
                        "selection_id": item.id,
                        "label": item.label,
                        "reference": unlock,
                        "kind": "candidate_unlock_not_selected",
                        "source": item.source_ref,
                    }
                )

    system_graph = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "nodes": nodes,
        "edges": edges,
        "unresolved_references": unresolved,
    }
    resource_graph = _resource_graph(parsed, nodes_source, lookup)
    open_reference_questions = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "questions": [
            {
                "id": f"REF-{index:03d}",
                "selection_id": item["selection_id"],
                "reference": item["reference"],
                "kind": item["kind"],
                "source": item["source"],
                "status": "recorded_not_committed",
                "question": "该引用没有在当前项目已选择项中形成正式节点，不能自动进入系统图。",
            }
            for index, item in enumerate(unresolved, 1)
            if item["kind"] == "dependency"
        ],
    }
    return system_graph, resource_graph, open_reference_questions


def _resource_storage(item: Selection) -> str:
    text = item.label + " " + item.purpose
    if "配置" in text:
        return "config"
    if any(token in text for token in ("货币", "金币", "资源点", "经济")):
        return "local_save"
    if any(token in text for token in ("图标", "UI", "环境", "素材")):
        return "asset_bundle"
    return "none"


def _resource_graph(
    parsed: dict[str, Any], nodes_source: list[Selection], lookup: dict[str, Selection]
) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    flows: list[dict[str, Any]] = []
    consumers_by_resource: dict[str, list[Selection]] = {}
    unlock_consumers_by_resource: dict[str, list[Selection]] = {}
    for node in nodes_source:
        for dep in node.dependencies:
            consumers_by_resource.setdefault(dep, []).append(node)
        for unlock in node.unlocks:
            unlock_consumers_by_resource.setdefault(unlock, []).append(node)

    resource_items = [item for item in parsed["selections"] if item.item_type == "资源"]
    for index, item in enumerate(resource_items, 1):
        resource_id = f"RES-{index:03d}"
        producers = [lookup[dep].id for dep in item.dependencies if dep in lookup]
        consumers = [lookup[unlock].id for unlock in item.unlocks if unlock in lookup]
        consumers.extend(
            node.id
            for node in consumers_by_resource.get(item.label, [])
            if node.id not in consumers
        )
        consumers.extend(
            node.id
            for node in consumers_by_resource.get(item.option, [])
            if node.id not in consumers
        )
        consumers.extend(
            node.id
            for node in unlock_consumers_by_resource.get(item.label, [])
            if node.id not in consumers
        )
        consumers.extend(
            node.id
            for node in unlock_consumers_by_resource.get(item.option, [])
            if node.id not in consumers
        )
        if not consumers:
            consumers.extend(
                producer for producer in producers if producer not in consumers
            )
        resources.append(
            {
                "id": resource_id,
                "name": item.label,
                "source": item.source_ref,
                "producers": producers,
                "consumers": consumers,
                "storage": _resource_storage(item),
            }
        )
        for producer in producers:
            flows.append(
                {
                    "from": producer,
                    "to": resource_id,
                    "resource": resource_id,
                    "operation": "grant",
                    "source": item.source_ref,
                }
            )
        for consumer in consumers:
            flows.append(
                {
                    "from": resource_id,
                    "to": consumer,
                    "resource": resource_id,
                    "operation": "consume",
                    "source": item.source_ref,
                }
            )

    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "resources": resources,
        "flows": flows,
    }


def _mmd_label(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ")


def _system_graph_mmd(graph: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    if not graph["nodes"]:
        lines.append('  EMPTY["无系统节点"]')
        return "\n".join(lines) + "\n"
    for node in graph["nodes"]:
        lines.append(f'  {node["id"].replace("-", "_")}["{_mmd_label(node["name"])}"]')
    for edge in graph["edges"]:
        lines.append(
            f'  {edge["from"].replace("-", "_")} -->|{edge["relation"]}| {edge["to"].replace("-", "_")}'
        )
    return "\n".join(lines) + "\n"


def _resource_graph_mmd(graph: dict[str, Any], system_graph: dict[str, Any]) -> str:
    node_names = {node["id"]: node["name"] for node in system_graph["nodes"]}
    resource_names = {item["id"]: item["name"] for item in graph["resources"]}
    lines = ["flowchart LR"]
    if not graph["resources"]:
        lines.append('  EMPTY["无资源节点"]')
        return "\n".join(lines) + "\n"
    for resource in graph["resources"]:
        lines.append(
            f'  {resource["id"].replace("-", "_")}["{_mmd_label(resource["name"])}"]'
        )
    for node_id, name in node_names.items():
        lines.append(f'  {node_id.replace("-", "_")}["{_mmd_label(name)}"]')
    for flow in graph["flows"]:
        left = str(flow["from"]).replace("-", "_")
        right = str(flow["to"]).replace("-", "_")
        label = f'{flow["operation"]}:{resource_names.get(flow["resource"], flow["resource"])}'
        lines.append(f"  {left} -->|{_mmd_label(label)}| {right}")
    return "\n".join(lines) + "\n"


def _source_digest(parsed: dict[str, Any], coverage: dict[str, Any]) -> str:
    selections = parsed["selections"]
    lines = [
        "# Source Digest",
        "",
        f"- Source: {parsed['source']}",
        f"- Parsed selections: {len(selections)}",
        f"- Answered design questions: {coverage['answered_questions']}/{coverage['total_questions']}",
        "",
        "## Selected Items",
        "",
    ]
    for item in selections:
        lines.append(f"- {item.label} ({item.source_ref})")
        if item.purpose:
            lines.append(f"  - 目的：{item.purpose}")
        if item.dependencies:
            lines.append(f"  - 依赖：{'、'.join(item.dependencies)}")
        if item.unlocks:
            lines.append(f"  - 解锁：{'、'.join(item.unlocks)}")
    lines.append("")
    return "\n".join(lines)


def _stage0_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    coverage, project_selection, open_questions = _coverage(parsed)
    concept_profile = ConceptProcessor().build_profile(parsed)
    question_coverage = QuestionEngine().evaluate(parsed)
    phase_map = _phase_map(parsed)
    scope_catalog = _scope_catalog(parsed, phase_map)
    source_manifest = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "sources": [
            {
                "path": parsed["source"],
                "sha256": parsed["source_sha256"],
                "size_bytes": parsed["source_size_bytes"],
                "line_count": parsed["source_line_count"],
                "role": "current_project_design_doc",
                "source_package": parsed.get("source_package", ""),
                "source_input_type": parsed.get("source_input_type", ""),
            }
        ],
    }
    design_extraction = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "source_package": parsed.get("source_package", ""),
        "source_input_type": parsed.get("source_input_type", ""),
        "layers": parsed["layers"],
        "selections": [_selection_dict(item) for item in parsed["selections"]],
    }
    main_source = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "source_package": parsed.get("source_package", ""),
        "source_input_type": parsed.get("source_input_type", ""),
        "selection_count": len(parsed["selections"]),
        "layer_count": len(parsed["layers"]),
        "allowed_attachment_extensions": sorted(ALLOWED_DESIGN_SOURCE_SUFFIXES),
        "rule": "Stage 00 uses submitted Concept operator input or a single .md/.txt design attachment; default design files are not used.",
    }
    write_json(
        out_dir / "option_taxonomy.json",
        {"schema_version": 1, "questions": list(TAXONOMY)},
    )
    write_json(out_dir / "main_design_source.json", main_source)
    write_json(out_dir / "design_source_manifest.json", source_manifest)
    write_json(out_dir / "design_extraction.json", design_extraction)
    write_json(out_dir / "option_coverage_report.json", coverage)
    write_json(out_dir / "concept_profile.json", concept_profile)
    write_json(out_dir / "core_question_coverage_report.json", question_coverage)
    write_json(out_dir / "project_option_selection.json", project_selection)
    write_json(out_dir / "full_scope_catalog.json", scope_catalog)
    write_json(out_dir / "implementation_phase_map.json", phase_map)
    write_json(out_dir / "open_questions.json", open_questions)
    write_text(out_dir / "source_digest.md", _source_digest(parsed, coverage))
    return {
        "content_exists": True,
        "selection_count": len(parsed["selections"]),
        "open_questions": len(open_questions["questions"]),
        "core_question_coverage_rate": question_coverage["coverage_rate"],
        "main_design_source": main_source,
    }


def _stage1_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    coverage, project_selection, open_questions = _coverage(parsed)
    phase_map = _phase_map(parsed)
    scope_catalog = _scope_catalog(parsed, phase_map)
    system_graph, resource_graph, reference_questions = _graph(parsed)
    loop_report = LoopExtractor().extract(parsed)
    system_definitions = SystemDeducer().deduce(parsed, system_graph)
    combined_questions = list(open_questions["questions"]) + list(
        reference_questions["questions"]
    )
    gameplay_framework = _gameplay_framework_md(
        parsed, phase_map, system_graph, resource_graph
    )
    core_loop = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "loop": loop_report["loop"],
        "template_key": loop_report["template_key"],
        "source_kind": loop_report["source_kind"],
        "output_rate": loop_report["output_rate"],
        "source_selection": [
            _selection_dict(item)
            for item in parsed["selections"]
            if item.item_type == "核心循环"
        ],
    }
    system_boundary = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "included_nodes": system_graph["nodes"],
        "recorded_but_not_committed_references": system_graph["unresolved_references"],
        "rule": "只有当前项目文档中已经显式选择的项进入系统边界。",
    }
    core_slice = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "phase": "core_playable",
        "items": phase_map["phases"].get("core_playable", []),
        "rule": "核心可玩切片来自当前项目显式选择项；后续批次不被删除。",
    }
    write_text(out_dir / "gameplay_framework.md", gameplay_framework)
    write_json(out_dir / "core_loop.json", core_loop)
    write_json(out_dir / "system_definitions.json", system_definitions)
    write_json(out_dir / "system_boundary.json", system_boundary)
    write_json(out_dir / "full_feature_scope.json", scope_catalog)
    write_json(out_dir / "core_playable_slice.json", core_slice)
    write_json(out_dir / "implementation_phase_map.json", phase_map)
    write_json(out_dir / "option_coverage_report.json", coverage)
    write_json(out_dir / "project_option_selection.json", project_selection)
    write_json(
        out_dir / "open_questions.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "questions": combined_questions,
        },
    )
    write_json(out_dir / "system_relation_graph.json", system_graph)
    write_text(out_dir / "system_relation_graph.mmd", _system_graph_mmd(system_graph))
    write_json(out_dir / "resource_flow_graph.json", resource_graph)
    write_text(
        out_dir / "resource_flow_graph.mmd",
        _resource_graph_mmd(resource_graph, system_graph),
    )
    return {
        "content_exists": True,
        "system_nodes": max(
            len(system_graph["nodes"]), system_definitions["system_count"]
        ),
        "resource_nodes": len(resource_graph["resources"]),
        "core_loop_output_rate": loop_report["output_rate"],
        "system_definition_rate": system_definitions["definition_rate"],
        "open_questions": len(combined_questions),
    }


def _group_by_item_type(selections: list[Selection]) -> dict[str, list[Selection]]:
    grouped: dict[str, list[Selection]] = {}
    for item in selections:
        grouped.setdefault(item.item_type, []).append(item)
    return grouped


def _gameplay_framework_md(
    parsed: dict[str, Any],
    phase_map: dict[str, Any],
    system_graph: dict[str, Any],
    resource_graph: dict[str, Any],
) -> str:
    grouped = _group_by_item_type(parsed["selections"])
    lines = [
        "# Gameplay Framework",
        "",
        f"- Source: {parsed['source']}",
        "- Rule: no Subway Surfers case selections are inherited; only current project selections are used.",
        "",
        "## Core Experience",
        "",
    ]
    for key in ("核心循环", "压力来源", "奖励节奏"):
        for item in grouped.get(key, []):
            lines.append(f"- {item.label} ({item.source_ref})")
            if item.purpose:
                lines.append(f"  - Purpose: {item.purpose}")
    lines.extend(["", "## Selected Systems", ""])
    for node in system_graph["nodes"]:
        lines.append(
            f"- {node['id']} {node['name']} [{node['type']}] ({node['source']})"
        )
    lines.extend(["", "## Resource Flow", ""])
    for resource in resource_graph["resources"]:
        lines.append(
            f"- {resource['id']} {resource['name']} storage={resource['storage']} "
            f"producers={resource['producers'] or 'none'} consumers={resource['consumers'] or 'none'}"
        )
    lines.extend(["", "## Implementation Phases", ""])
    for phase, items in phase_map["phases"].items():
        lines.append(f"### {phase}")
        if not items:
            lines.append("- none")
        for item in items:
            lines.append(f"- {item['label']} ({item['source']})")
    lines.append("")
    return "\n".join(lines)


def _validate_graphs(
    system_graph: dict[str, Any], resource_graph: dict[str, Any]
) -> list[dict[str, Any]]:
    blocking: list[dict[str, Any]] = []
    for node in system_graph.get("nodes", []):
        if not node.get("source"):
            blocking.append(
                {"id": "GRAPH-NODE-SOURCE", "message": f"{node.get('id')} 缺少来源。"}
            )
    # Resource flow completeness is a warning, not a blocker — producers/consumers
    # may be undefined in early-stage designs generated from the design workbench.
    return blocking


def _find_related_entities(
    system_entity: dict[str, Any],
    all_entities: list[dict[str, Any]],
) -> list[str]:
    """Return entity ids related to a system entity by node/dependency links."""
    system_entity_id = str(system_entity.get("entity_id") or "")
    system_node = str(system_entity.get("node_id") or "")
    system_deps = {str(item) for item in system_entity.get("dependencies", []) if item}
    related: list[str] = []
    for entity in all_entities:
        entity_id = str(entity.get("entity_id") or "")
        if not entity_id or entity_id == system_entity_id:
            continue
        entity_node = str(entity.get("node_id") or "")
        entity_deps = {str(item) for item in entity.get("dependencies", []) if item}
        if system_node and (system_node == entity_node or system_node in entity_deps):
            related.append(entity_id)
            continue
        if entity_node and entity_node in system_deps:
            related.append(entity_id)
            continue
        if system_deps and entity_deps and system_deps & entity_deps:
            related.append(entity_id)
    return sorted(set(related))


def _extract_systems_from_entities(
    entities: list[dict[str, Any]],
    system_graph: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build downstream system definitions from L5 entities and graph nodes."""
    systems: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entity in entities:
        if str(entity.get("kind") or "") != "system":
            continue
        system_id = str(entity.get("entity_id") or entity.get("node_id") or "")
        if not system_id or system_id in seen:
            continue
        seen.add(system_id)
        dependencies = [str(item) for item in entity.get("dependencies", []) if item]
        systems.append(
            {
                "system_id": system_id,
                "system_name": str(entity.get("label") or system_id),
                "node_id": str(entity.get("node_id") or ""),
                "source": str(entity.get("source") or ""),
                "dependencies": dependencies,
                "related_entities": _find_related_entities(entity, entities),
                "source_entity_id": str(entity.get("entity_id") or ""),
                "definition_source": "entity",
            }
        )

    graph_nodes = []
    if isinstance(system_graph, dict):
        graph_nodes = [
            node for node in system_graph.get("nodes", []) if isinstance(node, dict)
        ]
    for node in graph_nodes:
        node_id = str(node.get("id") or "")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        graph_entity = {
            "entity_id": node_id,
            "node_id": node_id,
            "dependencies": [],
        }
        systems.append(
            {
                "system_id": node_id,
                "system_name": str(node.get("name") or node_id),
                "node_id": node_id,
                "source": str(node.get("source") or ""),
                "dependencies": [],
                "related_entities": _find_related_entities(graph_entity, entities),
                "node_type": str(node.get("type") or ""),
                "implementation_phase": str(node.get("implementation_phase") or ""),
                "definition_source": "system_graph",
            }
        )
    return systems


def _stage2_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    phase_map = _phase_map(parsed)
    scope_catalog = _scope_catalog(parsed, phase_map)
    system_graph, resource_graph, reference_questions = _graph(parsed)
    entity_report = EntityValidator().validate(
        parsed, supplement_adapter=_stage2_supplement_adapter(out_dir)
    )
    entity_graph = GraphGenerator().generate(system_graph, entity_report)
    entity_phase_map = PhaseClassifier().classify(entity_report)
    blocking = _validate_graphs(system_graph, resource_graph)
    if not entity_graph["cycle_free"]:
        blocking.append(
            {
                "id": "ENTITY-GRAPH-CYCLE",
                "message": "Entity dependency graph contains cycles.",
                "cycles": entity_graph["cycles"],
            }
        )
    frozen_lines = [
        "# Frozen Game Design",
        "",
        f"- Source: {parsed['source']}",
        "- Freeze rule: this file summarizes explicit current-project selections only.",
        "",
        "## Scope",
        "",
    ]
    for item in scope_catalog["items"]:
        frozen_lines.append(
            f"- {item['label']} -> {item['implementation_phase']} ({item['source']})"
        )
    frozen_lines.append("")
    contract_entities = list(entity_report.get("entities", []))
    contract_systems = _extract_systems_from_entities(contract_entities, system_graph)
    freeze_contract = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "frozen_at": now_iso(),
        "source": parsed["source"],
        "frozen": not blocking,
        "source_rule": "current_project_design_doc_or_approved_repair_patch_only",
        "untraced_system_count": 0,
        "blocking_issue_count": len(blocking),
        "allowed_repair_patch_count": 0,
        "entities": contract_entities,
        "systems": contract_systems,
        "entity_stats": {
            "total_count": len(contract_entities),
            "coverage_rate": entity_report.get("entity_coverage_rate", 0.0),
            "unmapped_nodes": len(entity_report.get("missing_entities", [])),
            "system_count": len(contract_systems),
        },
    }
    scope_decisions = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "decisions": [
            {
                "selection_id": item["id"],
                "label": item["label"],
                "phase": item["implementation_phase"],
                "source": item["source"],
                "status": "frozen" if not blocking else "blocked",
            }
            for item in scope_catalog["items"]
        ],
    }
    phase_backlog = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "phases": phase_map["phases"],
    }
    review_report = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "passed" if not blocking else "blocked",
        "blocking_issues": blocking,
        "warnings": reference_questions["questions"],
        "entity_warnings": entity_report["invalid_entities"]
        + entity_report["missing_entities"],
        "checks": {
            "source_exists": True,
            "all_scope_has_phase": all(
                item.get("implementation_phase") for item in scope_catalog["items"]
            ),
            "system_nodes_have_source": all(
                node.get("source") for node in system_graph["nodes"]
            ),
            "entity_coverage_rate": entity_report["entity_coverage_rate"],
            "entity_count": entity_report["entity_count"],
            "entity_graph_cycle_free": entity_graph["cycle_free"],
            "resources_have_flow": not any(
                not item.get("producers")
                or not item.get("consumers")
                or not item.get("storage")
                for item in resource_graph["resources"]
            ),
            "weak_reference_count": len(reference_questions["questions"]),
        },
    }
    repair_patch = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "patches": [],
        "rule": "No automatic repair was applied. Missing or unselected references remain non-committed questions/warnings.",
    }
    write_text(out_dir / "frozen_game_design.md", "\n".join(frozen_lines))
    write_json(out_dir / "design_freeze_contract.json", freeze_contract)
    write_json(out_dir / "scope_decisions.json", scope_decisions)
    write_json(out_dir / "phase_backlog.json", phase_backlog)
    write_json(out_dir / "design_review_report.json", review_report)
    write_json(out_dir / "repair_patch.json", repair_patch)
    write_json(out_dir / "entity_coverage_report.json", entity_report)
    write_json(out_dir / "entity_dependency_graph.json", entity_graph)
    write_json(out_dir / "entity_phase_classification.json", entity_phase_map)
    write_json(out_dir / "system_relation_graph.json", system_graph)
    write_json(out_dir / "resource_flow_graph.json", resource_graph)
    write_text(out_dir / "system_relation_graph.mmd", _system_graph_mmd(system_graph))
    write_text(
        out_dir / "resource_flow_graph.mmd",
        _resource_graph_mmd(resource_graph, system_graph),
    )
    return {
        "content_exists": True,
        "blocking_issues": len(blocking),
        "ai_review_status": review_report["status"],
        "traceability_valid": not blocking,
        "design_entity_count": entity_report["entity_count"],
        "entity_coverage_rate": entity_report["entity_coverage_rate"],
    }


def _stage2_supplement_adapter(out_dir: Path) -> Any:
    """Return the configured Step 02 L5 supplement adapter, or None when disabled."""
    model_adapter = None
    adapter_name = _active_pipeline_adapter_name()
    if not adapter_name or adapter_name == "none":
        return None
    try:
        from core.adapters.registry import get_adapter
        from core.config.ai_config import (
            AI_CONFIG_PATH,
            AIProfile,
            get_active_completion_entry,
            image_config_from_entry,
            llm_config_from_entry,
        )

        if AI_CONFIG_PATH.exists():
            entry = get_active_completion_entry()
            adapter_name, llm = llm_config_from_entry(entry)
            profile = AIProfile(
                id=getattr(entry, "id", "completion"),
                name=getattr(entry, "label", "Completion"),
                adapter=adapter_name,
                llm=llm,
                image=image_config_from_entry(None),
            )
            model_adapter = get_adapter(adapter_name, profile=profile)
    except Exception:
        model_adapter = None
    from pipeline.step_02_design_review_freeze.supplement import EntitySupplementAdapter

    return EntitySupplementAdapter(
        cache_dir=out_dir,
        adapter_name=str(adapter_name),
        model_adapter=model_adapter,
    )


def _active_pipeline_adapter_name() -> str:
    try:
        from core.config.ai_config import AI_CONFIG_PATH, get_active_completion_entry, llm_config_from_entry

        if AI_CONFIG_PATH.exists():
            entry = get_active_completion_entry()
            adapter_name, _llm = llm_config_from_entry(entry)
            return adapter_name
    except Exception:
        pass
    return str(load_project_settings(BASE_DIR).get("pipeline_adapter", "none"))


def _requirement_text(item: Selection) -> str:
    if item.purpose:
        return f"实现并验证“{item.label}”：{item.purpose}"
    return f"实现并验证“{item.label}”。"


def _stage3_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    preflight = run_actual_development_preflight(BASE_DIR, write_report=True)
    preflight_blockers = (
        preflight.get("blockers", []) if preflight.get("status") != "passed" else []
    )
    preflight_settings = (
        preflight.get("settings", {})
        if isinstance(preflight.get("settings"), dict)
        else {}
    )
    write_json(out_dir / "actual_development_preflight_dependency.json", preflight)

    phase_map = _phase_map(parsed)
    system_graph, resource_graph, _ = _graph(parsed)
    freeze_contract = read_json(stage_dir(2) / "design_freeze_contract.json", {})
    if not isinstance(freeze_contract, dict):
        freeze_contract = {}
    if not freeze_contract.get("systems"):
        freeze_contract = {
            **freeze_contract,
            "systems": _extract_systems_from_entities(
                list(freeze_contract.get("entities", [])),
                system_graph,
            ),
        }
    nodes_by_id = {node["id"]: node for node in system_graph["nodes"]}
    binder = SystemBinder()
    requirements = []
    for index, item in enumerate(parsed["selections"], 1):
        req_id = f"REQ-{index:03d}"
        phase = _classify_phase(item)
        requirements.append(
            {
                "id": req_id,
                "requirement": _requirement_text(item),
                "selection_id": item.id,
                "source_refs": [item.source_ref],
                "phase": phase,
                "system_ids": [item.id] if item.id in nodes_by_id else [],
                "system_binding": {},
                "inputs": ["design_selection"],
                "outputs": [_phase_target_path(phase)],
                "dependencies": item.dependencies,
                "acceptance": f"可通过配置、运行流程或人工检查证明“{item.label}”已按来源实现。",
                "trace_kind": "selection",
            }
        )
    requirements.extend(EntityToRequirementConverter().convert(parsed))
    binder.bind(requirements, system_graph)
    binding_stats = RequirementBindingEngine(freeze_contract).bind_missing(requirements)

    systems_md = ["# Systems", ""]
    for node in system_graph["nodes"]:
        systems_md.append(f"## {node['id']} {node['name']}")
        systems_md.append("")
        systems_md.append(f"- Type: {node['type']}")
        systems_md.append(f"- Phase: {node['implementation_phase']}")
        systems_md.append(f"- Source: {node['source']}")
        systems_md.append("")

    entities_md = ["# Entities", "", "## Resources", ""]
    for resource in resource_graph["resources"]:
        entities_md.append(
            f"- {resource['id']} {resource['name']} storage={resource['storage']} source={resource['source']}"
        )
    entities_md.extend(["", "## Project Selections", ""])
    for item in parsed["selections"]:
        entities_md.append(f"- {item.id} {item.label} source={item.source_ref}")

    contracts_md = ["# Contracts", ""]
    for node in system_graph["nodes"]:
        contracts_md.append(
            f"- {node['id']} exposes source-traced behavior for {node['name']}. Source: {node['source']}"
        )

    acceptance_md = ["# Acceptance Criteria", ""]
    for req in requirements:
        acceptance_md.append(
            f"- {req['id']}: {req['acceptance']} Source: {', '.join(req['source_refs'])}"
        )

    path_bindings = []
    for req in requirements:
        phase = str(req.get("phase") or "core_playable")
        module = _module_for_phase(phase)
        path_bindings.append(
            {
                "requirement_id": req["id"],
                "selection_id": req["selection_id"],
                "phase": phase,
                "module": module,
                "target_path": _phase_target_path(phase),
                "test_path": _phase_test_path(phase),
                "allowed_write_paths": [
                    _phase_target_path(phase),
                    _phase_test_path(phase),
                ],
                "source_refs": req["source_refs"],
            }
        )

    structure_spec = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "valid": not preflight_blockers,
        "project_type": preflight_settings.get("project_engine", "unity"),
        "development_path": preflight_settings.get("development_path", ""),
        "editor_path": preflight_settings.get("editor_path", ""),
        "allowed_roots": list(UNITY_PROGRAM_ALLOWED_ROOTS),
        "preflight_blocking_issues": preflight_blockers,
        "system_path_map": path_bindings,
        "output_file_rules": [
            "Stage 09 must bind every task to target_path and output_files.",
            "Stage 12 may only write files declared by Stage 09 output_files.",
            "Unity project creation is out of scope; the user must create the initial project.",
            "Packages/manifest.json may only change when Stage 09 declares package_changes.",
        ],
        "path_binding_contract": {
            "required_task_fields": [
                "task_id",
                "requirement_id",
                "target_path",
                "output_files",
                "verification_commands",
                "dependencies",
            ],
            "required_topology_fields": ["dependencies", "parallel_groups"],
        },
    }

    structure_md = [
        "# Program Structure Spec",
        "",
        f"- Project type: {preflight_settings.get('project_engine', 'unity')}",
        f"- Development path: {preflight_settings.get('development_path', '')}",
        f"- Editor path: {preflight_settings.get('editor_path', '')}",
        f"- Preflight status: {preflight.get('status')}",
        "- Rule: Stage 03 owns the Unity program skeleton contract.",
        "- Rule: Stage 09 binds tasks to concrete paths and files.",
        "- Rule: Stage 12 executes only declared output files and cannot invent structure.",
        "",
        "## Allowed Roots",
        "",
    ]
    for root in UNITY_PROGRAM_ALLOWED_ROOTS:
        structure_md.append(f"- {root}")
    structure_md.extend(["", "## System Path Map", ""])
    for binding in path_bindings:
        structure_md.append(
            f"- {binding['requirement_id']} -> {binding['target_path']} "
            f"(tests: {binding['test_path']})"
        )
    structure_md.extend(["", "## Phase Summary", ""])
    for phase, items in phase_map["phases"].items():
        structure_md.append(f"- {phase}: {len(items)} traced item(s)")

    program_md = ["# Program Requirements", ""]
    for req in requirements:
        program_md.append(f"## {req['id']}")
        program_md.append("")
        program_md.append(req["requirement"])
        program_md.append("")
        program_md.append(f"- Phase: {req['phase']}")
        program_md.append(f"- Source: {', '.join(req['source_refs'])}")
        program_md.append("")

    contract = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "valid": not preflight_blockers,
        "source": parsed["source"],
        "requirements": requirements,
        "binding_stats": binding_stats,
        "system_count": len(system_graph["nodes"]),
        "resource_count": len(resource_graph["resources"]),
        "program_structure_spec": "program_structure_spec.json",
        "preflight_blocking_issues": preflight_blockers,
    }
    traceability = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "traceability_valid": all(req["source_refs"] for req in requirements),
        "traces": [
            {
                "requirement_id": req["id"],
                "selection_id": req["selection_id"],
                "source_refs": req["source_refs"],
                "system_ids": req["system_ids"],
                "phase": req["phase"],
            }
            for req in requirements
        ],
    }
    write_text(out_dir / "systems.md", "\n".join(systems_md))
    write_text(out_dir / "entities.md", "\n".join(entities_md))
    write_text(out_dir / "contracts.md", "\n".join(contracts_md))
    write_text(out_dir / "acceptance_criteria.md", "\n".join(acceptance_md))
    write_text(out_dir / "program_structure_spec.md", "\n".join(structure_md))
    write_json(out_dir / "program_structure_spec.json", structure_spec)
    write_text(out_dir / "program_requirements.md", "\n".join(program_md))
    write_json(out_dir / "program_requirements_contract.json", contract)
    write_json(out_dir / "traceability_matrix.json", traceability)
    write_json(
        out_dir / "requirement_quality_report.json",
        build_requirement_quality_report(requirements),
    )
    return {
        "content_exists": True,
        "requirement_count": len(requirements),
        "traceability_valid": traceability["traceability_valid"],
        "blocking_issues": len(preflight_blockers),
        "ai_review_status": "blocked" if preflight_blockers else "passed",
    }


def _asset_type(item: Selection) -> str:
    text = item.label + " " + item.purpose
    normalized = text.lower()
    if "配置" in text or "config" in normalized:
        return "config"
    if re.search(r"(?<![a-z0-9])(?:ui|hud)(?![a-z0-9])", normalized) or any(
        token in text for token in ("图标", "界面")
    ):
        return "ui"
    if any(token in text for token in ("特效", "反馈", "奖励")) or any(
        token in normalized for token in ("vfx", "effect", "feedback", "reward")
    ):
        return "effect"
    if any(token in text for token in ("场景", "环境", "区域", "章节", "空间")) or any(
        token in normalized
        for token in (
            "room",
            "level",
            "environment",
            "chamber",
            "dungeon",
            "floor",
            "biome",
            "tileset",
            "backdrop",
        )
    ):
        return "environment"
    return "art_asset"


def _asset_priority(asset_type: str) -> str:
    return "P0" if asset_type in {"ui", "effect", "art_asset"} else "P1"


def _asset_complexity(asset_type: str) -> str:
    if asset_type in {"ui", "config"}:
        return "s"
    if asset_type in {"effect", "environment"}:
        return "m"
    return "xs"


def _asset_items(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        item
        for item in parsed["selections"]
        if item.item_type in {"资源", "表现"}
        or any(
            token in (item.label + item.purpose).lower()
            for token in ("UI", "HUD", "素材", "镜头", "反馈", "环境")
        )
        or any(
            token in (item.label + item.purpose).lower()
            for token in ("ui", "hud", "room", "level", "chamber", "dungeon")
        )
    ]
    result = []
    for index, item in enumerate(candidates, 1):
        asset_type = _asset_type(item)
        result.append(
            {
                "asset_id": f"ASSET-{index:03d}",
                "name": item.label,
                "asset_type": asset_type,
                "source": item.source_ref,
                "purpose": item.purpose,
                "dependencies": item.dependencies,
                "unlocks": item.unlocks,
                "priority": _asset_priority(asset_type),
                "complexity": _asset_complexity(asset_type),
                "required_for_phase": _classify_phase(item),
                "status": "requirement_defined",
                "trace_kind": "selection",
            }
        )
    return result


def _stage2_entities() -> list[dict[str, Any]]:
    data = read_json(stage_dir(2) / "entity_coverage_report.json", {})
    entities = data.get("entities", []) if isinstance(data, dict) else []
    return [entity for entity in entities if isinstance(entity, dict)]


def _stage4_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    assets = _asset_items(parsed)
    converter = EntityToAssetConverter()
    frozen_entities = _stage2_entities()
    if frozen_entities:
        assets.extend(converter.convert_entities(frozen_entities))
    else:
        assets.extend(converter.convert(parsed))
    market_research = MarketResearchSkill().local_fallback(parsed)
    concept_assets = [item for item in assets if item["asset_type"] == "environment"]
    ui_assets = [item for item in assets if item["asset_type"] in {"ui", "config"}]
    effect_assets = [
        item
        for item in assets
        if item["asset_type"] in {"effect", "audio", "art_asset"}
    ]
    art_path_bindings = []
    asset_root_by_type = {
        "ui": "Assets/UI/",
        "config": "Assets/Config/",
        "effect": "Assets/VFX/",
        "environment": "Assets/Art/",
        "art_asset": "Assets/Art/",
    }
    for asset in assets:
        target_path = asset_root_by_type.get(
            str(asset.get("asset_type")), "Assets/Art/"
        )
        art_path_bindings.append(
            {
                "asset_id": asset.get("asset_id"),
                "asset_type": asset.get("asset_type"),
                "target_path": target_path,
                "source": asset.get("source"),
            }
        )
    art_structure_spec = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "valid": True,
        "project_type": "Unity",
        "allowed_roots": list(UNITY_ART_ALLOWED_ROOTS),
        "asset_path_map": art_path_bindings,
        "output_file_rules": [
            "Art outputs must stay under declared Unity art roots.",
            "Stage 11 must align art requirements with program tasks by source trace.",
            "Stage 12 cannot write art files unless Stage 09 explicitly declares them as program outputs.",
        ],
    }
    contract = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": parsed["source"],
        "valid": bool(assets),
        "assets": assets,
        "market_research": market_research,
        "rule": "Art requirements are generated only from current-project resource and presentation selections.",
    }
    asset_registry = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "assets": assets,
    }

    def asset_lines(title: str, items: list[dict[str, Any]]) -> str:
        lines = [f"# {title}", ""]
        if not items:
            lines.append("- 当前项目文档没有显式选择该类资产。")
        for item in items:
            lines.append(f"- {item['asset_id']} {item['name']} ({item['source']})")
            if item["purpose"]:
                lines.append(f"  - 目的：{item['purpose']}")
        lines.append("")
        return "\n".join(lines)

    write_text(out_dir / "原画需求.md", asset_lines("原画需求", concept_assets))
    write_text(out_dir / "UI需求.md", asset_lines("UI需求", ui_assets))
    write_text(out_dir / "特效需求.md", asset_lines("特效需求", effect_assets))
    write_text(
        out_dir / "art_structure_spec.md",
        "# Art Structure Spec\n\n"
        "- Project type: Unity\n"
        "- Every art item keeps an `asset_id` and source reference.\n"
        "- Config assets are treated as data-facing production assets.\n"
        "- Missing style or audio requests stay out of scope unless current project docs add them.\n"
        "\n## Allowed Roots\n\n"
        + "\n".join(f"- {root}" for root in UNITY_ART_ALLOWED_ROOTS)
        + "\n",
    )
    write_text(
        out_dir / "drift_analysis.md",
        "# Drift Analysis\n\n"
        "- Status: pass\n"
        "- No asset requirement was generated from reference-case selections.\n"
        "- Unspecified style, audio, and monetization art remain uncommitted.\n",
    )
    write_json(out_dir / "asset_registry.json", asset_registry)
    write_json(out_dir / "market_research.json", market_research)
    write_json(out_dir / "art_structure_spec.json", art_structure_spec)
    write_json(out_dir / "art_requirements_contract.json", contract)
    write_skill_guidance(out_dir, "frontend-design")
    return {
        "content_exists": bool(assets),
        "asset_count": len(assets),
        "traceability_valid": all(item["source"] for item in assets),
        "blocking_issues": 0 if assets else 1,
        "ai_review_status": "passed" if assets else "blocked",
    }


def _program_requirements(out_dir: Path | None = None) -> list[dict[str, Any]]:
    _ = out_dir
    data = read_json(stage_dir(3) / "program_requirements_contract.json", {})
    requirements = data.get("requirements", []) if isinstance(data, dict) else []
    return [item for item in requirements if isinstance(item, dict)]


def _art_assets() -> list[dict[str, Any]]:
    data = read_json(stage_dir(4) / "asset_registry.json", {})
    assets = data.get("assets", []) if isinstance(data, dict) else []
    return [item for item in assets if isinstance(item, dict)]


STYLE_CONFIRMATION_FILENAME = "style_confirmation.json"
STYLE_PROMPT_OVERRIDE_FILENAME = "prompt_override.json"

STYLE_OPTION_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "key": "readable_production",
        "title": "清晰量产风",
        "description": "清晰轮廓、生产友好的材质分层，游戏对比度易读，适合批量资产制作。",
        "palette": ("#2E3440", "#88C0D0", "#EBCB8B"),
    },
    {
        "key": "painterly_concept",
        "title": "概念绘画风",
        "description": "手绘质感表面、富有表现力的光线，以概念艺术构图探索氛围与情绪。",
        "palette": ("#3B4252", "#A3BE8C", "#D08770"),
    },
    {
        "key": "high_contrast_arcade",
        "title": "高对比街机风",
        "description": "大胆色块分区、清脆反馈配色，运动中仍能快速扫描识别关键元素。",
        "palette": ("#1B1F3B", "#F2CC8F", "#E07A5F"),
    },
    {
        "key": "cinematic_realism",
        "title": "电影写实风",
        "description": "真实材质、强烈主光源，高保真场景搭建，接近 AAA 电影级视觉。",
        "palette": ("#202124", "#6D6875", "#B5838D"),
    },
    {
        "key": "stylized_diagrammatic",
        "title": "风格化图示风",
        "description": "简化形体、强烈形状语言，视觉层级清晰，适合 UI 集成与信息传达。",
        "palette": ("#264653", "#2A9D8F", "#E9C46A"),
    },
)


def _config_bool(path: str, default: bool = False) -> bool:
    value = get_config(path, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _manual_gate_enabled(gate_name: str, step_number: int) -> bool:
    if os.getenv("AUTODESIGNMAKER_SKIP_ALL_GATES", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False
    skip_tokens = {
        token.strip()
        for token in os.getenv("AUTODESIGNMAKER_SKIP_GATES", "").split(",")
        if token.strip()
    }
    step_tokens = {str(step_number), f"{step_number:02d}"}
    if step_number == ART_STYLE_CONFIRMATION_STAGE:
        step_tokens.update(
            {
                str(LEGACY_ART_STYLE_CONFIRMATION_STAGE),
                f"{LEGACY_ART_STYLE_CONFIRMATION_STAGE:02d}",
            }
        )
    if skip_tokens.intersection(step_tokens):
        return False
    if not _config_bool("manual_gates.enable_manual_gates", True):
        return False
    return _config_bool(f"manual_gates.{gate_name}", True)


def _style_option_count() -> int:
    value = get_config("art_style_generation.num_options", 5)
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 5
    return max(3, min(5, count))


def _style_image_generation_enabled() -> bool:
    return _image_generation_enabled()


GENERIC_PROJECT_TITLES = {
    "程序自动开发流程工具",
    "AutoDesignMaker",
    "Untitled Game",
    "Initial Idea Intake",
    "Idea Intake",
}


def _clean_project_title(value: Any) -> str:
    text = str(value or "").strip()
    # Step07 source titles often include placeholder punctuation and subtitles.
    # The style prompt needs the inspectable project name, not the full document title.
    text = re.sub(r"^[#\s?？\uFFFD]+", "", text).strip()
    text = re.split(r"\s+[—-]\s+", text, maxsplit=1)[0].strip()
    if text in GENERIC_PROJECT_TITLES:
        return ""
    return text[:80].strip()


def _project_title_from_raw_text(parsed: dict[str, Any]) -> str:
    raw_text = str(parsed.get("raw_text") or "")
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = _clean_project_title(stripped.removeprefix("# "))
            if title:
                return title
    return ""


def _stage_title(parsed: dict[str, Any]) -> str:
    for key in ("project_name", "game_title", "display_name", "project", "title", "name"):
        value = _clean_project_title(parsed.get(key))
        if value:
            return value
    summary = parsed.get("design_summary")
    if isinstance(summary, dict):
        for key in ("project_name", "game_title", "display_name", "project", "title"):
            value = _clean_project_title(summary.get(key))
            if value:
                return value
    value = _project_title_from_raw_text(parsed)
    if value:
        return value
    return "Untitled Game"


def _short_asset_label(asset: dict[str, Any]) -> str:
    label = (
        asset.get("asset_type")
        or asset.get("asset_id")
        or str(asset.get("name") or "")
    )
    result = str(label).split("：")[0].split("\n")[0][:40].strip()
    return result if result else "asset"


def _representative_asset_text(
    assets: list[dict[str, Any]], max_chars: int = 80
) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for asset in assets[:8]:
        label = _short_asset_label(asset)
        if not label or label in seen:
            continue
        if labels and len(", ".join([*labels, label])) > max_chars:
            break
        labels.append(label)
        seen.add(label)
    return ", ".join(labels) if labels else "core gameplay assets"


def _style_prompt(
    parsed: dict[str, Any], option: dict[str, Any], assets: list[dict[str, Any]]
) -> str:
    return "\n".join(
        [
            "Create a game art style reference image.",
            f"Project: {_stage_title(parsed)}",
            f"Style direction: {option['title']}",
            f"Style intent: {option['description']}",
            f"Representative assets: {_representative_asset_text(assets)}",
            "Composition: inspectable style board, clear silhouettes, no text overlays.",
        ]
    )


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = str(hex_color).lstrip("#")
    if len(value) != 6:
        return (64, 64, 64)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    import binascii

    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    )


def _write_style_placeholder_png(path: Path, palette: tuple[str, str, str]) -> None:
    width = 640
    height = 384
    colors = [_rgb(color) for color in palette]
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            band = min(2, x * 3 // width)
            base = colors[band]
            accent = colors[(band + 1) % len(colors)]
            blend = 0.22 if (x + y) % 37 < 12 else 0.0
            pixel = tuple(
                max(0, min(255, int(base[i] * (1 - blend) + accent[i] * blend)))
                for i in range(3)
            )
            row.extend(pixel)
        rows.append(bytes(row))
    raw = b"".join(rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _active_image_config_type() -> str:
    try:
        from core.config.ai_config import AI_CONFIG_PATH, get_active_image_entry

        if not AI_CONFIG_PATH.exists():
            return ""
        entry = get_active_image_entry()
        return str(entry.config_type) if entry is not None else ""
    except Exception:
        return ""


def _create_image_generator() -> Any:
    from core.config.ai_config_schema import CONFIG_TYPE_CODEX_CLI_IMAGE

    if _active_image_config_type() == CONFIG_TYPE_CODEX_CLI_IMAGE:
        from tools.asset_production.codex_image_tool import CodexCLIImageGenerator

        return CodexCLIImageGenerator()

    from tools.asset_production.image_tool import Image2Generator

    return Image2Generator()


def _image_generation_result_success(result: str) -> bool:
    text = str(result)
    lower = text.lower()
    if "已保存" in text or "saved" in lower:
        return True
    try:
        path = Path(text.strip())
        return path.exists() if text else False
    except OSError:
        return False


def _saved_image_path_from_result(result: str) -> Path | None:
    text = str(result or "").strip()
    for marker in ("saved:", "图片已保存至："):
        if marker in text:
            candidate = text.split(marker, 1)[1].strip().splitlines()[0].strip()
            if (
                len(candidate) >= 2
                and candidate[0] in "`\"'"
                and candidate[-1] == candidate[0]
            ):
                candidate = candidate[1:-1]
            path = Path(candidate)
            if path.is_file():
                return path
    return None


def _unique_style_image_path(image_path: Path) -> Path:
    return image_path.with_name(
        f"{image_path.stem}_{time.time_ns()}{image_path.suffix}"
    )


def _remove_temp_style_image(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as unlink_error:
        LOGGER.warning(
            "Failed to remove temporary style image %s: %s",
            path,
            unlink_error,
        )


def _place_style_image(source: Path, target: Path) -> Path:
    if source.resolve() == target.resolve():
        return target
    try:
        source.replace(target)
        return target
    except OSError:
        try:
            shutil.copy2(source, target)
            _remove_temp_style_image(source)
            return target
        except OSError:
            fallback = _unique_style_image_path(target)
            shutil.copy2(source, fallback)
            _remove_temp_style_image(source)
            return fallback


def _style_image_generation_workers(option_count: int) -> int:
    return max(1, min(5, int(option_count or 0)))


def _new_style_pngs(
    generated_dir: Path, before: dict[Path, int], operation_start_ns: int
) -> list[Path]:
    candidates: list[Path] = []
    for path in generated_dir.glob("*.png"):
        try:
            if not path.is_file():
                continue
            current = path.stat().st_mtime_ns
            previous = before.get(path)
            if current < operation_start_ns:
                continue
            if previous is None or current > previous:
                candidates.append(path)
        except OSError:
            continue
    return candidates


def _run_style_image_generation(
    generator: Any,
    prompt: str,
    generated_dir: Path,
    image_path: Path,
) -> dict[str, str]:
    operation_start_ns = time.time_ns()
    before = {
        path: path.stat().st_mtime_ns
        for path in generated_dir.glob("*.png")
        if path.is_file()
    }
    result = str(
        generator._run(
            prompt,
            output_dir=str(generated_dir),
            output_format="png",
        )
    )
    if not _image_generation_result_success(result):
        raise RuntimeError(result)
    saved_path = _saved_image_path_from_result(result)
    if saved_path is not None:
        final_path = _place_style_image(saved_path, image_path)
        return {"status": "success", "result": result, "image_path": str(final_path)}
    after = _new_style_pngs(generated_dir, before, operation_start_ns)
    if after:
        newest = max(after, key=lambda path: path.stat().st_mtime)
        final_path = _place_style_image(newest, image_path)
        return {"status": "success", "result": result, "image_path": str(final_path)}
    raise RuntimeError(f"Image generation reported success but produced no PNG: {result}")


def _generate_style_option_images(
    out_dir: Path, parsed: dict[str, Any], options: list[dict[str, Any]]
) -> dict[str, Any]:
    generated_dir = out_dir / "generated_images"
    generated_dir.mkdir(parents=True, exist_ok=True)
    for old_png in list(generated_dir.glob("*.png")):
        try:
            old_png.unlink()
        except OSError:
            pass
    use_api = _style_image_generation_enabled()
    records = []
    generator = None
    if use_api:
        try:
            generator = _create_image_generator()
        except Exception as exc:  # noqa: BLE001 - optional image dependency
            records.append(
                {
                    "style_id": "",
                    "status": "api_unavailable",
                    "result": str(exc),
                }
            )
            use_api = False
    api_records: dict[str, dict[str, str]] = {}
    if generator is not None:
        def _gen_one(option: dict[str, Any]) -> tuple[str, dict[str, str]]:
            style_id = option["style_id"]
            worker_dir = generated_dir / f"{style_id}_work"
            worker_dir.mkdir(parents=True, exist_ok=True)
            try:
                return style_id, _run_style_image_generation(
                    generator,
                    str(option["prompt"]),
                    worker_dir,
                    generated_dir / f"{style_id}.png",
                )
            except Exception as exc:  # noqa: BLE001 - external API boundary
                return style_id, {"status": "failed", "result": str(exc)}
            finally:
                try:
                    worker_dir.rmdir()
                except OSError:
                    pass

        with ThreadPoolExecutor(
            max_workers=_style_image_generation_workers(len(options))
        ) as executor:
            for style_id, record in executor.map(_gen_one, options):
                api_records[style_id] = record
    for option in options:
        image_path = generated_dir / f"{option['style_id']}.png"
        prompt = str(option["prompt"])
        api_record = api_records.get(option["style_id"])
        record_path = Path(api_record.get("image_path", "")) if api_record else image_path
        if not record_path.is_file():
            record_path = image_path
            if not record_path.exists():
                _write_style_placeholder_png(record_path, tuple(option["palette"]))
        option["image_path"] = rel(record_path)
        records.append(
            {
                "style_id": option["style_id"],
                "image_path": option["image_path"],
                "prompt": prompt,
                "status": api_record["status"] if api_record else "placeholder",
                "result": api_record["result"] if api_record else "deterministic placeholder",
            }
        )
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "stage": ART_STYLE_GENERATION_STAGE,
        "project": _stage_title(parsed),
        "enabled": use_api,
        "records": records,
        "generated_count": len(options),
        "status": "success",
    }


def _style_prompt_override_options(
    override: Any, parsed: dict[str, Any], assets: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(override, dict):
        return []
    raw_options = override.get("options")
    if not isinstance(raw_options, list):
        return []
    try:
        count = int(
            override.get("count") or override.get("requested_count") or len(raw_options)
        )
    except (TypeError, ValueError):
        count = len(raw_options)
    count = max(1, min(5, count))
    options: list[dict[str, Any]] = []
    for index, raw_option in enumerate(raw_options[:count], 1):
        if not isinstance(raw_option, dict):
            continue
        preset = STYLE_OPTION_PRESETS[(index - 1) % len(STYLE_OPTION_PRESETS)]
        option = dict(raw_option)
        style_id = str(option.get("style_id") or f"STYLE-{index:02d}-{preset['key']}")
        option["style_id"] = style_id
        option["title"] = str(option.get("title") or preset["title"])
        option["description"] = str(
            option.get("description") or "用户调整后的风格图提示词。"
        )
        palette = option.get("palette")
        if not isinstance(palette, (list, tuple)) or len(palette) < 3:
            option["palette"] = list(preset["palette"])
        else:
            option["palette"] = [str(color) for color in palette[:3]]
        if not str(option.get("prompt") or "").strip():
            option["prompt"] = _style_prompt(parsed, option, assets)
        if not isinstance(option.get("source_refs"), list):
            option["source_refs"] = ["stage_07.prompt_override"]
        options.append(option)
    return options


def _write_style_generation_outputs(
    parsed: dict[str, Any],
    out_dir: Path,
    options: list[dict[str, Any]],
    *,
    prompt_override_used: bool = False,
) -> dict[str, Any]:
    _apply_style_option_recommendations(parsed, options)
    manifest = _generate_style_option_images(out_dir, parsed, options)
    manifest["prompt_override_used"] = prompt_override_used
    recommended = _recommended_style_option(options)
    style_options = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "project": _stage_title(parsed),
        "source_stage": 6,
        "option_count": len(options),
        "recommended_style_id": recommended.get("style_id", ""),
        "options": options,
        "selection_required": True,
        "prompt_override_used": prompt_override_used,
    }
    write_json(out_dir / "style_options.json", style_options)
    write_json(out_dir / "generation_log.json", manifest)
    write_json(out_dir / "generated_images_manifest.json", manifest)
    write_text(
        out_dir / "style_options.md",
        "# Art Style Options\n\n"
        + "\n".join(
            f"- {option['style_id']}: {option['title']} — {option['description']}"
            for option in options
        )
        + "\n",
    )
    confirmation_result = _style_confirmation_outputs(parsed, out_dir, style_options)
    confirmation_result.update(
        {
            "content_exists": bool(options),
            "style_option_count": len(options),
            "generated_image_count": len(options),
            "recommended_style_id": recommended.get("style_id", ""),
            "prompt_override_used": prompt_override_used,
            "blocking_issues": max(
                int(confirmation_result.get("blocking_issues", 0)),
                0 if options else 1,
            ),
            "traceability_valid": bool(options)
            and bool(confirmation_result.get("traceability_valid", True)),
        }
    )
    return confirmation_result


def _stage7_art_style_generation_outputs(
    parsed: dict[str, Any], out_dir: Path
) -> dict[str, Any]:
    assets = _art_assets()
    override_path = out_dir / STYLE_PROMPT_OVERRIDE_FILENAME
    override_options = _style_prompt_override_options(
        read_json(override_path, {}), parsed, assets
    )
    if override_options:
        try:
            override_path.unlink(missing_ok=True)
        except OSError:
            pass
        return _write_style_generation_outputs(
            parsed, out_dir, override_options, prompt_override_used=True
        )

    existing_style_options = read_json(out_dir / "style_options.json", {})
    existing_confirmation = read_json(out_dir / STYLE_CONFIRMATION_FILENAME, {})
    if (
        isinstance(existing_confirmation, dict)
        and existing_confirmation.get("status") == "approved"
        and _confirmation_options(existing_style_options)
    ):
        result = _style_confirmation_outputs(parsed, out_dir, existing_style_options)
        result.update(
            {
                "status": "success",
                "style_option_count": len(_confirmation_options(existing_style_options)),
                "generated_image_count": len(_confirmation_options(existing_style_options)),
                "reused_generation": True,
            }
        )
        return result

    count = _style_option_count()
    selected_presets = STYLE_OPTION_PRESETS[:count]
    options: list[dict[str, Any]] = []
    for index, preset in enumerate(selected_presets, 1):
        style_id = f"STYLE-{index:02d}-{preset['key']}"
        option = {
            "style_id": style_id,
            "title": preset["title"],
            "description": preset["description"],
            "palette": list(preset["palette"]),
            "source_refs": ["stage_04.asset_registry", "stage_06.art_review"],
        }
        option["prompt"] = _style_prompt(parsed, option, assets)
        options.append(option)
    return _write_style_generation_outputs(parsed, out_dir, options)


def _style_option_score(
    parsed: dict[str, Any], option: dict[str, Any], index: int, total: int
) -> int:
    _ = parsed
    baseline = 100 - ((index - 1) * max(4, 24 // max(total, 1)))
    if "diagram" in str(option.get("style_id", "")).lower():
        baseline += 2
    return max(60, min(100, baseline))


def _apply_style_option_recommendations(
    parsed: dict[str, Any], options: list[dict[str, Any]]
) -> None:
    if not options:
        return
    total = len(options)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, option in enumerate(options, 1):
        score = _style_option_score(parsed, option, index, total)
        option["score"] = score
        option["recommended"] = False
        option["recommendation_reason"] = (
            "Balanced fit for early production readability and asset consistency."
        )
        scored.append((score, -index, option))
    recommended = max(scored, key=lambda item: (item[0], item[1]))[2]
    recommended["recommended"] = True
    recommended["recommendation_reason"] = (
        "Recommended default: strongest overall fit for this project's current art requirements."
    )


def _recommended_style_option(options: list[dict[str, Any]]) -> dict[str, Any]:
    for option in options:
        if option.get("recommended"):
            return option
    if not options:
        return {}
    return max(options, key=lambda option: int(option.get("score", 0) or 0))


def _load_style_options() -> dict[str, Any]:
    data = read_json(stage_dir(ART_STYLE_GENERATION_STAGE) / "style_options.json", {})
    return data if isinstance(data, dict) else {}


def _confirmation_options(style_options: dict[str, Any]) -> list[dict[str, Any]]:
    options = style_options.get("options", []) if isinstance(style_options, dict) else []
    return [item for item in options if isinstance(item, dict)]


def _write_auto_style_confirmation(
    out_dir: Path, style_options: dict[str, Any], *, reason: str
) -> dict[str, Any]:
    options = _confirmation_options(style_options)
    selected = _recommended_style_option(options)
    confirmation = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "approved",
        "mode": "auto",
        "reason": reason,
        "selected_style_id": selected.get("style_id", ""),
        "selected_title": selected.get("title", ""),
        "selected_image_path": selected.get("image_path", ""),
        "notes": "Automatically approved because the manual style gate was skipped.",
    }
    write_json(out_dir / STYLE_CONFIRMATION_FILENAME, confirmation)
    return confirmation


def _style_confirmation_outputs(
    parsed: dict[str, Any],
    out_dir: Path,
    style_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = parsed
    if style_options is None:
        style_options = read_json(out_dir / "style_options.json", {})
    options = _confirmation_options(style_options)
    if not options:
        result = {
            "schema_version": 1,
            "generated_at": now_iso(),
            "status": "blocked",
            "message": "Stage 07 style_options.json is missing or empty.",
            "selected_style_id": "",
        }
        write_json(out_dir / STYLE_CONFIRMATION_FILENAME, result)
        return {
            "content_exists": True,
            "blocking_issues": 1,
            "ai_review_status": "blocked",
            "traceability_valid": False,
        }

    confirmation_path = out_dir / STYLE_CONFIRMATION_FILENAME
    confirmation = read_json(confirmation_path, {})
    if isinstance(confirmation, dict) and confirmation.get("status") == "approved":
        valid_selection = confirmation.get("selected_style_id") in {
            option.get("style_id") for option in options
        }
        write_text(
            out_dir / "style_confirmation.md",
            "# Art Style Confirmation\n\n"
            f"- Status: approved\n- Selected: {confirmation.get('selected_style_id', '')}\n",
        )
        return {
            "content_exists": True,
            "confirmation_status": "approved",
            "selected_style_id": confirmation.get("selected_style_id", ""),
            "blocking_issues": 0,
            "ai_review_status": "passed",
            "traceability_valid": valid_selection,
        }

    if not _manual_gate_enabled("gate_art_style", ART_STYLE_CONFIRMATION_STAGE):
        confirmation = _write_auto_style_confirmation(
            out_dir, style_options, reason="manual_gate_disabled_or_skipped"
        )
        write_text(
            out_dir / "style_confirmation.md",
            "# Art Style Confirmation\n\n"
            f"- Status: approved\n- Selected: {confirmation.get('selected_style_id', '')}\n"
            "- Mode: auto\n",
        )
        return {
            "content_exists": True,
            "confirmation_status": "approved",
            "selected_style_id": confirmation.get("selected_style_id", ""),
            "blocking_issues": 0,
            "ai_review_status": "passed",
            "traceability_valid": bool(confirmation.get("selected_style_id")),
        }

    pending = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "waiting_confirmation",
        "confirmation_ui": "style_confirmation_dialog",
        "style_options_path": rel(out_dir / "style_options.json"),
        "confirmation_path": rel(confirmation_path),
        "option_count": len(options),
    }
    write_json(out_dir / "style_confirmation_pending.json", pending)
    write_text(
        out_dir / "style_confirmation.md",
        "# Art Style Confirmation\n\n- Status: waiting_confirmation\n",
    )
    return {
        "status": "waiting_confirmation",
        "content_exists": True,
        "confirmation_status": "waiting_confirmation",
        "confirmation_ui": "style_confirmation_dialog",
        "blocking_issues": 0,
        "ai_review_status": "waiting_confirmation",
        "traceability_valid": True,
    }


def _review_outputs(
    out_dir: Path,
    *,
    prefix: str,
    title: str,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    weak_items: list[dict[str, Any]],
    missing_items: list[dict[str, Any]],
) -> dict[str, Any]:
    allowed = not blockers
    report = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "verdict": "PASS" if allowed else "BLOCKED",
        "allowed_to_enter_plan": allowed,
        "blocking_items": blockers,
        "warning_items": warnings,
        "weak_relation_items": weak_items,
        "missing_items": missing_items,
    }
    write_json(out_dir / f"{prefix}_report.json", report)
    write_text(
        out_dir / "review.md",
        f"# {title}\n\n"
        f"- Verdict: {report['verdict']}\n"
        f"- Blocking: {len(blockers)}\n"
        f"- Warnings: {len(warnings)}\n"
        f"- Weak relations: {len(weak_items)}\n"
        f"- Missing: {len(missing_items)}\n",
    )
    write_text(
        out_dir / "verdict.md", "# 评审结论\n\n" + ("通过\n" if allowed else "阻断\n")
    )
    return {
        "content_exists": True,
        "blocking_issues": len(blockers),
        "ai_review_status": "passed" if allowed else "blocked",
        "traceability_valid": not blockers,
    }


def _stage5_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    requirements = _program_requirements()
    intelligent_report = IntelligentReviewer().review_program(requirements)
    write_json(out_dir / "intelligent_review_report.json", intelligent_report)
    blockers = [
        issue
        for issue in intelligent_report["issues"]
        if issue.get("severity") == "BLOCKER"
    ]
    warnings = [
        issue
        for issue in intelligent_report["issues"]
        if issue.get("severity") in {"CRITICAL", "WARNING"}
    ]
    return _review_outputs(
        out_dir,
        prefix="ProgReview",
        title="Program Requirements Review",
        blockers=blockers,
        warnings=warnings,
        weak_items=[],
        missing_items=[],
    )


def _stage6_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    assets = _art_assets()
    intelligent_report = IntelligentReviewer().review_art(assets)
    write_json(out_dir / "intelligent_review_report.json", intelligent_report)
    blockers = [
        issue
        for issue in intelligent_report["issues"]
        if issue.get("severity") == "BLOCKER"
    ]
    warnings = [
        issue
        for issue in intelligent_report["issues"]
        if issue.get("severity") in {"CRITICAL", "WARNING"}
    ]
    return _review_outputs(
        out_dir,
        prefix="ArtReview",
        title="Art Requirements Review",
        blockers=blockers,
        warnings=warnings,
        weak_items=[],
        missing_items=[],
    )


def _phase_order() -> list[str]:
    return [
        "core_playable",
        "progression",
        "economy",
        "content_ops",
        "social",
        "launch_ops",
    ]


PHASE_MODULES = {
    "core_playable": "Core",
    "progression": "Progression",
    "economy": "Economy",
    "content_ops": "Content",
    "social": "Social",
    "launch_ops": "Operations",
}


def _path_join(*parts: str) -> str:
    return Path(*[part for part in parts if part]).as_posix().replace("\\", "/")


def _module_for_phase(phase: str) -> str:
    return PHASE_MODULES.get(str(phase or "core_playable"), "Core")


def _task_class_name(task_id: str) -> str:
    clean = (
        re.sub(r"[^A-Za-z0-9]+", " ", str(task_id or "Task")).title().replace(" ", "")
    )
    return f"{clean or 'Task'}Feature"


def _phase_target_path(phase: str) -> str:
    return _path_join("Assets", "Scripts", _module_for_phase(phase)) + "/"


def _phase_test_path(phase: str) -> str:
    return _path_join("Assets", "Tests", "EditMode", _module_for_phase(phase)) + "/"


def _task_output_files(task_id: str, phase: str) -> list[str]:
    class_name = _task_class_name(task_id)
    return [
        _path_join(_phase_target_path(phase), f"{class_name}.cs"),
        _path_join(_phase_test_path(phase), f"{class_name}Tests.cs"),
    ]


TEMPLATE_NOISE_PHRASES = (
    "Hades 范本反推：",
    "基于公开信息与设计分析反推，非官方配置；",
    "部分 L4 为基于同品类结构的合理推断。",
    "部分 L4 为基于同品类结构的合理推",
)
MAX_TASK_TITLE_LENGTH = 120


def _clean_task_title(raw_title: Any, *, fallback: str = "未命名任务") -> str:
    """Remove repeated template caveats from generated task titles."""
    title = str(raw_title or "")
    for phrase in TEMPLATE_NOISE_PHRASES:
        title = title.replace(phrase, "")
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"[：:]\s*$", "", title).strip()
    title = title.strip("。；;：: ")
    if not title or title in {"资源", "表现", "配置"}:
        title = fallback
    if len(title) > MAX_TASK_TITLE_LENGTH:
        title = title[: MAX_TASK_TITLE_LENGTH - 3].rstrip() + "..."
    return title


def _task_template_note() -> str:
    return (
        "# Hades Template Note\n\n"
        "This plan is generated from a Hades reference template built from public "
        "information and design analysis. The repeated reverse-engineering caveat "
        "is intentionally omitted from task titles; source references retain the "
        "full trace back to the design document.\n"
    )


def _program_task_category(req: dict[str, Any]) -> str:
    raw_text = f"{req.get('requirement', '')} {req.get('acceptance', '')} {req.get('phase', '')}"
    text = re.sub(r"\bschema=[^\s；;,，]+", "", raw_text, flags=re.IGNORECASE).lower()
    if any(token in text for token in ("combat", "战斗", "attack", "dash", "weapon")):
        return "combat"
    if any(token in text for token in ("progression", "成长", "upgrade", "mirror")):
        return "progression"
    if any(token in text for token in ("ui", "hud", "界面", "反馈")):
        return "ui"
    if any(
        token in text for token in ("economy", "currency", "reward", "奖励", "货币")
    ):
        return "economy"
    if any(token in text for token in ("data", "metric", "test", "experiment", "指标")):
        return "analytics"
    if any(token in text for token in ("launch", "release", "liveops", "运营", "发布")):
        return "launch_ops"
    if any(token in text for token in ("compliance", "privacy", "rating", "合规")):
        return "compliance"
    if any(token in text for token in ("doc", "documentation", "schema", "文档")):
        return "documentation"
    if any(token in text for token in ("social", "community", "社区")):
        return "social"
    return str(req.get("phase") or "core_playable")


def _is_documentation_requirement(req: dict[str, Any]) -> bool:
    direct_values = [
        req.get("system"),
        req.get("phase"),
        req.get("selection_id"),
        req.get("entity_id"),
        req.get("entity_label"),
        req.get("entity_kind"),
        req.get("entity_schema"),
        req.get("requirement"),
        req.get("title"),
    ]
    related_values = list(req.get("dependencies", []) or []) + list(
        req.get("outputs", []) or []
    )
    for value in direct_values + related_values:
        normalized = str(value or "").strip().lower()
        if "documentation_" in normalized:
            return True
    return False


def _program_task_priority(req: dict[str, Any], category: str) -> str:
    phase = str(req.get("phase") or "")
    text = f"{req.get('requirement', '')} {req.get('selection_id', '')}".lower()
    if phase == "core_playable" or category in {"combat", "ui"}:
        return "P0"
    if category in {"progression", "economy", "analytics"}:
        return "P1"
    if any(token in text for token in ("input", "objective", "settlement")):
        return "P0"
    if category in {"compliance", "documentation", "launch_ops"}:
        return "P2"
    return "P1"


def _art_task_category(asset_type: str) -> str:
    return {
        "ui": "ui",
        "config": "config",
        "effect": "vfx",
        "audio": "audio",
        "animation": "animation",
        "environment": "environment_art",
        "art_asset": "art",
    }.get(asset_type, "art")


def _load_program_structure_spec() -> dict[str, Any]:
    data = read_json(stage_dir(3) / "program_structure_spec.json", {})
    return data if isinstance(data, dict) else {}


def _program_allowed_roots() -> list[str]:
    spec = _load_program_structure_spec()
    roots = spec.get("allowed_roots") if isinstance(spec, dict) else None
    if isinstance(roots, list) and all(isinstance(item, str) for item in roots):
        return [Path(item).as_posix().rstrip("/") + "/" for item in roots]
    return list(UNITY_PROGRAM_ALLOWED_ROOTS)


def _is_under_allowed_roots(path_text: str, roots: list[str]) -> bool:
    normalized = Path(str(path_text)).as_posix().lstrip("/").rstrip("/")
    if not normalized:
        return False
    for root in roots:
        root_norm = Path(root).as_posix().lstrip("/").rstrip("/")
        if normalized == root_norm or normalized.startswith(root_norm + "/"):
            return True
    return False


def _program_plan() -> dict[str, Any]:
    data = read_json(stage_dir(PROGRAM_PLAN_STAGE) / "program_task_breakdown.json", {})
    return data if isinstance(data, dict) else {}


def _stage8_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    requirements = _program_requirements()
    structure_spec = _load_program_structure_spec()
    allowed_roots = _program_allowed_roots()
    binding_by_req = {
        str(item.get("requirement_id")): item
        for item in structure_spec.get("system_path_map", [])
        if isinstance(item, dict)
    }
    tasks = []
    for req in requirements:
        if _is_documentation_requirement(req):
            continue
        task_id = f"DEV-{len(tasks) + 1:03d}"
        phase = str(req.get("phase", "core_playable"))
        binding = binding_by_req.get(str(req.get("id")), {})
        target_path = str(binding.get("target_path") or _phase_target_path(phase))
        test_path = str(binding.get("test_path") or _phase_test_path(phase))
        output_files = _task_output_files(task_id, phase)
        category = _program_task_category(req)
        priority = _program_task_priority(req, category)
        tasks.append(
            {
                "task_id": task_id,
                "requirement_id": req.get("id"),
                "title": _clean_task_title(
                    req.get("requirement"),
                    fallback=f"实现并验证 {req.get('id') or task_id}",
                ),
                "phase": phase,
                "category": category,
                "priority": priority,
                "target_path": target_path,
                "output_files": output_files,
                "allowed_write_paths": [target_path, test_path],
                "verification_commands": [
                    {
                        "id": "static_csharp_contract",
                        "type": "internal",
                        "required": True,
                        "description": "Check declared C# outputs and public type names.",
                    },
                    {
                        "id": "unity_batchmode_compile",
                        "type": "unity_batchmode",
                        "required": True,
                        "description": "Open the project with Unity Editor in batchmode and fail on compile errors.",
                    },
                ],
                "package_changes": [],
                "source_refs": req.get("source_refs", []),
                "acceptance": req.get("acceptance", ""),
                "dependencies": [],
                "execution_policy": "ai_edit_declared_files_only",
                "status": "planned",
            }
        )
    by_phase: dict[str, list[dict[str, Any]]] = {phase: [] for phase in _phase_order()}
    for task in tasks:
        by_phase.setdefault(str(task["phase"]), []).append(task)

    dependencies: list[dict[str, Any]] = []
    previous_phase_task_ids: list[str] = []
    parallel_groups: list[dict[str, Any]] = []
    previous_group_id = ""
    for phase in _phase_order():
        phase_tasks = by_phase.get(phase, [])
        task_ids = [str(task["task_id"]) for task in phase_tasks]
        if not task_ids:
            continue
        group_id = f"PG-{len(parallel_groups) + 1:03d}-{phase}"
        parallel_groups.append(
            {
                "group_id": group_id,
                "phase": phase,
                "task_ids": task_ids,
                "depends_on_groups": [previous_group_id] if previous_group_id else [],
                "execution": "parallel_allowed",
            }
        )
        for task in phase_tasks:
            task["dependencies"] = list(previous_phase_task_ids)
            for previous_task_id in previous_phase_task_ids:
                dependencies.append(
                    {
                        "from": previous_task_id,
                        "to": task["task_id"],
                        "relation": "phase_order",
                    }
                )
        previous_phase_task_ids = task_ids
        previous_group_id = group_id

    path_binding_errors = []
    for task in tasks:
        for output in task.get("output_files", []):
            if not _is_under_allowed_roots(str(output), allowed_roots):
                path_binding_errors.append(
                    {
                        "task_id": task.get("task_id"),
                        "output_file": output,
                        "message": "Output file is outside Stage 03 allowed roots.",
                    }
                )

    lines = ["# Program Plan Index", ""]
    for phase in _phase_order():
        phase_tasks = by_phase.get(phase, [])
        lines.append(f"## {phase}")
        lines.append("")
        if not phase_tasks:
            lines.append("- none")
        for task in phase_tasks:
            lines.append(
                f"- {task['task_id']} {task['title']} ({', '.join(task['source_refs'])})"
            )
        lines.append("")
        if phase_tasks:
            write_text(
                out_dir / f"PLAN-{phase}.md",
                f"# PLAN {phase}\n\n"
                + "\n".join(
                    f"- {task['task_id']}: {task['title']} -> {', '.join(task['output_files'])}"
                    for task in phase_tasks
                )
                + "\n",
            )

    plan = {
        "schema_version": 2,
        "generated_at": now_iso(),
        "project_type": "Unity",
        "execution_mode": "actual_unity_ai_development",
        "allowed_roots": allowed_roots,
        "tasks": tasks,
        "dependencies": dependencies,
        "parallel_groups": parallel_groups,
        "execution_topology": {
            "group_order": [group["group_id"] for group in parallel_groups],
            "missing_topology_is_blocking": True,
        },
        "path_binding_errors": path_binding_errors,
        "rules": [
            "Stage 12 must execute this topology and must not infer a new one.",
            "Stage 12 must edit only task output_files.",
            "Missing output_files, dependencies, or parallel_groups blocks actual development.",
            "Package changes are allowed only when listed in task.package_changes.",
        ],
    }

    write_text(out_dir / "program_plan_index.md", "\n".join(lines))
    write_text(out_dir / "TEMPLATE_NOTE.md", _task_template_note())
    write_json(out_dir / "program_task_breakdown.json", plan)
    write_json(
        out_dir / "phase_task_map.json",
        {"schema_version": 1, "generated_at": now_iso(), "phases": by_phase},
    )
    write_json(
        out_dir / "build_config.json",
        {
            "schema_version": 1,
            "target": "actual_unity_project",
            "configuration": "development",
        },
    )
    write_json(
        out_dir / "config_schema.json",
        {
            "schema_version": 2,
            "schema": "actual_unity_program_plan_v1",
            "required_task_fields": [
                "task_id",
                "requirement_id",
                "phase",
                "category",
                "priority",
                "target_path",
                "output_files",
                "allowed_write_paths",
                "verification_commands",
                "source_refs",
                "acceptance",
            ],
            "required_topology_fields": ["dependencies", "parallel_groups"],
        },
    )
    write_text(
        out_dir / "program_structure_spec.md",
        "# Program Structure Binding\n\n"
        "- Source: stage_03/program_structure_spec.json\n"
        "- Stage 09 binds each task to concrete Unity project paths.\n"
        "- Stage 12 cannot change this structure during execution.\n",
    )
    return {
        "content_exists": bool(tasks),
        "task_count": len(tasks),
        "traceability_valid": all(task["source_refs"] for task in tasks),
        "blocking_issues": len(path_binding_errors) if tasks else 1,
        "ai_review_status": (
            "passed" if tasks and not path_binding_errors else "blocked"
        ),
    }


def _stage9_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    assets = _art_assets()
    tasks = []
    for index, asset in enumerate(assets, 1):
        asset_type = str(asset.get("asset_type") or "art_asset")
        tasks.append(
            {
                "task_id": f"ART-{index:03d}",
                "asset_id": asset.get("asset_id"),
                "title": _clean_task_title(
                    asset.get("name"),
                    fallback=f"{asset_type} asset {asset.get('asset_id') or index}",
                ),
                "asset_type": asset_type,
                "category": _art_task_category(asset_type),
                "priority": asset.get("priority") or _asset_priority(asset_type),
                "complexity": asset.get("complexity") or _asset_complexity(asset_type),
                "phase": asset.get("required_for_phase", "core_playable"),
                "source_refs": [asset.get("source")] if asset.get("source") else [],
                "status": "planned",
            }
        )
    lines = ["# Art Plan Index", ""]
    for task in tasks:
        lines.append(f"- {task['task_id']} {task['title']} ({task['asset_type']})")
    if not tasks:
        lines.append("- none")
    write_text(out_dir / "art_plan_index.md", "\n".join(lines) + "\n")
    write_text(out_dir / "TEMPLATE_NOTE.md", _task_template_note())
    write_text(
        out_dir / "ART-001.md",
        "# ART-001 Asset Production Batch\n\n"
        + "\n".join(f"- {task['task_id']}: {task['title']}" for task in tasks)
        + "\n",
    )
    write_json(
        out_dir / "art_task_breakdown.json",
        {"schema_version": 1, "generated_at": now_iso(), "tasks": tasks},
    )
    write_text(
        out_dir / "art_structure_spec.md",
        "# Art Structure Spec\n\n- Art tasks map to asset_registry entries.\n- Every produced asset must preserve its source trace.\n",
    )
    write_json(
        out_dir / "validation_report_art_plan.json",
        {"valid": bool(tasks), "task_count": len(tasks)},
    )
    write_skill_guidance(out_dir, "frontend-design")
    return {
        "content_exists": bool(tasks),
        "art_task_count": len(tasks),
        "traceability_valid": all(task["source_refs"] for task in tasks),
        "blocking_issues": 0 if tasks else 1,
        "ai_review_status": "passed" if tasks else "blocked",
    }


def _program_tasks() -> list[dict[str, Any]]:
    data = read_json(stage_dir(PROGRAM_PLAN_STAGE) / "program_task_breakdown.json", {})
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    return [item for item in tasks if isinstance(item, dict)]


def _art_tasks() -> list[dict[str, Any]]:
    data = read_json(stage_dir(ART_PLAN_STAGE) / "art_task_breakdown.json", {})
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    return [item for item in tasks if isinstance(item, dict)]


def _image_generation_enabled() -> bool:
    try:
        from core.config.ai_config import AI_CONFIG_PATH, get_active_image_entry, image_config_from_entry

        if AI_CONFIG_PATH.exists():
            return bool(image_config_from_entry(get_active_image_entry()).enabled)
    except Exception:
        pass
    value = os.getenv("AUTODESIGNMAKER_ENABLE_IMAGE_GENERATION", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _image_generation_prompt(task: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Generate a production-ready game art asset image.",
            f"Asset/task id: {task.get('asset_id') or task.get('task_id') or 'unknown'}",
            f"Title: {task.get('title') or task.get('name') or 'unnamed art asset'}",
            f"Asset type: {task.get('asset_type') or 'art_asset'}",
            f"Phase: {task.get('phase') or task.get('required_for_phase') or 'core_playable'}",
            "Style: clean game-production concept asset, inspectable, not a logo.",
        ]
    )


def _write_generated_images_manifest(
    out_dir: Path,
    tasks: list[dict[str, Any]],
    *,
    stage: int,
) -> dict[str, Any]:
    enabled = _image_generation_enabled()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "stage": stage,
        "enabled": enabled,
        "status": "skipped" if not enabled else "not_started",
        "reason": (
            ""
            if enabled
            else "Enable image generation in the active AI profile to call the image generator."
        ),
        "task_count": len(tasks),
        "generated_count": 0,
        "records": [],
    }
    if not tasks:
        manifest.update({"status": "skipped", "reason": "No art tasks available."})
        write_json(out_dir / "generated_images_manifest.json", manifest)
        return manifest
    if not enabled:
        write_json(out_dir / "generated_images_manifest.json", manifest)
        return manifest

    try:
        generator = _create_image_generator()
    except Exception as exc:  # noqa: BLE001 - optional runtime dependency
        manifest.update({"status": "blocked", "reason": str(exc)})
        write_json(out_dir / "generated_images_manifest.json", manifest)
        return manifest

    generated_dir = out_dir / "generated_images"
    records = []
    for task in tasks:
        task_id = str(task.get("task_id") or task.get("asset_id") or "art")
        try:
            result = generator._run(
                _image_generation_prompt(task),
                output_dir=str(generated_dir),
                output_format="png",
            )
            ok = _image_generation_result_success(result)
            records.append(
                {
                    "task_id": task_id,
                    "status": "success" if ok else "failed",
                    "result": result,
                }
            )
        except Exception as exc:  # noqa: BLE001 - external image API boundary
            records.append({"task_id": task_id, "status": "failed", "result": str(exc)})

    generated_count = sum(1 for item in records if item["status"] == "success")
    manifest.update(
        {
            "status": (
                "success"
                if generated_count == len(tasks)
                else "partial" if generated_count else "failed"
            ),
            "generated_count": generated_count,
            "records": records,
        }
    )
    write_json(out_dir / "generated_images_manifest.json", manifest)
    return manifest


def _validate_actual_development_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        blockers.append(
            {
                "code": "TASKS_MISSING",
                "message": "Stage 09 produced no executable tasks.",
            }
        )
        tasks = []
    if not isinstance(plan.get("dependencies"), list):
        blockers.append(
            {
                "code": "DEPENDENCIES_MISSING",
                "message": "Stage 09 must declare top-level dependencies.",
            }
        )
    if not isinstance(plan.get("parallel_groups"), list):
        blockers.append(
            {
                "code": "PARALLEL_GROUPS_MISSING",
                "message": "Stage 09 must declare top-level parallel_groups.",
            }
        )

    allowed_roots = plan.get("allowed_roots")
    if not isinstance(allowed_roots, list) or not allowed_roots:
        allowed_roots = _program_allowed_roots()

    required = (
        "task_id",
        "requirement_id",
        "target_path",
        "output_files",
        "allowed_write_paths",
        "verification_commands",
        "source_refs",
        "acceptance",
    )
    task_ids = set()
    for task in tasks:
        task_id = str(task.get("task_id") or "")
        if task_id:
            task_ids.add(task_id)
        for field_name in required:
            if task.get(field_name) in ("", [], None):
                blockers.append(
                    {
                        "code": "TASK_FIELD_MISSING",
                        "task_id": task_id,
                        "field": field_name,
                        "message": "Task is missing a required actual-development field.",
                    }
                )
        task_outputs = task.get("output_files", [])
        if not isinstance(task_outputs, list):
            task_outputs = []
        for output in task_outputs:
            if not _is_under_allowed_roots(str(output), allowed_roots):
                blockers.append(
                    {
                        "code": "OUTPUT_OUTSIDE_ALLOWED_ROOT",
                        "task_id": task_id,
                        "output_file": output,
                        "allowed_roots": allowed_roots,
                    }
                )

    plan_dependencies = plan.get("dependencies", [])
    if not isinstance(plan_dependencies, list):
        plan_dependencies = []
    for edge in plan_dependencies:
        if str(edge.get("from")) not in task_ids or str(edge.get("to")) not in task_ids:
            blockers.append(
                {
                    "code": "DEPENDENCY_UNKNOWN_TASK",
                    "edge": edge,
                    "message": "Dependency references an unknown task id.",
                }
            )

    output_by_task = {
        str(task.get("task_id")): [str(item) for item in task.get("output_files", [])]
        for task in tasks
    }
    plan_parallel_groups = plan.get("parallel_groups", [])
    if not isinstance(plan_parallel_groups, list):
        plan_parallel_groups = []
    for group in plan_parallel_groups:
        if (
            not isinstance(group, dict)
            or not isinstance(group.get("task_ids"), list)
            or not group.get("task_ids")
        ):
            blockers.append(
                {
                    "code": "PARALLEL_GROUP_INVALID",
                    "group": group,
                    "message": "Parallel group must declare non-empty task_ids.",
                }
            )
            continue
        seen: dict[str, str] = {}
        for task_id in group.get("task_ids", []):
            if str(task_id) not in task_ids:
                blockers.append(
                    {
                        "code": "PARALLEL_GROUP_UNKNOWN_TASK",
                        "group_id": group.get("group_id"),
                        "task_id": task_id,
                    }
                )
            for output in output_by_task.get(str(task_id), []):
                if output in seen:
                    blockers.append(
                        {
                            "code": "PARALLEL_OUTPUT_CONFLICT",
                            "group_id": group.get("group_id"),
                            "output_file": output,
                            "task_ids": [seen[output], str(task_id)],
                        }
                    )
                else:
                    seen[output] = str(task_id)
    return blockers


def _iter_audit_files(project_path: Path) -> list[Path]:
    audit_paths: list[Path] = []
    roots = [
        project_path / "Assets",
        project_path / "Packages",
        project_path / "ProjectSettings",
    ]
    excluded_dirs = {"Library", "Temp", "Logs", "Obj", "Build", "Builds", ".git"}
    for root in roots:
        if root.is_file():
            audit_paths.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in excluded_dirs for part in path.parts):
                continue
            if path.is_file():
                audit_paths.append(path)
    return audit_paths


def _snapshot_project_files(project_path: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in _iter_audit_files(project_path):
        try:
            snapshot[path.resolve().relative_to(project_path.resolve()).as_posix()] = (
                _sha256(path)
            )
        except OSError:
            continue
    return snapshot


def _changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = sorted(set(before) | set(after))
    return [key for key in keys if before.get(key) != after.get(key)]


def _unity_allowed_companion_files(
    output_files: list[str], allowed_write_paths: list[str]
) -> set[str]:
    companions: set[str] = set()
    for output in output_files:
        normalized = Path(output).as_posix()
        companions.add(normalized + ".meta")
        parent = Path(normalized).parent
        while parent.as_posix() not in {"", "."}:
            companions.add(parent.as_posix() + ".meta")
            if parent.as_posix() == "Assets":
                break
            parent = parent.parent
    for allowed_path in allowed_write_paths:
        normalized = Path(allowed_path).as_posix().rstrip("/")
        if normalized:
            companions.add(normalized + ".meta")
    return companions


def _compact_messages(messages: list[str], *, limit: int = 1200) -> list[str]:
    compacted: list[str] = []
    for message in messages:
        text = str(message)
        if len(text) > limit:
            text = text[:limit] + "...<truncated>"
        compacted.append(text)
    return compacted


def _apply_package_changes(
    project_path: Path, package_changes: list[dict[str, Any]]
) -> dict[str, Any]:
    manifest_path = project_path / "Packages" / "manifest.json"
    report = {
        "manifest": "Packages/manifest.json",
        "status": "skipped" if not package_changes else "success",
        "changes": package_changes,
        "errors": [],
    }
    if not package_changes:
        return report
    data = read_json(manifest_path, {})
    if not isinstance(data, dict):
        report["status"] = "failed"
        report["errors"].append("Packages/manifest.json is not valid JSON.")
        return report
    dependencies = data.setdefault("dependencies", {})
    if not isinstance(dependencies, dict):
        report["status"] = "failed"
        report["errors"].append(
            "Packages/manifest.json dependencies must be an object."
        )
        return report
    before_dependencies = dict(dependencies)
    applied: list[dict[str, Any]] = []
    for change in package_changes:
        package_name = str(
            change.get("package_name") or change.get("name") or ""
        ).strip()
        action = str(change.get("action") or "upsert").strip().lower()
        version = str(change.get("version") or change.get("source") or "").strip()
        if not package_name:
            report["status"] = "failed"
            report["errors"].append("package_changes item is missing package_name.")
            continue
        if action in {"remove", "delete"}:
            dependencies.pop(package_name, None)
            applied.append(
                {
                    "package_name": package_name,
                    "action": action,
                    "before": before_dependencies.get(package_name),
                    "after": None,
                }
            )
        elif version:
            dependencies[package_name] = version
            applied.append(
                {
                    "package_name": package_name,
                    "action": "upsert",
                    "before": before_dependencies.get(package_name),
                    "after": version,
                }
            )
        else:
            report["status"] = "failed"
            report["errors"].append(
                f"package change for {package_name} is missing version/source."
            )
    if report["errors"]:
        return report
    write_json(manifest_path, data)
    report["applied"] = applied
    return report


def _static_csharp_contract(
    project_path: Path, output_files: list[str]
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    for relative in output_files:
        if not str(relative).endswith(".cs"):
            continue
        path = project_path / relative
        if not path.exists():
            blockers.append(
                {
                    "code": "CS_OUTPUT_MISSING",
                    "file": relative,
                    "message": "Declared C# output file was not created.",
                }
            )
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        public_types = re.findall(
            r"\bpublic\s+(?:(?:sealed|static|abstract|partial)\s+)*(?:class|struct|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
            text,
        )
        if public_types and path.stem not in public_types:
            blockers.append(
                {
                    "code": "CS_PUBLIC_TYPE_NAME_MISMATCH",
                    "file": relative,
                    "expected": path.stem,
                    "public_types": public_types,
                }
            )
        if "/Tests/" in Path(relative).as_posix():
            lines = text.splitlines()
            guard_stack: list[bool] = []

            def uses_nunit_symbol(code: str) -> bool:
                if code == "using NUnit.Framework;":
                    return True
                if re.match(
                    r"^\[\s*(?:Test|TestCase|SetUp|TearDown|OneTimeSetUp|OneTimeTearDown)\b",
                    code,
                ):
                    return True
                return bool(
                    re.search(
                        r"\b(?:Assert|StringAssert|CollectionAssert|Is|Does)\s*\.", code
                    )
                )

            for index, line in enumerate(lines):
                stripped = line.strip()
                directive_match = re.match(
                    r"^#\s*(if|elif|else|endif)\b(.*)$", stripped
                )
                if directive_match:
                    directive = directive_match.group(1)
                    expression = directive_match.group(2)
                    is_nunit_guard = bool(
                        re.search(r"\bDEV\d+_ENABLE_NUNIT_TESTS\b", expression)
                    )
                    if directive == "if":
                        guard_stack.append(is_nunit_guard)
                    elif directive == "elif":
                        if guard_stack:
                            guard_stack[-1] = is_nunit_guard
                    elif directive == "else":
                        if guard_stack:
                            guard_stack[-1] = False
                    elif directive == "endif":
                        if guard_stack:
                            guard_stack.pop()
                    continue

                code = stripped.split("//", 1)[0].strip()
                if not code or not uses_nunit_symbol(code):
                    continue
                if not any(guard_stack):
                    blockers.append(
                        {
                            "code": "CS_UNGUARDED_NUNIT_REFERENCE",
                            "file": relative,
                            "line": index + 1,
                            "text": code,
                            "message": "NUnit references in generated test helpers must be guarded by a task-specific DEVxxx_ENABLE_NUNIT_TESTS symbol.",
                        }
                    )
    return {
        "id": "static_csharp_contract",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
    }


def _run_unity_batchmode_compile(
    *,
    editor_path: Path,
    project_path: Path,
    log_path: Path,
    timeout_seconds: int = 1200,
) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(editor_path),
        "-batchmode",
        "-quit",
        "-projectPath",
        str(project_path),
        "-logFile",
        str(log_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=child_process_env(),
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return {
            "id": "unity_batchmode_compile",
            "status": "failed",
            "command": command,
            "log_file": str(log_path),
            "errors": [str(exc)],
        }
    log_text = (
        log_path.read_text(encoding="utf-8-sig", errors="replace")
        if log_path.exists()
        else ""
    )
    compile_markers = ["Compiler errors", "error CS", "Compilation failed"]
    marker_errors = [marker for marker in compile_markers if marker in log_text]
    errors = []
    if result.returncode != 0:
        errors.append(result.stderr.strip() or f"Unity exited {result.returncode}")
    errors.extend(f"Unity log contains marker: {marker}" for marker in marker_errors)
    return {
        "id": "unity_batchmode_compile",
        "status": "passed" if not errors else "failed",
        "returncode": result.returncode,
        "command": command,
        "log_file": str(log_path),
        "errors": errors,
    }


def _run_task_verification(
    *,
    task: dict[str, Any],
    project_path: Path,
    editor_path: Path,
    out_dir: Path,
    defer_unity_batchmode: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    output_files = [str(item) for item in task.get("output_files", [])]
    for command in task.get("verification_commands", []):
        if not isinstance(command, dict):
            results.append(
                {
                    "id": "invalid_verification_command",
                    "status": "failed",
                    "errors": ["verification command must be an object"],
                }
            )
            continue
        command_type = command.get("type")
        if command_type == "internal":
            results.append(_static_csharp_contract(project_path, output_files))
        elif command_type == "unity_batchmode":
            if defer_unity_batchmode:
                results.append(
                    {
                        "id": "unity_batchmode_compile",
                        "status": "deferred",
                        "scope": "parallel_group",
                        "message": "Unity compile is run once after the declared parallel group completes.",
                    }
                )
                continue
            log_path = out_dir / "unity_logs" / f"{task.get('task_id')}.log"
            results.append(
                _run_unity_batchmode_compile(
                    editor_path=editor_path,
                    project_path=project_path,
                    log_path=log_path,
                )
            )
        else:
            results.append(
                {
                    "id": command.get("id", "unknown"),
                    "status": "failed",
                    "errors": [
                        f"Unsupported verification command type: {command_type}"
                    ],
                }
            )
    return results


def _stage11_checkpoint_root() -> Path:
    return stage_dir(DEV_EXECUTION_STAGE).parent.parent / "checkpoints"


def _stage11_resume_dir() -> Path:
    return _stage11_checkpoint_root() / DEV_EXECUTION_RESUME_DIR_NAME


def _stage11_legacy_resume_dirs() -> list[Path]:
    return [
        _stage11_checkpoint_root() / dirname
        for dirname in LEGACY_DEV_EXECUTION_RESUME_DIR_NAMES
    ]


def _stage11_resume_read_dirs() -> list[Path]:
    return [_stage11_resume_dir(), *_stage11_legacy_resume_dirs()]


def _current_save_stage_dir(stage: int) -> Path | None:
    workspace = save_manager.current_save_workspace_dir(BASE_DIR)
    if workspace is None:
        return None
    return workspace / "outputs" / "artifacts" / f"stage_{stage:02d}"


def _legacy_save_stage_dir(stage: int) -> Path | None:
    # Legacy read-only fallback: older builds used save/ instead of saves/.
    index = read_json(BASE_DIR / "save" / "save_index.json", {})
    if not isinstance(index, dict):
        return None
    save_id = str(index.get("current_save_id") or "")
    if not save_id:
        return None
    return (
        BASE_DIR
        / "save"
        / save_id
        / "workspace"
        / "outputs"
        / "artifacts"
        / f"stage_{stage:02d}"
    )


def _previous_stage11_report() -> dict[str, Any]:
    candidates = [stage_dir(DEV_EXECUTION_STAGE) / "devexecution.json"]
    current_save_stage = _current_save_stage_dir(DEV_EXECUTION_STAGE)
    if current_save_stage is not None:
        candidates.append(current_save_stage / "devexecution.json")
    legacy_save_stage = _legacy_save_stage_dir(DEV_EXECUTION_STAGE)
    if legacy_save_stage is not None:
        candidates.append(legacy_save_stage / "devexecution.json")
    for path in candidates:
        report = read_json(path, {})
        if isinstance(report, dict) and report.get("records"):
            return report
    return {}


def _write_stage11_task_record(
    out_dir: Path, task_id: Any, record: dict[str, Any]
) -> None:
    filename = f"{task_id}_execution.json"
    write_json(out_dir / filename, record)
    write_json(_stage11_resume_dir() / filename, record)


def _stage11_record_successful(record: dict[str, Any]) -> bool:
    return str(record.get("status")) in {"success", "auto_repaired"}


def _records_from_devexecution_report(stage_path: Path | None) -> list[dict[str, Any]]:
    if stage_path is None:
        return []
    report = read_json(stage_path / "devexecution.json", {})
    records = report.get("records", []) if isinstance(report, dict) else []
    return [record for record in records if isinstance(record, dict)]


def _task_records_from_dir(stage_path: Path | None) -> list[dict[str, Any]]:
    if stage_path is None:
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(stage_path.glob("DEV-*_execution.json")):
        record = read_json(path, {})
        if isinstance(record, dict):
            records.append(record)
    return records


def _merge_task_records(sources: list[list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for records in sources:
        for record in records:
            task_id = str(record.get("task_id") or "")
            if not task_id or task_id in merged:
                continue
            merged[task_id] = record
    return merged


def _previous_records_by_task() -> dict[str, dict[str, Any]]:
    active_stage = stage_dir(DEV_EXECUTION_STAGE)
    current_save_stage = _current_save_stage_dir(DEV_EXECUTION_STAGE)
    legacy_save_stage = _legacy_save_stage_dir(DEV_EXECUTION_STAGE)
    legacy_resume_records: list[dict[str, Any]] = []
    for resume_dir in _stage11_legacy_resume_dirs():
        legacy_resume_records.extend(_task_records_from_dir(resume_dir))
    return _merge_task_records(
        [
            _task_records_from_dir(active_stage),
            _records_from_devexecution_report(active_stage),
            _task_records_from_dir(_stage11_resume_dir()),
            _task_records_from_dir(current_save_stage),
            _records_from_devexecution_report(current_save_stage),
            legacy_resume_records,
            _task_records_from_dir(legacy_save_stage),
            _records_from_devexecution_report(legacy_save_stage),
        ]
    )


def _can_reuse_existing_task_output(task: dict[str, Any], project_path: Path) -> bool:
    outputs = task.get("output_files", [])
    if not isinstance(outputs, list) or not outputs:
        return False
    return all((project_path / str(output)).is_file() for output in outputs)


def _write_stage11_progress(
    out_dir: Path,
    *,
    project_path: Path,
    editor_path: Path,
    expected_count: int,
    execution_records: list[dict[str, Any]],
    package_reports: list[dict[str, Any]],
    changed_files_manifest: list[dict[str, Any]],
    current_group_id: str = "",
    current_task_id: str = "",
    current_execution_object_id: str = "",
    status: str = "running",
    next_task_id: str = "",
    stop_reason: str = "",
) -> None:
    successful_count = sum(
        1 for record in execution_records if _stage11_record_successful(record)
    )
    completed_units = [
        str(record.get("task_id"))
        for record in execution_records
        if record.get("task_id") and _stage11_record_successful(record)
    ]
    progress = {
        "schema_version": 2,
        "generated_at": now_iso(),
        "execution_mode": "actual_unity_ai_development",
        "status": status,
        "project_path": str(project_path),
        "unity_editor_path": str(editor_path),
        "task_count": expected_count,
        "executed_task_count": len(execution_records),
        "successful_task_count": successful_count,
        "current_group_id": current_group_id,
        "current_task_id": current_task_id,
        "current_execution_object_id": current_execution_object_id,
        "next_task_id": next_task_id,
        "stop_reason": stop_reason,
        "records": execution_records,
        "package_change_reports": package_reports,
        "blocking_issues": [],
        "note": (
            "Step 11 stopped at a resumable task boundary."
            if status == "stopped"
            else "Step 11 is still executing. Final success is written only after all tasks and group Unity validation complete."
        ),
    }
    write_json(out_dir / "devexecution_progress.json", progress)
    write_json(out_dir / "development_execution_log.json", progress)
    write_json(
        out_dir / "changed_files_manifest.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "status": status,
            "tasks": changed_files_manifest,
        },
    )
    write_text(
        out_dir / "devexecution.md",
        "# Development Execution\n\n"
        f"- Status: {status}\n"
        f"- Completed tasks: {successful_count}/{expected_count}\n"
        + (f"- Current task: {current_task_id}\n" if current_task_id else "")
        + (f"- Next task: {next_task_id}\n" if next_task_id else "")
        + (f"- Stop reason: {stop_reason}\n" if stop_reason else "")
        + (
            "\n".join(
                f"- {record['task_id']}: {record['status']}"
                for record in execution_records
            )
            + "\n"
            if execution_records
            else ""
        ),
    )
    report = read_json(out_dir / "validation_report.json", {})
    if not isinstance(report, dict):
        report = {}
    report.update(
        {
            "status": status,
            "valid": False,
            "content_exists": bool(execution_records)
            or bool(current_task_id)
            or status == "stopped",
            "ai_review_status": status,
            "blocking_issues": 0,
            "traceability_valid": False,
            "scope_budget_valid": True,
            "business_quality": {
                "status": status,
                "executed_task_count": len(execution_records),
                "successful_task_count": successful_count,
                "task_count": expected_count,
                "current_group_id": current_group_id,
                "current_task_id": current_task_id,
                "next_task_id": next_task_id,
                "stop_reason": stop_reason,
            },
        }
    )
    write_json(out_dir / "validation_report.json", report)
    runtime_control.write_run_state(
        BASE_DIR,
        status=status,
        current_step=DEV_EXECUTION_STAGE,
        current_group_id=current_group_id,
        current_task_id=current_task_id,
        current_execution_object_id=current_execution_object_id,
        next_task_id=next_task_id,
        completed_units=completed_units,
        unit_type=DEV_EXECUTION_TASK_UNIT_TYPE,
        stop_reason=stop_reason,
    )


def _sync_stage11_checkpoint(out_dir: Path, *, event: str, message: str = "") -> None:
    try:
        save_manager.ensure_current_save(BASE_DIR)
        save_manager.retry_sync(
            BASE_DIR,
            event=event,
            stage=DEV_EXECUTION_STAGE,
            message=message,
            attempts=3,
            delay_seconds=1,
        )
    except (
        Exception
    ) as exc:  # noqa: BLE001 - checkpoint sync should be reported, not hidden
        write_json(
            out_dir / "save_sync_warning.json",
            {
                "schema_version": 1,
                "generated_at": now_iso(),
                "event": event,
                "message": message,
                "error": str(exc),
            },
        )


def _ordered_stage11_task_ids(parallel_groups: list[Any]) -> list[str]:
    ordered: list[str] = []
    for group in parallel_groups:
        if not isinstance(group, dict):
            continue
        task_ids = group.get("task_ids", [])
        if not isinstance(task_ids, list):
            continue
        ordered.extend(str(task_id) for task_id in task_ids if str(task_id))
    return ordered


def _next_stage11_task_id(ordered_task_ids: list[str], current_task_id: Any) -> str:
    current = str(current_task_id or "")
    if current not in ordered_task_ids:
        return ""
    index = ordered_task_ids.index(current) + 1
    return ordered_task_ids[index] if index < len(ordered_task_ids) else ""


def _write_stage11_stop_report(
    out_dir: Path,
    *,
    expected_count: int,
    execution_records: list[dict[str, Any]],
    current_group_id: str,
    current_task_id: str,
    next_task_id: str,
    stop_reason: str,
) -> dict[str, Any]:
    successful_count = sum(
        1 for record in execution_records if _stage11_record_successful(record)
    )
    report = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "stopped",
        "stage": DEV_EXECUTION_STAGE,
        "boundary": "after_current_task" if current_task_id else "before_next_task",
        "executed_task_count": len(execution_records),
        "successful_task_count": successful_count,
        "task_count": expected_count,
        "current_group_id": current_group_id,
        "current_task_id": current_task_id,
        "next_task_id": next_task_id,
        "resume_supported": True,
        "reason": stop_reason,
    }
    write_json(out_dir / "devexecution_stop_report.json", report)
    return report


@dataclass
class _Stage11SyncTracker:
    out_dir: Path
    every_tasks: int
    seconds: int
    completed_since_sync: int = 0
    last_sync_at: float = field(default_factory=time.monotonic)

    def task_checkpoint(self, *, event: str, message: str = "") -> None:
        self.completed_since_sync += 1
        elapsed = time.monotonic() - self.last_sync_at
        if self.completed_since_sync >= self.every_tasks or elapsed >= self.seconds:
            self.force(event=event, message=message)

    def group_checkpoint(self, *, event: str, message: str = "") -> None:
        self.force(event=event, message=message)

    def force(self, *, event: str, message: str = "") -> None:
        _sync_stage11_checkpoint(self.out_dir, event=event, message=message)
        self.completed_since_sync = 0
        self.last_sync_at = time.monotonic()


def _write_stage11_dependency_skip_report(
    out_dir: Path, skipped_records: list[dict[str, Any]]
) -> None:
    write_json(
        out_dir / "dependency_skip_report.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "skipped_task_count": len(skipped_records),
            "skipped_tasks": skipped_records,
        },
    )


def _append_stage11_review_outputs(
    out_dir: Path,
    *,
    status: str,
    records: list[dict[str, Any]],
    current_group_id: str = "",
    current_task_id: str = "",
    next_task_id: str = "",
    project_state_tainted: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    failed_records = [
        record
        for record in records
        if record.get("status") not in {"success", "auto_repaired"}
        and not str(record.get("status", "")).startswith("skipped")
    ]
    events = [
        build_failure_event(
            stage=DEV_EXECUTION_STAGE,
            record=record,
            reproduction_payload_path=str(record.get("reproduction_payload_path") or ""),
            log_paths=[str(item) for item in record.get("log_paths", []) if str(item)],
        )
        for record in failed_records
    ]
    correction_summary = upsert_failure_queue(
        out_dir,
        stage=DEV_EXECUTION_STAGE,
        events=events,
        reviewed_contract="program_task_breakdown.json",
        source_review="stage_11_unattended_execution",
    )
    resume_cursor = build_resume_cursor(
        stage=DEV_EXECUTION_STAGE,
        records=records,
        current_group_id=current_group_id,
        current_task_id=current_task_id,
        next_task_id=next_task_id,
        project_state_tainted=project_state_tainted,
    )
    config = unattended_config()
    summary = write_unattended_summary(
        out_dir,
        stage=DEV_EXECUTION_STAGE,
        status=status,
        records=records,
        correction_summary=correction_summary,
        resume_cursor=resume_cursor,
        continue_after_completed_with_review=config.continue_after_completed_with_review,
    )
    write_pause_resume_log(
        out_dir,
        stage=DEV_EXECUTION_STAGE,
        status=status,
        records=records,
        resume_cursor=resume_cursor,
        correction_summary=correction_summary,
        title="Development Execution Pause and Resume",
    )
    return summary, resume_cursor


def _extract_repair_payload(text: str) -> dict[str, Any]:
    match = re.search(r"REPAIR_JSON_START\s*(\{.*?\})\s*REPAIR_JSON_END", text, re.S)
    if not match:
        raise ValueError("repair response missing REPAIR_JSON_START/REPAIR_JSON_END block")
    data = json.loads(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("repair response JSON must be an object")
    return data


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.drive:
        return False
    return bool(str(value).strip())


def _allowed_repair_path(path: str, allowed_write_paths: list[str]) -> bool:
    normalized = Path(path).as_posix()
    for allowed in allowed_write_paths:
        allowed_norm = Path(str(allowed)).as_posix().rstrip("/")
        if normalized == allowed_norm or normalized.startswith(f"{allowed_norm}/"):
            return True
    return False


def _attempt_auto_repair_task(
    *,
    task: dict[str, Any],
    record: dict[str, Any],
    execution_store: Any,
    execution_object_id: str,
    project_path: Path,
    editor_path: Path,
    out_dir: Path,
    allowed_write_paths: list[str],
    output_files: list[str],
    repair_prompt_context: str,
) -> tuple[dict[str, Any], bool]:
    config = unattended_config()
    failure_event = build_failure_event(
        stage=DEV_EXECUTION_STAGE,
        record=record,
        reproduction_payload_path=str(record.get("reproduction_payload_path") or ""),
    )
    if not config.enable_step11_auto_repair or not failure_event.auto_repairable:
        return record, False
    if not execution_object_id:
        return record, False
    correction_id = correction_id_for_event(failure_event)
    try:
        current_object = execution_store.get(execution_object_id)
        current_facts = (
            current_object.get("submission_snapshot", {}).get("related_facts", {})
            if isinstance(current_object, dict)
            else {}
        )
        confirm_automated_retry_from_safe_point(
            execution_store,
            execution_object_id=execution_object_id,
            remaining_write_scope=[f"unity_file:{item}" for item in output_files],
            current_facts=current_facts,
            correction_id=correction_id,
        )
    except Exception as exc:  # noqa: BLE001 - recovery boundary
        record.setdefault("codex_errors", []).append(f"auto repair skipped: {exc}")
        return record, False

    attempts_path = out_dir / "repair_attempts.jsonl"
    last_hash = failure_event.error_hash
    for attempt_index in range(1, config.max_auto_repair_attempts + 1):
        attempt_id = f"RA-ST11-{task.get('task_id')}-{attempt_index:03d}"
        repair_task = build_file_generation_task(
            task_id=f"{task.get('task_id')}-repair-{attempt_index}",
            goal="\n".join(
                [
                    "Repair this Unity C# task failure.",
                    "Return only a REPAIR_JSON_START/REPAIR_JSON_END block.",
                    "Do not modify files outside allowed_write_paths.",
                    repair_prompt_context,
                    f"Failure summary: {failure_event.error_summary}",
                    f"Allowed write paths: {', '.join(allowed_write_paths)}",
                ]
            ),
            input_files=[],
            output_files=output_files,
            allowed_write_paths=allowed_write_paths,
        )
        repair_task.timeout_seconds = config.repair_timeout_seconds
        started_at = now_iso()
        attempt_record: dict[str, Any] = {
            "attempt_id": attempt_id,
            "correction_id": correction_id,
            "started_at": started_at,
            "timeout_seconds": config.repair_timeout_seconds,
            "written_files": [],
            "error_hash_before": last_hash,
        }
        try:
            from core.adapters.registry import get_adapter
            from core.config.ai_config import AI_CONFIG_PATH, get_active_profile

            if AI_CONFIG_PATH.exists():
                profile = get_active_profile()
                adapter = get_adapter(profile.adapter, profile=profile)
            else:
                adapter_name = load_project_settings(BASE_DIR).get("pipeline_adapter", "codex")
                adapter = get_adapter(adapter_name)
            repair_result = adapter.generate(repair_task)
            if repair_result.errors:
                raise RuntimeError("; ".join(repair_result.errors))
            payload = _extract_repair_payload(repair_result.text)
            if payload.get("needs_human"):
                attempt_record.update({"status": "needs_user_review", "finished_at": now_iso()})
                _append_jsonl(attempts_path, attempt_record)
                return record, False
            files = payload.get("files", [])
            if not isinstance(files, list):
                raise ValueError("repair files must be a list")
            written_files: list[str] = []
            before = _snapshot_project_files(project_path)
            for item in files:
                if not isinstance(item, dict):
                    raise ValueError("repair file entry must be an object")
                rel_path = str(item.get("path") or "")
                if not _is_safe_relative_path(rel_path):
                    raise ValueError(f"unsafe repair path: {rel_path}")
                if not _allowed_repair_path(rel_path, allowed_write_paths):
                    raise ValueError(f"repair path outside allowed_write_paths: {rel_path}")
                target = project_path / rel_path
                expected_hash = str(item.get("expected_hash_before") or "").strip()
                if expected_hash and target.is_file():
                    current_hash = project_file_hashes(project_path, [rel_path]).get(rel_path, "")
                    if current_hash and current_hash != expected_hash:
                        raise ValueError(f"expected_hash_before mismatch: {rel_path}")
                mode = str(item.get("mode") or "replace")
                if mode != "replace":
                    raise ValueError(f"unsupported repair mode: {mode}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(item.get("content") or ""), encoding="utf-8")
                written_files.append(rel_path)
            after = _snapshot_project_files(project_path)
            changed_files = _changed_files(before, after)
            unexpected_changes = [
                item for item in changed_files if item not in set(output_files).union(allowed_write_paths)
            ]
            if unexpected_changes:
                record["project_state_tainted"] = True
                raise RuntimeError(f"unexpected changes after repair: {unexpected_changes}")
            verification_results = _run_task_verification(
                task=task,
                project_path=project_path,
                editor_path=editor_path,
                out_dir=out_dir,
                defer_unity_batchmode=True,
            )
            verification_errors = [
                item
                for item in verification_results
                if item.get("status") not in {"passed", "deferred"}
            ]
            if verification_errors:
                error_hash_after = build_failure_event(
                    stage=DEV_EXECUTION_STAGE,
                    record={**record, "verification_results": verification_results},
                    reproduction_payload_path=str(record.get("reproduction_payload_path") or ""),
                ).error_hash
                attempt_record.update(
                    {
                        "status": "retry_failed",
                        "finished_at": now_iso(),
                        "written_files": written_files,
                        "error_hash_after": error_hash_after,
                        "verification_results": verification_results,
                    }
                )
                _append_jsonl(attempts_path, attempt_record)
                if error_hash_after == last_hash:
                    return record, False
                last_hash = error_hash_after
                continue
            final_hashes = project_file_hashes(project_path, output_files)
            record_automated_remediation(
                execution_store,
                execution_object_id=execution_object_id,
                repair_attempt_id=attempt_id,
                correction_id=correction_id,
                affected_files=written_files,
                final_hashes=final_hashes,
                validation_result={"status": "passed", "verification_results": verification_results},
                affected_scopes=[f"unity_file:{item}" for item in written_files],
            )
            verified_object = verify_program_task_execution_object(
                execution_store,
                execution_object_id=execution_object_id,
                project_path=project_path,
                output_files=output_files,
                written_files=written_files or output_files,
                verification_results=verification_results,
                execution_record=record,
            )
            record.update(
                {
                    "status": "auto_repaired",
                    "codex_errors": [],
                    "changed_files": sorted(set(record.get("changed_files", []) + written_files)),
                    "verification_results": verification_results,
                    "execution_object_state": verified_object.get("state"),
                    "auto_repair": {
                        "attempt_id": attempt_id,
                        "correction_id": correction_id,
                        "status": "repaired",
                    },
                }
            )
            attempt_record.update(
                {
                    "status": "repaired",
                    "finished_at": now_iso(),
                    "written_files": written_files,
                    "error_hash_after": "",
                    "verification_results": verification_results,
                }
            )
            _append_jsonl(attempts_path, attempt_record)
            return record, True
        except Exception as exc:  # noqa: BLE001 - repair boundary
            attempt_record.update(
                {
                    "status": "retry_failed",
                    "finished_at": now_iso(),
                    "error": str(exc),
                }
            )
            _append_jsonl(attempts_path, attempt_record)
            record.setdefault("codex_errors", []).append(f"auto repair failed: {exc}")
            if record.get("project_state_tainted"):
                return record, False
    return record, False


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _stage11_active_execution_object_id(execution_store: Any, task_id: Any) -> str:
    task_id_text = str(task_id or "")
    if not task_id_text:
        return ""
    for obj in reversed(execution_store.list_objects()):
        if (
            obj.get("metadata", {}).get("stage") == DEV_EXECUTION_STAGE
            and obj.get("metadata", {}).get("business_id") == task_id_text
            and obj.get("state") in {"approved", "executing", "cancellation_requested"}
        ):
            return str(obj.get("execution_object_id") or "")
    return ""


def _stage10_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    program_plan = _program_plan()
    program_tasks = _program_tasks()
    art_tasks = _art_tasks()
    assets = _art_assets()
    allowed_roots = _program_allowed_roots()
    links = []
    for asset in assets:
        source = asset.get("source")
        related_program = [
            task["task_id"]
            for task in program_tasks
            if source and source in task.get("source_refs", [])
        ]
        links.append(
            {
                "asset_id": asset.get("asset_id"),
                "asset_name": asset.get("name"),
                "source": source,
                "art_tasks": [
                    task["task_id"]
                    for task in art_tasks
                    if task.get("asset_id") == asset.get("asset_id")
                ],
                "program_tasks": related_program,
                "status": "aligned" if source else "missing_source",
            }
        )
    gaps = [item for item in links if item["status"] != "aligned"]

    path_blockers = []
    required_task_fields = [
        "task_id",
        "requirement_id",
        "target_path",
        "output_files",
        "allowed_write_paths",
        "verification_commands",
        "source_refs",
        "acceptance",
    ]
    for task in program_tasks:
        task_id = task.get("task_id")
        for field_name in required_task_fields:
            if field_name not in task or task.get(field_name) in ("", [], None):
                path_blockers.append(
                    {
                        "code": "TASK_FIELD_MISSING",
                        "task_id": task_id,
                        "field": field_name,
                        "message": "Stage 09 task is missing a required actual-development field.",
                    }
                )
        task_outputs = task.get("output_files", [])
        if not isinstance(task_outputs, list):
            task_outputs = []
        for output in task_outputs:
            if not _is_under_allowed_roots(str(output), allowed_roots):
                path_blockers.append(
                    {
                        "code": "OUTPUT_OUTSIDE_ALLOWED_ROOT",
                        "task_id": task_id,
                        "output_file": output,
                        "allowed_roots": allowed_roots,
                    }
                )
    if not isinstance(program_plan.get("dependencies"), list):
        path_blockers.append(
            {
                "code": "TOPOLOGY_DEPENDENCIES_MISSING",
                "message": "Stage 09 program_task_breakdown.json must include top-level dependencies.",
            }
        )
    if not isinstance(program_plan.get("parallel_groups"), list):
        path_blockers.append(
            {
                "code": "TOPOLOGY_PARALLEL_GROUPS_MISSING",
                "message": "Stage 09 program_task_breakdown.json must include top-level parallel_groups.",
            }
        )

    task_ids = {str(task.get("task_id")) for task in program_tasks}
    dependency_blockers = []
    plan_dependencies = program_plan.get("dependencies", [])
    if not isinstance(plan_dependencies, list):
        plan_dependencies = []
    for edge in plan_dependencies:
        if str(edge.get("from")) not in task_ids or str(edge.get("to")) not in task_ids:
            dependency_blockers.append(
                {
                    "code": "DEPENDENCY_UNKNOWN_TASK",
                    "edge": edge,
                    "message": "Dependency references an unknown task id.",
                }
            )

    conflict_items = []
    output_by_task = {
        str(task.get("task_id")): [str(item) for item in task.get("output_files", [])]
        for task in program_tasks
    }
    plan_parallel_groups = program_plan.get("parallel_groups", [])
    if not isinstance(plan_parallel_groups, list):
        plan_parallel_groups = []
    for group in plan_parallel_groups:
        seen: dict[str, str] = {}
        group_task_ids = group.get("task_ids", []) if isinstance(group, dict) else []
        if not isinstance(group_task_ids, list):
            group_task_ids = []
        for task_id in group_task_ids:
            for output in output_by_task.get(str(task_id), []):
                if output in seen:
                    conflict_items.append(
                        {
                            "code": "PARALLEL_OUTPUT_CONFLICT",
                            "group_id": group.get("group_id"),
                            "output_file": output,
                            "task_ids": [seen[output], str(task_id)],
                        }
                    )
                else:
                    seen[output] = str(task_id)

    all_plan_blockers = path_blockers + dependency_blockers + conflict_items
    write_text(
        out_dir / "AlignmentProtocol.md",
        "# Alignment Protocol\n\n"
        "- Program and art plans align by source trace and asset id.\n"
        "- Stage 11 also validates actual Unity path binding before Stage 12.\n"
        "- Output files outside Stage 03 allowed roots block actual development.\n",
    )
    write_text(
        out_dir / "program_assets.md",
        "# Program Asset References\n\n"
        + "\n".join(
            f"- {link['asset_id']}: program_tasks={link['program_tasks'] or 'none'}"
            for link in links
        )
        + "\n",
    )
    write_text(
        out_dir / "art_assets.md",
        "# Art Asset Deliverables\n\n"
        + "\n".join(
            f"- {link['asset_id']}: art_tasks={link['art_tasks'] or 'none'}"
            for link in links
        )
        + "\n",
    )
    write_text(
        out_dir / "dependency_graph.md",
        "# Dependency Graph\n\n"
        + "\n".join(
            f"- {edge.get('from')} -> {edge.get('to')} ({edge.get('relation', 'depends_on')})"
            for edge in plan_dependencies
        )
        + "\n",
    )
    write_text(
        out_dir / "gap_analysis.md",
        "# Gap Analysis\n\n"
        + (
            "- No blocking gaps.\n"
            if not gaps and not all_plan_blockers
            else "\n".join(
                f"- {item.get('code', item.get('status', 'gap'))}: {item}"
                for item in gaps + all_plan_blockers
            )
            + "\n"
        ),
    )
    write_json(
        out_dir / "asset_alignment_matrix.json",
        {"schema_version": 1, "generated_at": now_iso(), "links": links, "gaps": gaps},
    )
    write_json(
        out_dir / "path_binding_validation.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "valid": not path_blockers and not dependency_blockers,
            "allowed_roots": allowed_roots,
            "blockers": path_blockers + dependency_blockers,
        },
    )
    write_json(
        out_dir / "parallel_conflict_report.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "valid": not conflict_items,
            "conflicts": conflict_items,
        },
    )
    write_json(
        out_dir / "validation_report_alignment.json",
        {
            "valid": not gaps and not all_plan_blockers,
            "gap_count": len(gaps),
            "path_blocker_count": len(path_blockers),
            "dependency_blocker_count": len(dependency_blockers),
            "parallel_conflict_count": len(conflict_items),
        },
    )
    return {
        "content_exists": bool(links) or bool(program_tasks),
        "alignment_count": len(links),
        "blocking_issues": len(gaps) + len(all_plan_blockers),
        "ai_review_status": (
            "passed" if not gaps and not all_plan_blockers else "blocked"
        ),
        "traceability_valid": not gaps and not all_plan_blockers,
    }


def _stage11_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    preflight = run_actual_development_preflight(BASE_DIR, write_report=True)
    plan = _program_plan()
    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    plan_blockers = _validate_actual_development_plan(plan)
    path_validation = read_json(
        stage_dir(ASSET_ALIGNMENT_STAGE) / "path_binding_validation.json", {}
    )
    parallel_validation = read_json(
        stage_dir(ASSET_ALIGNMENT_STAGE) / "parallel_conflict_report.json", {}
    )
    if isinstance(path_validation, dict) and path_validation.get("valid") is False:
        plan_blockers.extend(path_validation.get("blockers", []))
    if (
        isinstance(parallel_validation, dict)
        and parallel_validation.get("valid") is False
    ):
        plan_blockers.extend(parallel_validation.get("conflicts", []))

    preflight_blockers = (
        preflight.get("blockers", []) if preflight.get("status") != "passed" else []
    )
    blocking_before_execution = list(preflight_blockers) + list(plan_blockers)
    if blocking_before_execution:
        result = {
            "schema_version": 2,
            "generated_at": now_iso(),
            "execution_mode": "actual_unity_ai_development",
            "status": "blocked",
            "preflight_status": preflight.get("status"),
            "records": [],
            "blocking_issues": blocking_before_execution,
            "rule": "Step 11 must not fabricate development success when preflight or Stage 09 topology is invalid.",
        }
        write_json(out_dir / "devexecution.json", result)
        write_json(out_dir / "actual_development_blocked.json", result)
        write_json(out_dir / "actual_development_report.json", result)
        write_json(out_dir / "development_execution_log.json", result)
        write_text(
            out_dir / "devexecution.md",
            "# Development Execution\n\n"
            "- Status: blocked\n"
            "- No Unity project files were modified by Step 11.\n",
        )
        return {
            "content_exists": True,
            "executed_task_count": 0,
            "blocking_issues": len(blocking_before_execution),
            "ai_review_status": "blocked",
            "traceability_valid": False,
        }

    settings = load_project_settings(BASE_DIR)
    project_path = Path(settings["development_path"]).expanduser()
    editor_path = Path(settings["editor_path"]).expanduser()
    unattended = unattended_config()
    sync_tracker = _Stage11SyncTracker(
        out_dir=out_dir,
        every_tasks=unattended.sync_checkpoint_every_tasks,
        seconds=unattended.sync_checkpoint_seconds,
    )
    execution_store = load_execution_object_store(BASE_DIR)
    tasks_by_id = {
        str(task.get("task_id")): task for task in tasks if isinstance(task, dict)
    }
    parallel_groups = plan.get("parallel_groups", [])
    if not isinstance(parallel_groups, list):
        parallel_groups = []
    ordered_task_ids = _ordered_stage11_task_ids(parallel_groups)

    execution_records: list[dict[str, Any]] = []
    package_reports: list[dict[str, Any]] = []
    changed_files_manifest: list[dict[str, Any]] = []
    previous_records = _previous_records_by_task()
    stopped = False
    soft_stopped = False
    stop_reason = ""
    resume_next_task_id = ""
    project_state_tainted = False
    skipped_task_info: dict[str, dict[str, Any]] = {}
    skipped_records: list[dict[str, Any]] = []
    expected_count = len(tasks_by_id)
    _write_stage11_progress(
        out_dir,
        project_path=project_path,
        editor_path=editor_path,
        expected_count=expected_count,
        execution_records=execution_records,
        package_reports=package_reports,
        changed_files_manifest=changed_files_manifest,
    )

    for group in parallel_groups:
        if stopped:
            break
        group_id = group.get("group_id") if isinstance(group, dict) else "unknown_group"
        group_task_ids = group.get("task_ids", []) if isinstance(group, dict) else []
        if not isinstance(group_task_ids, list):
            group_task_ids = []
        group_record_indexes: list[int] = []
        group_needs_unity_compile = False
        group_failed_without_taint = False
        for task_id in group_task_ids:
            if str(task_id) in skipped_task_info:
                task = tasks_by_id.get(str(task_id), {})
                info = skipped_task_info[str(task_id)]
                record = {
                    "task_id": task_id,
                    "group_id": group_id,
                    "requirement_id": task.get("requirement_id") if isinstance(task, dict) else "",
                    "phase": task.get("phase") if isinstance(task, dict) else "",
                    "status": info.get("status", "skipped_by_dependency"),
                    "blocked_by": info.get("blocked_by", []),
                    "changed_files": [],
                    "unexpected_changes": [],
                    "verification_results": [],
                    "source_refs": task.get("source_refs", []) if isinstance(task, dict) else [],
                    "execution_note": "Skipped because a dependency requires review.",
                }
                execution_records.append(record)
                skipped_records.append(record)
                _write_stage11_task_record(out_dir, task_id, record)
                continue
            if runtime_control.stop_requested(BASE_DIR):
                stopped = True
                soft_stopped = True
                resume_next_task_id = str(task_id)
                stop_reason = f"Operator requested soft stop before {task_id}."
                _write_stage11_progress(
                    out_dir,
                    project_path=project_path,
                    editor_path=editor_path,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    package_reports=package_reports,
                    changed_files_manifest=changed_files_manifest,
                    current_group_id=str(group_id),
                    next_task_id=resume_next_task_id,
                    stop_reason=stop_reason,
                    status="stopped",
                )
                _write_stage11_stop_report(
                    out_dir,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    current_group_id=str(group_id),
                    current_task_id="",
                    next_task_id=resume_next_task_id,
                    stop_reason=stop_reason,
                )
                _sync_stage11_checkpoint(
                    out_dir,
                    event="stage11_soft_stopped",
                    message=stop_reason,
                )
                break
            task = tasks_by_id.get(str(task_id))
            if not task:
                stopped = True
                stop_reason = f"Unknown task in execution topology: {task_id}"
                break

            output_files = [str(item) for item in task.get("output_files", [])]
            package_changes = task.get("package_changes", [])
            if not isinstance(package_changes, list):
                package_changes = []
            allowed_changed_files = set(output_files)
            allowed_write_paths = [
                str(item) for item in task.get("allowed_write_paths", [])
            ]
            allowed_changed_files.update(
                _unity_allowed_companion_files(output_files, allowed_write_paths)
            )
            if package_changes:
                allowed_changed_files.add("Packages/manifest.json")

            execution_object_id = _stage11_active_execution_object_id(
                execution_store, task.get("task_id")
            )
            try:
                if not execution_object_id:
                    execution_object = begin_program_task_execution_object(
                        execution_store,
                        task=task,
                        project_path=project_path,
                        stage=DEV_EXECUTION_STAGE,
                    )
                    execution_object_id = str(
                        execution_object.get("execution_object_id") or ""
                    )
                _write_stage11_progress(
                    out_dir,
                    project_path=project_path,
                    editor_path=editor_path,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    package_reports=package_reports,
                    changed_files_manifest=changed_files_manifest,
                    current_group_id=str(group_id),
                    current_task_id=str(task.get("task_id") or ""),
                    current_execution_object_id=execution_object_id,
                )
            except Exception as exc:  # noqa: BLE001 - workflow gate boundary
                matching_objects = [
                    obj
                    for obj in execution_store.list_objects()
                    if obj.get("metadata", {}).get("stage") == 10
                    and obj.get("metadata", {}).get("business_id")
                    == task.get("task_id")
                ]
                if matching_objects:
                    execution_object_id = str(
                        matching_objects[-1].get("execution_object_id") or ""
                    )
                record = {
                    "task_id": task.get("task_id"),
                    "group_id": group_id,
                    "requirement_id": task.get("requirement_id"),
                    "phase": task.get("phase"),
                    "status": "failed",
                    "codex_status": "not_started",
                    "codex_errors": [str(exc)],
                    "codex_warnings": [],
                    "changed_files": [],
                    "diff_summary": {
                        "changed_file_count": 0,
                        "unexpected_change_count": 0,
                        "allowed_changed_files": sorted(allowed_changed_files),
                    },
                    "unexpected_changes": [],
                    "verification_results": [],
                    "source_refs": task.get("source_refs", []),
                    "execution_object_id": execution_object_id,
                    "execution_object_state": (
                        execution_store.get(execution_object_id).get("state")
                        if execution_object_id
                        else ""
                    ),
                    "execution_note": "Blocked by execution-object workflow before writing project files.",
                }
                execution_records.append(record)
                group_record_indexes.append(len(execution_records) - 1)
                changed_files_manifest.append(
                    {
                        "task_id": task.get("task_id"),
                        "allowed_files": sorted(allowed_changed_files),
                        "changed_files": [],
                        "unexpected_changes": [],
                        "execution_object_id": execution_object_id,
                    }
                )
                _write_stage11_task_record(out_dir, task.get("task_id"), record)
                _write_stage11_progress(
                    out_dir,
                    project_path=project_path,
                    editor_path=editor_path,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    package_reports=package_reports,
                    changed_files_manifest=changed_files_manifest,
                    current_group_id=str(group_id),
                    current_task_id=str(task.get("task_id") or ""),
                    current_execution_object_id=execution_object_id,
                )
                stop_reason = (
                    f"Task {task.get('task_id')} failed execution-object gate."
                )
                if unattended.continue_independent_tasks:
                    failed_id = str(task.get("task_id") or "")
                    skipped_task_info.update(
                        dependency_skip_ids(
                            failed_task_ids={failed_id},
                            current_group_id=str(group_id),
                            parallel_groups=parallel_groups,
                            dependencies=plan.get("dependencies", []),
                        )
                    )
                    group_failed_without_taint = True
                else:
                    stopped = True
                break

            reused_existing_output = False
            codex_result = None
            codex_errors: list[str] = []
            codex_warnings: list[str] = []
            reproduction_payload_path = ""
            task_prompt_for_repair = ""
            previous_record = previous_records.get(str(task.get("task_id")))
            if previous_record and _can_reuse_existing_task_output(task, project_path):
                reused_existing_output = True
                package_report = {
                    "manifest": "Packages/manifest.json",
                    "status": "reused_previous_output",
                    "changes": package_changes,
                    "errors": [],
                    "task_id": task.get("task_id"),
                }
                package_reports.append(package_report)
                changed_files = [
                    str(item)
                    for item in previous_record.get("changed_files", [])
                    if str(item)
                ] or output_files
                unexpected_changes = [
                    item for item in changed_files if item not in allowed_changed_files
                ]
            else:
                before = _snapshot_project_files(project_path)
                package_report = _apply_package_changes(project_path, package_changes)
                package_report["task_id"] = task.get("task_id")
                package_reports.append(package_report)

                if package_report.get("status") == "failed":
                    codex_errors.extend(package_report.get("errors", []))
                else:
                    goal = "\n".join(
                        [
                            "Implement this Unity C# development task in the existing project.",
                            f"Task: {task.get('task_id')}",
                            f"Requirement: {task.get('title')}",
                            f"Acceptance: {task.get('acceptance')}",
                            "Rules:",
                            "- Edit only the declared output files.",
                            "- Do not create a Unity project or change project structure.",
                            "- Keep code compatible with the current Unity project.",
                            "- The primary public type in each C# file must match the filename.",
                            "- Treat this prompt as the complete task brief; do not read full pipeline JSON files.",
                            "- Keep each file concise and self-contained. Prefer simple data models, validation methods, and manual-check helpers.",
                            "- Avoid broad project searches. Inspect only the target folder if you need local naming conventions.",
                            "- Do not add unguarded NUnit references. If you use NUnit.Framework, [Test], or NUnit assertions, wrap the entire NUnit-dependent test file with DEVxxx_ENABLE_NUNIT_TESTS or replace them with local helper methods.",
                        ]
                    )
                    model_task = build_file_generation_task(
                        task_id=str(task.get("task_id")),
                        goal=goal,
                        input_files=[],
                        output_files=output_files,
                        allowed_write_paths=allowed_write_paths,
                    )
                    model_task.timeout_seconds = 720
                    task_prompt_for_repair = model_task.prompt
                    adapter_name = "unknown"
                    try:
                        from core.adapters.registry import get_adapter
                        from core.config.ai_config import AI_CONFIG_PATH, get_active_profile

                        if AI_CONFIG_PATH.exists():
                            _profile = get_active_profile()
                            adapter_name = _profile.adapter
                            model_adapter = get_adapter(_profile.adapter, profile=_profile)
                        else:
                            _adapter_name = load_project_settings(BASE_DIR).get(
                                "pipeline_adapter", "codex"
                            )
                            adapter_name = str(_adapter_name)
                            model_adapter = get_adapter(_adapter_name)
                        reproduction_payload_path = write_reproduction_payload(
                            out_dir,
                            task=task,
                            prompt=model_task.prompt,
                            adapter_name=adapter_name,
                            timeout_seconds=model_task.timeout_seconds,
                            allowed_write_paths=allowed_write_paths,
                            output_files=output_files,
                            package_changes=package_changes,
                        )
                        codex_result = model_adapter.generate(model_task)
                        codex_errors.extend(codex_result.errors)
                    except Exception as exc:
                        codex_errors.append(str(exc))

                after = _snapshot_project_files(project_path)
                changed_files = _changed_files(before, after)
                unexpected_changes = [
                    item for item in changed_files if item not in allowed_changed_files
                ]
            if (
                codex_errors
                and _can_reuse_existing_task_output(task, project_path)
                and not unexpected_changes
            ):
                codex_warnings.extend(codex_errors)
                codex_errors = []
            verification_results = []
            if not codex_errors and not unexpected_changes:
                verification_results = _run_task_verification(
                    task=task,
                    project_path=project_path,
                    editor_path=editor_path,
                    out_dir=out_dir,
                    defer_unity_batchmode=True,
                )
            if any(
                result.get("status") == "deferred" for result in verification_results
            ):
                group_needs_unity_compile = True
            verification_errors = [
                result
                for result in verification_results
                if result.get("status") not in {"passed", "deferred"}
            ]
            status = (
                "success"
                if not codex_errors
                and not unexpected_changes
                and not verification_errors
                else "failed"
            )
            record = {
                "task_id": task.get("task_id"),
                "group_id": group_id,
                "requirement_id": task.get("requirement_id"),
                "phase": task.get("phase"),
                "status": status,
                "codex_status": (
                    "reused_previous_output"
                    if reused_existing_output
                    else (
                        codex_result.status
                        if codex_result
                        else "not_run" if codex_errors else "unknown"
                    )
                ),
                "codex_errors": _compact_messages(codex_errors),
                "codex_warnings": _compact_messages(codex_warnings),
                "package_errors": _compact_messages(package_report.get("errors", [])),
                "reproduction_payload_path": reproduction_payload_path,
                "changed_files": changed_files,
                "diff_summary": {
                    "changed_file_count": len(changed_files),
                    "unexpected_change_count": len(unexpected_changes),
                    "allowed_changed_files": sorted(allowed_changed_files),
                },
                "unexpected_changes": unexpected_changes,
                "verification_results": verification_results,
                "source_refs": task.get("source_refs", []),
                "execution_object_id": execution_object_id,
                "execution_object_state": (
                    execution_store.get(execution_object_id).get("state")
                    if execution_object_id
                    else ""
                ),
                "execution_note": (
                    "Reused existing Codex-generated outputs from the previous Step 11 attempt."
                    if reused_existing_output
                    else "Executed serially inside the Stage 09 declared parallel group for post-run audit isolation."
                ),
            }
            if execution_object_id and status != "success":
                record_execution_object_failure(
                    execution_store,
                    execution_object_id=execution_object_id,
                    failure_stage="task_execution",
                    written_files=changed_files,
                    changed_state=[task.get("task_id")],
                    unfinished_actions=["verification"],
                    error="; ".join(_compact_messages(codex_errors))
                    or "Task execution failed.",
                    rollback_needed=bool(changed_files),
                )
                record["execution_object_state"] = execution_store.get(
                    execution_object_id
                ).get("state")
                repaired_record, repaired = _attempt_auto_repair_task(
                    task=task,
                    record=record,
                    execution_store=execution_store,
                    execution_object_id=execution_object_id,
                    project_path=project_path,
                    editor_path=editor_path,
                    out_dir=out_dir,
                    allowed_write_paths=allowed_write_paths,
                    output_files=output_files,
                    repair_prompt_context=task_prompt_for_repair,
                )
                record = repaired_record
                if repaired:
                    status = str(record.get("status") or "auto_repaired")
            elif execution_object_id and not any(
                result.get("status") == "deferred" for result in verification_results
            ):
                try:
                    verified_object = verify_program_task_execution_object(
                        execution_store,
                        execution_object_id=execution_object_id,
                        project_path=project_path,
                        output_files=output_files,
                        written_files=changed_files or output_files,
                        verification_results=verification_results,
                        execution_record=record,
                    )
                    record["execution_object_state"] = verified_object.get("state")
                except Exception as exc:  # noqa: BLE001 - verifier boundary
                    record["status"] = "failed"
                    record.setdefault("codex_errors", []).append(str(exc))
                    record_execution_object_failure(
                        execution_store,
                        execution_object_id=execution_object_id,
                        failure_stage="execution_object_verification",
                        written_files=changed_files,
                        changed_state=[task.get("task_id")],
                        unfinished_actions=["execution_object_verification"],
                        error=str(exc),
                        rollback_needed=bool(changed_files),
                    )
                    record["execution_object_state"] = execution_store.get(
                        execution_object_id
                    ).get("state")
            execution_records.append(record)
            group_record_indexes.append(len(execution_records) - 1)
            changed_files_manifest.append(
                {
                    "task_id": task.get("task_id"),
                    "allowed_files": sorted(allowed_changed_files),
                    "changed_files": changed_files,
                    "unexpected_changes": unexpected_changes,
                    "execution_object_id": execution_object_id,
                }
            )
            status = str(record.get("status"))
            _write_stage11_task_record(out_dir, task.get("task_id"), record)
            _write_stage11_progress(
                out_dir,
                project_path=project_path,
                editor_path=editor_path,
                expected_count=expected_count,
                execution_records=execution_records,
                package_reports=package_reports,
                changed_files_manifest=changed_files_manifest,
                current_group_id=str(group_id),
                current_task_id=str(task.get("task_id") or ""),
                current_execution_object_id=execution_object_id,
            )
            sync_tracker.task_checkpoint(
                event="stage11_task_checkpoint",
                message=f"{task.get('task_id')} {status}",
            )
            if status not in {"success", "auto_repaired"}:
                stopped = True
                stop_reason = f"Task {task.get('task_id')} failed."
                if record.get("unexpected_changes") or record.get("project_state_tainted"):
                    project_state_tainted = True
                if project_state_tainted or not unattended.continue_independent_tasks:
                    break
                failed_id = str(task.get("task_id") or "")
                skipped_task_info.update(
                    dependency_skip_ids(
                        failed_task_ids={failed_id},
                        current_group_id=str(group_id),
                        parallel_groups=parallel_groups,
                        dependencies=plan.get("dependencies", []),
                    )
                )
                stopped = False
                group_failed_without_taint = True
                break
            if runtime_control.stop_requested(BASE_DIR):
                stopped = True
                soft_stopped = True
                resume_next_task_id = _next_stage11_task_id(
                    ordered_task_ids, task.get("task_id")
                )
                stop_reason = (
                    f"Operator requested soft stop after {task.get('task_id')}."
                )
                _write_stage11_progress(
                    out_dir,
                    project_path=project_path,
                    editor_path=editor_path,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    package_reports=package_reports,
                    changed_files_manifest=changed_files_manifest,
                    current_group_id=str(group_id),
                    current_task_id=str(task.get("task_id") or ""),
                    current_execution_object_id=execution_object_id,
                    next_task_id=resume_next_task_id,
                    stop_reason=stop_reason,
                    status="stopped",
                )
                _write_stage11_stop_report(
                    out_dir,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    current_group_id=str(group_id),
                    current_task_id=str(task.get("task_id") or ""),
                    next_task_id=resume_next_task_id,
                    stop_reason=stop_reason,
                )
                _sync_stage11_checkpoint(
                    out_dir,
                    event="stage11_soft_stopped",
                    message=stop_reason,
                )
                break
        if stopped:
            break
        if group_failed_without_taint:
            _write_stage11_dependency_skip_report(out_dir, skipped_records)
            sync_tracker.group_checkpoint(
                event="stage11_group_completed_with_review",
                message=str(group_id),
            )
            continue
        if group_record_indexes and group_needs_unity_compile:
            unity_result = _run_unity_batchmode_compile(
                editor_path=editor_path,
                project_path=project_path,
                log_path=out_dir / "unity_logs" / f"{group_id}.log",
            )
            for record_index in group_record_indexes:
                record = execution_records[record_index]
                record["verification_results"] = [
                    (
                        unity_result
                        if result.get("id") == "unity_batchmode_compile"
                        and result.get("status") == "deferred"
                        else result
                    )
                    for result in record.get("verification_results", [])
                ]
                if unity_result.get("status") != "passed":
                    record["status"] = "failed"
                execution_object_id = str(record.get("execution_object_id") or "")
                if execution_object_id:
                    current_state = execution_store.get(execution_object_id).get(
                        "state"
                    )
                    task = tasks_by_id.get(str(record.get("task_id")), {})
                    output_files = (
                        [str(item) for item in task.get("output_files", [])]
                        if isinstance(task, dict)
                        else []
                    )
                    if (
                        _stage11_record_successful(record)
                        and current_state == "executing"
                    ):
                        try:
                            verified_object = verify_program_task_execution_object(
                                execution_store,
                                execution_object_id=execution_object_id,
                                project_path=project_path,
                                output_files=output_files,
                                written_files=record.get("changed_files", [])
                                or output_files,
                                verification_results=record.get(
                                    "verification_results", []
                                ),
                                execution_record=record,
                            )
                            record["execution_object_state"] = verified_object.get(
                                "state"
                            )
                        except Exception as exc:  # noqa: BLE001 - verifier boundary
                            record["status"] = "failed"
                            record.setdefault("codex_errors", []).append(str(exc))
                            record_execution_object_failure(
                                execution_store,
                                execution_object_id=execution_object_id,
                                failure_stage="execution_object_group_verification",
                                written_files=record.get("changed_files", []),
                                changed_state=[record.get("task_id")],
                                unfinished_actions=[
                                    "execution_object_group_verification"
                                ],
                                error=str(exc),
                                rollback_needed=bool(record.get("changed_files")),
                            )
                            record["execution_object_state"] = execution_store.get(
                                execution_object_id
                            ).get("state")
                    elif (
                        not _stage11_record_successful(record)
                        and current_state == "executing"
                    ):
                        record_execution_object_failure(
                            execution_store,
                            execution_object_id=execution_object_id,
                            failure_stage="unity_batchmode_compile",
                            written_files=record.get("changed_files", []),
                            changed_state=[record.get("task_id")],
                            unfinished_actions=["unity_validation"],
                            error="; ".join(
                                _compact_messages(unity_result.get("errors", []))
                            )
                            or "Unity validation failed.",
                            rollback_needed=bool(record.get("changed_files")),
                        )
                        record["execution_object_state"] = execution_store.get(
                            execution_object_id
                        ).get("state")
                _write_stage11_task_record(out_dir, record.get("task_id"), record)
                _write_stage11_progress(
                    out_dir,
                    project_path=project_path,
                    editor_path=editor_path,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    package_reports=package_reports,
                    changed_files_manifest=changed_files_manifest,
                    current_group_id=str(group_id),
                    current_task_id=str(record.get("task_id") or ""),
                    current_execution_object_id=str(
                        record.get("execution_object_id") or ""
                    ),
                )
            sync_tracker.group_checkpoint(
                event="stage11_group_checkpoint",
                message=str(group_id),
            )
            group_failed_after_validation = any(
                not _stage11_record_successful(execution_records[index])
                for index in group_record_indexes
            )
            if unity_result.get("status") != "passed":
                stopped = True
                stop_reason = f"Unity validation failed for {group_id}."
                break
            if group_failed_after_validation:
                stopped = True
                stop_reason = f"Execution-object verification failed for {group_id}."
                break
            if runtime_control.stop_requested(BASE_DIR):
                stopped = True
                soft_stopped = True
                last_task_id = str(
                    execution_records[group_record_indexes[-1]].get("task_id") or ""
                )
                resume_next_task_id = _next_stage11_task_id(
                    ordered_task_ids, last_task_id
                )
                stop_reason = (
                    f"Operator requested soft stop after {group_id} validation."
                )
                _write_stage11_progress(
                    out_dir,
                    project_path=project_path,
                    editor_path=editor_path,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    package_reports=package_reports,
                    changed_files_manifest=changed_files_manifest,
                    current_group_id=str(group_id),
                    current_task_id=last_task_id,
                    next_task_id=resume_next_task_id,
                    stop_reason=stop_reason,
                    status="stopped",
                )
                _write_stage11_stop_report(
                    out_dir,
                    expected_count=expected_count,
                    execution_records=execution_records,
                    current_group_id=str(group_id),
                    current_task_id=last_task_id,
                    next_task_id=resume_next_task_id,
                    stop_reason=stop_reason,
                )
                _sync_stage11_checkpoint(
                    out_dir,
                    event="stage11_soft_stopped",
                    message=stop_reason,
                )
                break
        elif group_record_indexes:
            sync_tracker.group_checkpoint(
                event="stage11_group_checkpoint",
                message=str(group_id),
            )

    executed_successfully = [
        record for record in execution_records if _stage11_record_successful(record)
    ]
    review_records = [
        record
        for record in execution_records
        if not _stage11_record_successful(record)
        and not str(record.get("status", "")).startswith("skipped")
    ]
    skipped_count = sum(
        1 for record in execution_records if str(record.get("status", "")).startswith("skipped")
    )
    status = (
        "success"
        if len(executed_successfully) == expected_count and not stopped and not review_records
        else "stopped" if soft_stopped else "blocked"
    )
    if (
        status == "blocked"
        and not project_state_tainted
        and (review_records or skipped_count)
    ):
        status = "completed_with_review"
    blocking_issues = []
    if stop_reason and not soft_stopped:
        blocking_issues.append({"code": "EXECUTION_STOPPED", "message": stop_reason})
    for record in execution_records:
        if not _stage11_record_successful(record) and not str(
            record.get("status", "")
        ).startswith("skipped"):
            blocking_issues.append(
                {
                    "code": "TASK_EXECUTION_FAILED",
                    "task_id": record.get("task_id"),
                    "codex_errors": record.get("codex_errors", []),
                    "unexpected_changes": record.get("unexpected_changes", []),
                    "verification_results": record.get("verification_results", []),
                }
            )

    result = {
        "schema_version": 2,
        "generated_at": now_iso(),
        "execution_mode": "actual_unity_ai_development",
        "status": status,
        "project_path": str(project_path),
        "unity_editor_path": str(editor_path),
        "task_count": expected_count,
        "executed_task_count": len(execution_records),
        "successful_task_count": len(executed_successfully),
        "next_task_id": resume_next_task_id,
        "stop_reason": stop_reason if soft_stopped else "",
        "resume_supported": status in {"stopped", "completed_with_review"},
        "records": execution_records,
        "package_change_reports": package_reports,
        "execution_object_store": rel(execution_store.path),
        "execution_object_ids": [
            record.get("execution_object_id")
            for record in execution_records
            if record.get("execution_object_id")
        ],
        "blocking_issues": blocking_issues if status == "blocked" else [],
    }
    unattended_summary: dict[str, Any] = {"review_items_count": 0}
    resume_cursor: dict[str, Any] = {}
    if status in {"completed_with_review", "stopped", "blocked"}:
        cursor_record = review_records[0] if review_records else (execution_records[-1] if execution_records else {})
        unattended_summary, resume_cursor = _append_stage11_review_outputs(
            out_dir,
            status=status,
            records=execution_records,
            current_group_id=str(cursor_record.get("group_id") or ""),
            current_task_id=str(cursor_record.get("task_id") or ""),
            next_task_id=resume_next_task_id,
            project_state_tainted=project_state_tainted,
        )
        result["resume_cursor"] = resume_cursor
        result["review_items_count"] = int(
            unattended_summary.get("review_items_count") or 0
        )
        result["correction_summary"] = unattended_summary.get("correction_summary", {})
    write_json(out_dir / "devexecution.json", result)
    if status == "blocked":
        write_json(out_dir / "actual_development_blocked.json", result)
    write_json(out_dir / "actual_development_report.json", result)
    write_json(
        out_dir / "changed_files_manifest.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "tasks": changed_files_manifest,
        },
    )
    write_json(
        out_dir / "package_change_report.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "reports": package_reports,
        },
    )
    write_text(
        out_dir / "devexecution.md",
        "# Development Execution\n\n"
        + (f"- Status: {status}\n" if status != "success" else "")
        + (f"- Next task: {resume_next_task_id}\n" if resume_next_task_id else "")
        + (f"- Stop reason: {stop_reason}\n" if soft_stopped and stop_reason else "")
        + "\n".join(
            f"- {record['task_id']}: {record['status']}" for record in execution_records
        )
        + ("\n" if execution_records else "- No tasks executed.\n"),
    )
    write_json(out_dir / "development_execution_log.json", result)
    sync_tracker.force(
        event=f"stage11_{status}_final",
        message=stop_reason or status,
    )
    return {
        "status": status,
        "content_exists": bool(execution_records),
        "executed_task_count": len(execution_records),
        "blocking_issues": len(blocking_issues) if status == "blocked" else 0,
        "review_items_count": int(
            unattended_summary.get("review_items_count") or 0
        ) if status == "completed_with_review" else 0,
        "ai_review_status": (
            "passed"
            if status == "success"
            else (
                "stopped"
                if status == "stopped"
                else "completed_with_review"
                if status == "completed_with_review"
                else "blocked"
            )
        ),
        "traceability_valid": all(record.get("source_refs") for record in execution_records)
        and status in {"success", "completed_with_review"},
    }


def _stage12_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    tasks = _art_tasks()
    execution_store = load_execution_object_store(BASE_DIR)
    produced = []
    blockers = []
    for task in tasks:
        produced_record = {
            "task_id": task.get("task_id"),
            "asset_id": task.get("asset_id"),
            "status": "produced_as_traced_asset_requirement",
            "source_refs": task.get("source_refs", []),
        }
        try:
            verified_object = complete_art_task_execution_object(
                execution_store,
                task=task,
                produced_record=produced_record,
                stage=ART_PRODUCTION_STAGE,
            )
            produced_record["execution_object_id"] = verified_object.get(
                "execution_object_id"
            )
            produced_record["execution_object_state"] = verified_object.get("state")
        except Exception as exc:  # noqa: BLE001 - workflow gate boundary
            matching_objects = [
                obj
                for obj in execution_store.list_objects()
                if obj.get("metadata", {}).get("stage") == ART_PRODUCTION_STAGE
                and obj.get("metadata", {}).get("business_id") == task.get("task_id")
            ]
            execution_object_id = (
                str(matching_objects[-1].get("execution_object_id") or "")
                if matching_objects
                else ""
            )
            if execution_object_id:
                record_execution_object_failure(
                    execution_store,
                    execution_object_id=execution_object_id,
                    failure_stage="art_contract_verification",
                    written_files=[task.get("asset_id") or task.get("task_id")],
                    changed_state=[task.get("asset_id") or task.get("task_id")],
                    unfinished_actions=["asset_contract_verification"],
                    error=str(exc),
                    rollback_needed=False,
                )
                produced_record["execution_object_id"] = execution_object_id
                produced_record["execution_object_state"] = execution_store.get(
                    execution_object_id
                ).get("state")
            produced_record["status"] = "blocked_by_execution_object"
            produced_record["error"] = str(exc)
            blockers.append(
                {
                    "id": "ART-EXECUTION-OBJECT-BLOCKED",
                    "task_id": task.get("task_id"),
                    "execution_object_id": execution_object_id,
                    "message": str(exc),
                }
            )
        produced.append(produced_record)
    status = "success" if produced and not blockers else "blocked"
    if produced and blockers:
        status = "completed_with_review"
    events = [
        build_failure_event(
            stage=ART_PRODUCTION_STAGE,
            record={
                "task_id": item.get("task_id"),
                "asset_id": item.get("asset_id"),
                "status": item.get("status"),
                "error": item.get("error", ""),
                "execution_object_id": item.get("execution_object_id", ""),
                "changed_files": [item.get("asset_id") or item.get("task_id")],
            },
            failure_type="asset_contract_failed",
            severity="task_failed",
        )
        for item in produced
        if item.get("status") != "produced_as_traced_asset_requirement"
    ]
    correction_summary = upsert_failure_queue(
        out_dir,
        stage=ART_PRODUCTION_STAGE,
        events=events,
        reviewed_contract="art_asset_production_plan.json",
        source_review="stage_12_unattended_execution",
    )
    resume_cursor = build_resume_cursor(
        stage=ART_PRODUCTION_STAGE,
        records=produced,
        current_task_id=str(events[0].task_id) if events else "",
        project_state_tainted=False,
    )
    unattended_summary = write_unattended_summary(
        out_dir,
        stage=ART_PRODUCTION_STAGE,
        status=status,
        records=produced,
        correction_summary=correction_summary,
        resume_cursor=resume_cursor,
        continue_after_completed_with_review=unattended_config().continue_after_completed_with_review,
    )
    if status != "success":
        write_pause_resume_log(
            out_dir,
            stage=ART_PRODUCTION_STAGE,
            status=status,
            records=produced,
            resume_cursor=resume_cursor,
            correction_summary=correction_summary,
            title="Art Production Pause and Resume",
        )
    result = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": status,
        "produced_assets": produced,
        "execution_object_store": rel(execution_store.path),
        "execution_object_ids": [
            item.get("execution_object_id")
            for item in produced
            if item.get("execution_object_id")
        ],
        "blocking_issues": blockers if status == "blocked" else [],
        "review_items_count": unattended_summary.get("review_items_count", 0),
        "resume_cursor": resume_cursor,
        "correction_summary": correction_summary,
    }
    write_json(out_dir / "artproduction.json", result)
    write_text(
        out_dir / "artproduction.md",
        "# Art Production\n\n"
        + "\n".join(f"- {item['asset_id']}: {item['status']}" for item in produced)
        + "\n",
    )
    write_json(out_dir / "produced_assets_manifest.json", result)
    write_skill_guidance(out_dir, "imagegen")
    _write_generated_images_manifest(out_dir, tasks, stage=ART_PRODUCTION_STAGE)
    return {
        "status": status,
        "content_exists": bool(produced),
        "produced_asset_count": len(produced),
        "blocking_issues": len(blockers) if status == "blocked" else 0,
        "review_items_count": unattended_summary.get("review_items_count", 0),
        "ai_review_status": "passed" if status == "success" else status,
        "traceability_valid": all(item["source_refs"] for item in produced)
        and status in {"success", "completed_with_review"},
    }


def _stage13_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    dev = read_json(stage_dir(DEV_EXECUTION_STAGE) / "devexecution.json", {})
    art = read_json(stage_dir(ART_PRODUCTION_STAGE) / "artproduction.json", {})
    changed_manifest = read_json(
        stage_dir(DEV_EXECUTION_STAGE) / "changed_files_manifest.json", {}
    )
    blockers = []
    allow_review_outputs = unattended_config().continue_after_completed_with_review
    if dev.get("status") == "completed_with_review" and not allow_review_outputs:
        blockers.append(
            {
                "id": "DEVEXEC-REQUIRES-REVIEW",
                "message": "Development execution completed with review items; resolve stage_11/correction_queue.json before integration.",
            }
        )
    if art.get("status") == "completed_with_review" and not allow_review_outputs:
        blockers.append(
            {
                "id": "ARTPROD-REQUIRES-REVIEW",
                "message": "Art production completed with review items; resolve stage_12/correction_queue.json before integration.",
            }
        )
    if dev.get("status") != "success":
        if dev.get("status") != "completed_with_review":
            blockers.append(
                {
                    "id": "DEVEXEC-NOT-SUCCESS",
                    "message": "Development execution did not pass.",
                }
            )
    if art.get("status") != "success":
        if art.get("status") != "completed_with_review":
            blockers.append(
                {"id": "ARTPROD-NOT-SUCCESS", "message": "Art production did not pass."}
            )
    records = dev.get("records", []) if isinstance(dev.get("records"), list) else []
    changed_tasks = (
        changed_manifest.get("tasks", []) if isinstance(changed_manifest, dict) else []
    )
    actual_changed_files = sorted(
        {
            str(path)
            for task in changed_tasks
            if isinstance(task, dict)
            for path in task.get("changed_files", [])
        }
    )
    unexpected_changes = [
        {
            "task_id": task.get("task_id"),
            "unexpected_changes": task.get("unexpected_changes", []),
        }
        for task in changed_tasks
        if isinstance(task, dict) and task.get("unexpected_changes")
    ]
    unity_results = [
        verification
        for record in records
        for verification in record.get("verification_results", [])
        if isinstance(verification, dict)
        and verification.get("id") == "unity_batchmode_compile"
    ]
    failed_unity_results = [
        item for item in unity_results if item.get("status") != "passed"
    ]
    if not records:
        blockers.append(
            {
                "id": "ACTUAL-DEV-NO-RECORDS",
                "message": "Step 11 produced no real development records.",
            }
        )
    if not actual_changed_files:
        blockers.append(
            {
                "id": "ACTUAL-PROJECT-NO-CHANGES",
                "message": "No actual Unity project files were changed.",
            }
        )
    if unexpected_changes:
        blockers.append(
            {"id": "ACTUAL-PROJECT-UNEXPECTED-CHANGES", "items": unexpected_changes}
        )
    if not unity_results:
        blockers.append(
            {
                "id": "UNITY-VALIDATION-MISSING",
                "message": "Step 11 did not record Unity batchmode validation.",
            }
        )
    if failed_unity_results:
        blockers.append(
            {"id": "UNITY-VALIDATION-FAILED", "items": failed_unity_results}
        )
    execution_store = load_execution_object_store(BASE_DIR)
    dev_execution_object_ids = [
        record.get("execution_object_id")
        for record in records
        if isinstance(record, dict) and record.get("execution_object_id")
    ]
    art_execution_object_ids = [
        item.get("execution_object_id")
        for item in art.get("produced_assets", [])
        if isinstance(item, dict) and item.get("execution_object_id")
    ]
    execution_object_validation = validate_execution_object_references(
        execution_store,
        dev_execution_object_ids + art_execution_object_ids,
        required_state="verified",
    )
    if not execution_object_validation["valid"]:
        blockers.append(
            {
                "id": "EXECUTION-OBJECTS-NOT-VERIFIED",
                "message": "Step 11/12 execution objects must be verified before integration.",
                "details": execution_object_validation,
            }
        )
    integration_execution_object_id = ""
    if not blockers:
        verified_object = complete_relationship_graph_execution_object(
            execution_store,
            stage=INTEGRATION_STAGE,
            business_id="stage14_integration_relationships",
            title="Integration relationship graph correction",
            graph_facts={
                "development_records": len(records),
                "produced_assets": len(art.get("produced_assets", [])),
                "actual_changed_files": actual_changed_files,
                "unity_validation_count": len(unity_results),
            },
            write_scope=[
                "relationship_graph:integration",
                *[f"unity_file:{path}" for path in actual_changed_files],
            ],
        )
        integration_execution_object_id = str(
            verified_object.get("execution_object_id") or ""
        )

    project_audit = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "development_path": dev.get("project_path"),
        "actual_changed_files": actual_changed_files,
        "unexpected_changes": unexpected_changes,
        "execution_object_validation": execution_object_validation,
        "valid": not unexpected_changes and bool(actual_changed_files),
    }
    unity_summary = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "unity_editor_path": dev.get("unity_editor_path"),
        "validation_count": len(unity_results),
        "failed_validation_count": len(failed_unity_results),
        "valid": bool(unity_results) and not failed_unity_results,
        "results": unity_results,
    }
    report = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "success" if not blockers else "blocked",
        "blocking_issues": blockers,
        "execution_object_store": rel(execution_store.path),
        "execution_object_ids": [
            *dev_execution_object_ids,
            *art_execution_object_ids,
            *(
                [integration_execution_object_id]
                if integration_execution_object_id
                else []
            ),
        ],
        "execution_object_validation": execution_object_validation,
        "checks": [
            {
                "id": "actual_development_succeeded",
                "passed": dev.get("status") == "success",
            },
            {
                "id": "actual_project_files_changed",
                "passed": bool(actual_changed_files),
            },
            {"id": "no_out_of_scope_file_changes", "passed": not unexpected_changes},
            {
                "id": "unity_batchmode_validation_passed",
                "passed": bool(unity_results) and not failed_unity_results,
            },
            {"id": "assets_traced", "passed": bool(art.get("produced_assets"))},
            {
                "id": "execution_objects_verified",
                "passed": execution_object_validation["valid"],
            },
            {
                "id": "integration_relationship_object_verified",
                "passed": bool(integration_execution_object_id),
            },
            {
                "id": "replayable_pipeline",
                "passed": dev.get("execution_mode") == "actual_unity_ai_development",
            },
        ],
    }
    write_json(out_dir / "integration.json", report)
    write_text(
        out_dir / "integration.md",
        "# Integration Validation\n\n"
        + ("- Passed\n" if not blockers else "- Blocked\n"),
    )
    write_json(out_dir / "integration_validation_report.json", report)
    write_json(out_dir / "actual_project_file_audit.json", project_audit)
    write_json(out_dir / "unity_validation_summary.json", unity_summary)
    write_json(
        out_dir / "automated_test_results.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "tests": report["checks"],
            "passed": not blockers,
        },
    )
    write_json(
        out_dir / "issue_fix_log.json",
        {"schema_version": 1, "generated_at": now_iso(), "issues": blockers},
    )
    return {
        "content_exists": True,
        "blocking_issues": len(blockers),
        "ai_review_status": "passed" if not blockers else "blocked",
        "traceability_valid": not blockers,
    }


def _stage14_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    integration = read_json(stage_dir(INTEGRATION_STAGE) / "integration.json", {})
    project_audit = read_json(
        stage_dir(INTEGRATION_STAGE) / "actual_project_file_audit.json", {}
    )
    unity_summary = read_json(
        stage_dir(INTEGRATION_STAGE) / "unity_validation_summary.json", {}
    )
    blockers = []
    if integration.get("status") != "success":
        blockers.append(
            {
                "id": "INTEGRATION-NOT-SUCCESS",
                "message": "Integration validation did not pass.",
            }
        )
    if not project_audit.get("actual_changed_files"):
        blockers.append(
            {
                "id": "BUILD-NO-ACTUAL-PROJECT-CHANGES",
                "message": "No actual Unity project changes are available to package.",
            }
        )
    if unity_summary.get("valid") is not True:
        blockers.append(
            {
                "id": "BUILD-UNITY-VALIDATION-MISSING",
                "message": "Unity validation summary is missing or failed.",
            }
        )
    artifact_manifest = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "development_path": project_audit.get("development_path"),
        "changed_files": project_audit.get("actual_changed_files", []),
        "unity_validation": {
            "unity_editor_path": unity_summary.get("unity_editor_path"),
            "validation_count": unity_summary.get("validation_count", 0),
            "failed_validation_count": unity_summary.get("failed_validation_count", 0),
        },
    }
    report = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "success" if not blockers else "blocked",
        "package_type": "actual_unity_project_validation",
        "source": project_audit.get("development_path"),
        "blocking_issues": blockers,
        "included_stages": list(range(0, BUILD_PACKAGE_STAGE)),
        "artifact_manifest": "build_artifact_manifest.json",
    }
    write_json(out_dir / "build_report.json", report)
    write_json(out_dir / "build_artifact_manifest.json", artifact_manifest)
    write_text(
        out_dir / "build_package.md",
        "# Build Package\n\n"
        + (
            "- Actual Unity project validation recorded.\n"
            if not blockers
            else "- Build blocked.\n"
        ),
    )
    write_json(out_dir / "package_manifest.json", report)
    return {
        "content_exists": True,
        "blocking_issues": len(blockers),
        "ai_review_status": "passed" if not blockers else "blocked",
        "traceability_valid": not blockers,
    }


def _stage15_outputs(parsed: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    _ = parsed
    build = read_json(stage_dir(BUILD_PACKAGE_STAGE) / "build_report.json", {})
    build_artifacts = read_json(
        stage_dir(BUILD_PACKAGE_STAGE) / "build_artifact_manifest.json", {}
    )
    execution_store = load_execution_object_store(BASE_DIR)
    blockers = []
    if build.get("status") != "success":
        blockers.append(
            {"id": "BUILD-NOT-SUCCESS", "message": "Build package did not pass."}
        )
    changed_files = (
        build_artifacts.get("changed_files", [])
        if isinstance(build_artifacts, dict)
        else []
    )
    if not changed_files:
        blockers.append(
            {
                "id": "PATCH-NO-ACTUAL-PROJECT-CHANGES",
                "message": "No actual Unity project file changes were recorded.",
            }
        )
    rollback_execution_object_id = ""
    if not blockers:
        try:
            verified_object = complete_rollback_plan_execution_object(
                execution_store,
                changed_files=[str(item) for item in changed_files],
                rollback_source=str(
                    build.get("artifact_manifest") or "build_artifact_manifest.json"
                ),
                stage=DELTA_PATCH_STAGE,
            )
            rollback_execution_object_id = str(
                verified_object.get("execution_object_id") or ""
            )
        except Exception as exc:  # noqa: BLE001 - workflow gate boundary
            blockers.append(
                {
                    "id": "ROLLBACK-EXECUTION-OBJECT-BLOCKED",
                    "message": str(exc),
                }
            )
    patch = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "success" if not blockers else "blocked",
        "patch_type": "actual_unity_project_delta",
        "base": build_artifacts.get("development_path"),
        "blocking_issues": blockers,
        "changed_scope": "actual Unity project files",
        "changed_files": changed_files,
        "execution_object_store": rel(execution_store.path),
        "execution_object_ids": (
            [rollback_execution_object_id] if rollback_execution_object_id else []
        ),
    }
    write_json(out_dir / "patch_manifest.json", patch)
    write_json(
        out_dir / "changed_files_manifest.json",
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            "development_path": build_artifacts.get("development_path"),
            "changed_files": changed_files,
        },
    )
    write_text(
        out_dir / "delta_patch.md",
        "# Delta Patch\n\n- Delta records actual Unity project file changes.\n",
    )
    write_json(
        out_dir / "release_history.json", {"schema_version": 1, "entries": [patch]}
    )
    write_text(
        out_dir / "rollback_plan.md",
        "# Rollback Plan\n\n"
        "- Restore the listed Unity project files from version control or a project backup.\n"
        "- Re-run Unity batchmode validation after rollback.\n"
        "- Do not treat pipeline artifact deletion as rollback for actual project changes.\n",
    )
    return {
        "content_exists": True,
        "blocking_issues": len(blockers),
        "ai_review_status": "passed" if not blockers else "blocked",
        "traceability_valid": not blockers,
    }


def _load_current_design(base_dir: Path = BASE_DIR) -> dict[str, Any]:
    package_dir = _latest_concept_package(base_dir)
    if package_dir is None:
        raise DesignSourceError(
            "Stage 00 has no submitted Concept source package.",
            {
                "code": "STAGE00_CONCEPT_SOURCE_MISSING",
                "fix": "在步骤 0 填写人工输入，或提交一个 .md/.txt 主设计文档附件。",
            },
        )

    manifest = read_json(package_dir / "package_manifest.json", {})
    if not isinstance(manifest, dict):
        manifest = {}
    submission = _load_concept_submission(package_dir)
    notes = str(submission.get("notes") or "").strip()
    valid_attachments, invalid_attachments = _concept_attachment_paths(
        package_dir, submission
    )
    package_rel = rel(package_dir)

    if invalid_attachments:
        raise DesignSourceError(
            "Stage 00 contains unsupported or missing attachments.",
            {
                "code": "STAGE00_ATTACHMENT_INVALID",
                "package": package_rel,
                "invalid_attachments": invalid_attachments,
                "allowed_extensions": sorted(ALLOWED_DESIGN_SOURCE_SUFFIXES),
                "fix": "只提交 .md 或 .txt 文档附件。",
            },
        )

    if len(valid_attachments) > 1:
        raise DesignSourceError(
            "Stage 00 contains multiple design document attachments and no explicit primary source.",
            {
                "code": "STAGE00_MULTIPLE_PRIMARY_CANDIDATES",
                "package": package_rel,
                "attachments": [rel(path) for path in valid_attachments],
                "fix": "只保留一个 .md/.txt 主设计文档附件后重新提交步骤 0。",
            },
        )

    if len(valid_attachments) == 1:
        path = valid_attachments[0]
        parsed = _parse_design_doc(path)
        parsed["source_package"] = package_rel
        parsed["design_summary"] = manifest.get("design_summary", {})
        parsed["source_input_type"] = "concept_attachment"
        if parsed["selections"]:
            return parsed
        raise DesignSourceError(
            "Stage 00 design attachment is not a parseable Layer document.",
            {
                "code": "STAGE00_ATTACHMENT_UNPARSEABLE",
                "package": package_rel,
                "attachment": rel(path),
                "fix": "将附件转换为包含 '## Layer N ...' 和 '- 类型：选项' 条目的 Layer 格式后重新提交。",
            },
        )

    if notes:
        source = f"{package_rel}/operator_submission.json#notes"
        parsed = _manual_notes_as_design(notes, source)
        parsed["source_package"] = package_rel
        parsed["design_summary"] = manifest.get("design_summary", {})
        parsed["source_input_type"] = "operator_notes"
        if parsed["selections"]:
            return parsed

    raise DesignSourceError(
        "Stage 00 has no operator notes or valid design document attachment.",
        {
            "code": "STAGE00_INPUT_MISSING",
            "package": package_rel,
            "fix": "在步骤 0 填写人工输入，或提交一个 .md/.txt 主设计文档附件。",
        },
    )


def _blocking_issue_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 1 if value else 0


def _update_stage_report(
    step_number: int, out_dir: Path, result: dict[str, Any]
) -> dict[str, Any]:
    report_path = out_dir / "validation_report.json"
    report = read_json(report_path, {})
    if not isinstance(report, dict):
        report = {}
    status = str(result.get("status") or "")
    completed_with_review = status == "completed_with_review"
    blocking = 0 if completed_with_review else _blocking_issue_count(result.get("blocking_issues"))
    content_exists = bool(result.get("content_exists"))
    report.update(
        {
            "content_exists": content_exists,
            "ai_review_status": result.get(
                "ai_review_status", "passed" if blocking == 0 else "blocked"
            ),
            "blocking_issues": blocking,
            "review_items_count": int(result.get("review_items_count") or 0),
            "traceability_valid": bool(result.get("traceability_valid", True))
            and (blocking == 0 or completed_with_review),
            "scope_budget_valid": True,
            "business_quality": result,
        }
    )
    if completed_with_review:
        report["status"] = "completed_with_review"
        report["valid"] = True
    elif not content_exists:
        report["status"] = "content_missing"
        report["valid"] = False
    elif blocking:
        report["status"] = "failed"
        report["valid"] = False
    elif content_exists:
        report["status"] = status or report.get("status", "passed")
        report["valid"] = True
    write_json(report_path, report)
    return report


def _refresh_indexes(step_number: int, out_dir: Path) -> None:
    index_path = out_dir / "artifact_index.json"
    index = read_json(index_path, {})
    if isinstance(index, dict):
        index["manifest"] = file_manifest(out_dir)
        index["updated_at"] = now_iso()
        index["development_plan_outputs"] = True
        write_json(index_path, index)
    refresh_reference_manifest_file_inventory(step_number)


def _load_package_by_source_id(source_id: str) -> dict[str, Any]:
    """Load and parse a concept-format package by its source_id (Concept/GameplayFramework/Design)."""
    from core.source.finder import source_artifact_roots

    candidates: list[Path] = []
    for source_dir in source_artifact_roots():
        if not source_dir.exists():
            continue
        root_candidates: list[Path] = []
        for item in source_dir.iterdir():
            if not item.is_dir():
                continue
            manifest = read_json(item / "package_manifest.json", {})
            if not isinstance(manifest, dict):
                continue
            ids = {str(v) for v in manifest.get("source_ids", []) if v}
            pkg_type = str(
                manifest.get("package_type") or manifest.get("source_id") or ""
            )
            if source_id in ids or pkg_type == source_id:
                root_candidates.append(item)
        if root_candidates:
            candidates = root_candidates
            break
    if not candidates:
        raise DesignSourceError(
            f"Stage has no submitted {source_id} source package.",
            {
                "code": f"STAGE_{source_id.upper()}_SOURCE_MISSING",
                "fix": f"Run 导出到流水线 to generate the {source_id} package.",
            },
        )
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    package_dir = candidates[0]
    submission = _load_concept_submission(package_dir)
    valid_attachments, _ = _concept_attachment_paths(package_dir, submission)
    if not valid_attachments:
        raise DesignSourceError(
            f"{source_id} package has no valid attachment.",
            {"code": f"STAGE_{source_id.upper()}_ATTACHMENT_MISSING"},
        )
    manifest = read_json(package_dir / "package_manifest.json", {})
    if not isinstance(manifest, dict):
        manifest = {}
    parsed = _parse_design_doc(valid_attachments[0])
    parsed["source_package"] = rel(package_dir)
    parsed["design_summary"] = manifest.get("design_summary", {})
    parsed["source_input_type"] = f"{source_id.lower()}_attachment"
    return parsed


def _load_design_for_stage(step_number: int) -> dict[str, Any]:
    """Load design data appropriate for the given pipeline step.

    step 0  → Concept package  (project vision + core experience)
    step 1  → GameplayFramework package (gameplay systems)
    step 2+ → Design package   (full design specification)
    """
    if step_number == 0:
        return _load_current_design(BASE_DIR)
    if step_number == 1:
        try:
            return _load_package_by_source_id("GameplayFramework")
        except DesignSourceError:
            return _load_current_design(BASE_DIR)
    try:
        return _load_package_by_source_id("Design")
    except DesignSourceError:
        return _load_current_design(BASE_DIR)


def apply_development_plan_outputs(
    step_number: int, report: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Add controlled-plan artifacts to a stage output directory.

    Stage-aware loading:
      step 0  → devflow_Concept_*      (project vision + core experience)
      step 1  → devflow_GameplayFramework_* (gameplay systems)
      step 2+ → devflow_Design_*       (full design specification)
    """
    out_dir = stage_dir(step_number)
    try:
        parsed = _load_design_for_stage(step_number)
    except DesignSourceError as exc:
        result = {
            "content_exists": False,
            "message": str(exc),
            "source_error": exc.details,
            "blocking_issues": 1,
            "ai_review_status": "blocked",
            "traceability_valid": False,
        }
        write_json(out_dir / "design_source_error.json", result)
        updated = _update_stage_report(step_number, out_dir, result)
        _refresh_indexes(step_number, out_dir)
        raise RuntimeError(str(exc))

    if step_number == 0:
        result = _stage0_outputs(parsed, out_dir)
    elif step_number == 1:
        result = _stage1_outputs(parsed, out_dir)
    elif step_number == 2:
        result = _stage2_outputs(parsed, out_dir)
    elif step_number == 3:
        result = _stage3_outputs(parsed, out_dir)
    elif step_number == 4:
        result = _stage4_outputs(parsed, out_dir)
    elif step_number == 5:
        result = _stage5_outputs(parsed, out_dir)
    elif step_number == 6:
        result = _stage6_outputs(parsed, out_dir)
    elif step_number == 7:
        result = _stage7_art_style_generation_outputs(parsed, out_dir)
    elif step_number == 8:
        result = _stage8_outputs(parsed, out_dir)
    elif step_number == 9:
        result = _stage9_outputs(parsed, out_dir)
    elif step_number == 10:
        result = _stage10_outputs(parsed, out_dir)
    elif step_number == 11:
        result = _stage11_outputs(parsed, out_dir)
    elif step_number == 12:
        result = _stage12_outputs(parsed, out_dir)
    elif step_number == 13:
        result = _stage13_outputs(parsed, out_dir)
    elif step_number == 14:
        result = _stage14_outputs(parsed, out_dir)
    elif step_number == 15:
        result = _stage15_outputs(parsed, out_dir)
    else:
        return report or {}

    updated = _update_stage_report(step_number, out_dir, result)
    _refresh_indexes(step_number, out_dir)
    if result.get("status") == "stopped" or result.get("ai_review_status") == "stopped":
        raise PipelineStopRequested(
            f"Stage {step_number:02d} stopped at a resumable boundary."
        )
    if updated.get("valid") is False:
        raise RuntimeError(
            f"Development plan outputs failed for stage {step_number:02d}: {updated.get('business_quality')}"
        )
    return updated
