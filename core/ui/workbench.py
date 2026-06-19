#!/usr/bin/env python3
"""Desktop workbench helpers for the no-agent-runtime pipeline."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from tools.process_utils import child_process_env, hidden_subprocess_kwargs
from core.save import manager as save_manager
from tools.execution_object_paths import execution_object_store_path
from tools.actual_development_preflight import run_actual_development_preflight
from tools import runtime_control


PROJECT_NAME = "devflow"
PROJECT_DISPLAY_NAME = "程序自动开发流程工具"
APP_DISPLAY_NAME = "程序自动开发流程工具"


STATUS_DISPLAY_NAMES = {
    "success": "通过",
    "passed": "通过",
    "pass": "通过",
    "ok": "正常",
    "valid": "有效",
    "failed": "失败",
    "failure": "失败",
    "fail": "失败",
    "error": "错误",
    "warning": "警告",
    "missing": "未生成",
    "not_found": "未找到",
    "pending": "待处理",
    "running": "运行中",
    "incomplete": "未完成",
    "interrupted": "已中断",
    "stopped": "已停止",
    "skipped": "已跳过",
    "unknown": "未知",
}

PACKAGE_DISPLAY_NAMES = {
    "Concept": "初始玩法资料包",
    "GameplayFramework": "玩法框架资料包",
    "SubsystemDesign": "子系统设计资料包",
    "AIDesignScript": "AI 理解脚本资料包",
    "Design": "冻结设计资料包",
    "DevelopmentDesign": "开发系统设计资料包",
    "ProgReq": "程序需求资料包",
    "ArtReq": "美术需求资料包",
    "ProgReview": "程序需求评审资料包",
    "ArtReview": "美术需求评审资料包",
    "Plans": "程序开发计划资料包",
    "ArtPlans": "美术制作计划资料包",
    "Alignment": "资产对齐资料包",
    "DevExecution": "程序执行记录资料包",
    "ArtProduction": "美术制作记录资料包",
    "Integration": "集成验证资料包",
    "Build": "构建打包资料包",
    "DeltaPatch": "差量补丁资料包",
    "Patch": "补丁资料包",
}

PACKAGE_SHORT_NAMES = {
    "Concept": "cpt",
    "GameplayFramework": "gpf",
    "SubsystemDesign": "sub",
    "AIDesignScript": "ais",
    "Design": "des",
    "DevelopmentDesign": "devd",
    "ProgReq": "preq",
    "ArtReq": "areq",
    "ProgReview": "prev",
    "ArtReview": "arev",
    "Plans": "plan",
    "ArtPlans": "apln",
    "Alignment": "align",
    "DevExecution": "devx",
    "ArtProduction": "artx",
    "Integration": "int",
    "Build": "bld",
    "DeltaPatch": "patch",
}

ALLOWED_DOCUMENT_ATTACHMENT_SUFFIXES = {".md", ".txt"}


@dataclass(frozen=True)
class StageInteraction:
    number: int
    slug: str
    title: str
    human_goal: str
    operator_actions: tuple[str, ...]
    decision_questions: tuple[str, ...]
    source_patterns: tuple[str, ...]
    package_prefixes: tuple[str, ...]


STAGES: tuple[StageInteraction, ...] = (
    StageInteraction(
        0,
        "idea_intake",
        "初始想法输入",
        "把操作者的一句话玩法、长文档或附件整理成当前项目的玩法原型输入。",
        (
            "输入核心玩法描述，或附加一个设计文档。",
            "确认玩家扮演什么、核心循环是什么、希望保留哪些限制。",
            "提交后生成初始玩法资料包，再运行第 00 阶段。",
        ),
        (
            "玩家是谁，玩家的核心目标是什么？",
            "30 秒内反复发生的核心动作循环是什么？",
            "这个玩法最不能被改掉的设计点是什么？",
            "当前是否同意把该想法作为本项目的输入源？",
        ),
        ("devflow_Concept_*",),
        ("Concept",),
    ),
    StageInteraction(
        1,
        "gameplay_framework",
        "玩法框架确认",
        "把已选玩法原型扩展为可讨论的玩法框架，并由操作者确认或要求返工。",
        (
            "描述核心循环、成长节奏、胜负条件和主要系统边界。",
            "列出需要进入后续设计的子系统。",
            "提交后生成玩法框架资料包，再运行第 01 阶段。",
        ),
        (
            "当前玩法框架是否已经足够支撑后续系统拆解？",
            "哪些子系统必须进入设计队列？",
            "哪些玩法方向明确禁止继续发散？",
        ),
        ("devflow_GameplayFramework_*",),
        ("GameplayFramework",),
    ),
    StageInteraction(
        2,
        "design_review",
        "设计评审冻结",
        "把子系统设计、AI 理解脚本、冻结设计和开发系统设计整理成设计冻结包。",
        (
            "逐个确认子系统职责、输入输出、边界和验收条件。",
            "确认设计冻结文本，不允许后续阶段随意重构核心玩法。",
            "提交后生成子系统设计、AI 理解脚本、冻结设计、开发系统设计四类资料包。",
        ),
        (
            "每个子系统是否有清晰职责和边界？",
            "冻结设计是否已经覆盖核心玩法、循环、资源、反馈和失败条件？",
            "开发系统设计是否能支撑程序需求拆解？",
        ),
        (
            "devflow_SubsystemDesign_*",
            "devflow_AIDesignScript_*",
            "devflow_Design_*",
            "devflow_DevelopmentDesign_*",
        ),
        ("SubsystemDesign", "AIDesignScript", "Design", "DevelopmentDesign"),
    ),
    StageInteraction(
        3,
        "program_requirements",
        "程序需求确认",
        "把冻结设计转成系统、实体、事件、接口契约和验收条件。",
        (
            "补充或确认系统清单、实体模型、接口契约、验收条件。",
            "指出哪些内容属于阻断项，哪些只是建议项。",
            "提交后生成程序需求资料包，再运行第 03 阶段。",
        ),
        (
            "程序需求是否覆盖所有核心玩法系统？",
            "数据实体和契约是否能被开发者直接执行？",
            "是否存在需要回到设计冻结阶段修正的问题？",
        ),
        ("devflow_ProgReq_*",),
        ("ProgReq",),
    ),
    StageInteraction(
        4,
        "art_requirements",
        "美术需求确认",
        "把冻结设计转成原画、UI、特效和资产规格需求。",
        (
            "确认视觉风格、资产清单、UI 信息结构和特效反馈。",
            "补充禁止漂移的风格规则。",
            "提交后生成美术需求资料包，再运行第 04 阶段。",
        ),
        (
            "视觉风格是否足够明确？",
            "资产清单是否覆盖玩法必需反馈？",
            "哪些素材不能复用或不能风格漂移？",
        ),
        ("devflow_ArtReq_*",),
        ("ArtReq",),
    ),
    StageInteraction(
        5,
        "program_review",
        "程序需求评审",
        "人工审查程序需求是否完整、一致、可执行。",
        (
            "记录阻断项、警告项和可放行项。",
            "确认通过、失败或带风险放行。",
            "提交后生成程序需求评审资料包，再运行第 05 阶段。",
        ),
        (
            "是否存在阻断开发的需求缺口？",
            "接口、实体、系统之间是否一致？",
            "是否允许进入程序计划阶段？",
        ),
        ("devflow_ProgReview_*",),
        ("ProgReview",),
    ),
    StageInteraction(
        6,
        "art_review",
        "美术需求评审",
        "人工审查美术需求是否完整、风格一致、资产规格可执行。",
        (
            "记录风格漂移、缺失素材、规格不清和复用风险。",
            "确认通过、失败或带风险放行。",
            "提交后生成美术需求评审资料包，再运行第 06 阶段。",
        ),
        (
            "是否存在阻断制作的美术需求缺口？",
            "资产规格是否能被制作人员直接执行？",
            "是否允许进入美术计划阶段？",
        ),
        ("devflow_ArtReview_*",),
        ("ArtReview",),
    ),
    StageInteraction(
        7,
        "program_plan",
        "程序开发计划",
        "把程序需求拆成可执行开发任务和依赖顺序。",
        (
            "确认开发任务、依赖关系、目标文件、验收方式。",
            "标记高风险任务和必须先完成的基础模块。",
            "提交后生成程序开发计划资料包，再运行第 07 阶段。",
        ),
        (
            "任务顺序是否符合依赖关系？",
            "每个任务是否有明确输出文件或模块？",
            "是否允许进入资产对齐？",
        ),
        ("devflow_Plans_*",),
        ("Plans",),
    ),
    StageInteraction(
        8,
        "art_plan",
        "美术制作计划",
        "把美术需求拆成可执行制作任务和交付顺序。",
        (
            "确认每个资产的制作任务、规格、优先级、复用策略。",
            "标记风格风险和必须人工审看的资产。",
            "提交后生成美术制作计划资料包，再运行第 08 阶段。",
        ),
        (
            "资产优先级是否符合玩法验证需要？",
            "每个资产是否有明确规格和用途？",
            "是否允许进入资产对齐？",
        ),
        ("devflow_ArtPlans_*",),
        ("ArtPlans",),
    ),
    StageInteraction(
        9,
        "asset_alignment",
        "资产契约对齐",
        "对齐程序引用和美术资产交付，解决路径、命名、覆盖和冲突。",
        (
            "确认程序资产引用、艺术资产输出和缺口分析。",
            "人工裁决命名冲突、缺失资产、替代策略。",
            "提交后生成资产对齐资料包，再运行第 09 阶段。",
        ),
        (
            "程序和美术资产是否一一对应？",
            "冲突项是否已经人工裁决？",
            "是否允许进入开发执行和美术制作？",
        ),
        ("devflow_Alignment_*",),
        ("Alignment",),
    ),
    StageInteraction(
        10,
        "dev_execution",
        "程序开发执行",
        "记录程序开发结果、编译检查、代码审查和风险。",
        (
            "确认完成的模块、失败项、编译结果、待修复缺陷。",
            "提交后生成程序执行记录资料包，再运行第 10 阶段。",
        ),
        (
            "开发输出是否满足计划验收？",
            "是否有阻断集成的问题？",
            "是否允许进入集成验证？",
        ),
        ("devflow_DevExecution_*",),
        ("DevExecution",),
    ),
    StageInteraction(
        11,
        "art_production",
        "美术制作执行",
        "记录美术制作结果、质检、缺失资产和人工审看结论。",
        (
            "确认完成资产、质量问题、风格偏差、待补素材。",
            "提交后生成美术制作记录资料包，再运行第 11 阶段。",
        ),
        (
            "美术输出是否满足计划验收？",
            "是否有阻断集成的问题？",
            "是否允许进入集成验证？",
        ),
        ("devflow_ArtProduction_*",),
        ("ArtProduction",),
    ),
    StageInteraction(
        12,
        "integration_validation",
        "集成验证",
        "验证程序和美术产物能否按契约集成。",
        (
            "确认集成通过项、失败项、缺失项、回退策略。",
            "提交后生成集成验证资料包，再运行第 12 阶段。",
        ),
        (
            "所有关键契约是否被覆盖？",
            "失败项是否需要回退到开发或美术制作？",
            "是否允许进入构建打包？",
        ),
        ("devflow_Integration_*",),
        ("Integration",),
    ),
    StageInteraction(
        13,
        "build_package",
        "构建打包",
        "记录构建配置、构建产物、版本号和打包验证。",
        (
            "确认构建版本、目标平台、构建产物和运行检查。",
            "提交后生成构建打包资料包，再运行第 13 阶段。",
        ),
        (
            "构建产物是否存在并可运行？",
            "版本和配置是否正确？",
            "是否允许进入差量补丁阶段？",
        ),
        ("devflow_Build_*",),
        ("Build",),
    ),
    StageInteraction(
        14,
        "delta_patch",
        "差量补丁",
        "记录差量补丁内容、发布历史、文件哈希和验证结论。",
        (
            "确认补丁包含哪些变更、如何回滚、是否影响已有版本。",
            "提交后生成差量补丁资料包，再运行第 14 阶段。",
        ),
        (
            "补丁文件是否存在？",
            "更新清单和哈希是否匹配？",
            "是否允许进入最终审计？",
        ),
        ("devflow_DeltaPatch_*",),
        ("DeltaPatch",),
    ),
    StageInteraction(
        15,
        "migration_audit",
        "最终审计",
        "审查所有阶段产物、治理层验证和项目独立性状态。",
        (
            "查看最终审计报告。",
            "确认无缺失阶段报告、无失败产物层、无旧项目输入输出引用。",
            "运行第 15 阶段后读取最终审计报告。",
        ),
        (
            "是否所有阶段都成功？",
            "是否仍有旧项目命名、旧路径或旧输入输出风险？",
            "是否允许把当前结果视为完成状态？",
        ),
        (),
        (),
    ),
)


STAGE_BY_NUMBER = {stage.number: stage for stage in STAGES}


def display_status(value: Any) -> str:
    if value is None:
        return "未记录"
    if isinstance(value, bool):
        return display_bool(value)
    raw = str(value).strip()
    if not raw:
        return "未记录"
    return STATUS_DISPLAY_NAMES.get(raw.lower(), raw)


def display_bool(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    if value is None:
        return "未记录"
    return str(value)


def display_package_prefix(prefix: str) -> str:
    return PACKAGE_DISPLAY_NAMES.get(prefix, prefix)


def display_group_name(value: Any) -> str:
    raw = str(value).strip()
    if not raw:
        return "未命名资料组"
    for prefix, label in PACKAGE_DISPLAY_NAMES.items():
        if raw == prefix or raw.lower() == prefix.lower() or prefix.lower() in raw.lower():
            return label
    return raw


def source_requirement_labels(stage: StageInteraction) -> list[str]:
    labels: list[str] = []
    for prefix in stage.package_prefixes:
        label = display_package_prefix(prefix)
        if label not in labels:
            labels.append(label)
    if labels:
        return labels

    for pattern in stage.source_patterns:
        label = display_group_name(pattern)
        if label not in labels:
            labels.append(label)
    return labels


def package_output_labels(stage: StageInteraction) -> list[str]:
    return [display_package_prefix(prefix) for prefix in stage.package_prefixes]


def _norm_source_id(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _package_version_from_path(path: Path) -> int:
    match = re.search(r"_v(\d+)$", path.name)
    return int(match.group(1)) if match else 0


def source_package_metadata(path: Path) -> dict[str, Any]:
    manifest = read_json(path / "package_manifest.json", {})
    if isinstance(manifest, dict) and manifest:
        return manifest
    submission = read_json(path / "operator_submission.json", {})
    return submission if isinstance(submission, dict) else {}


def infer_source_ids(path: Path) -> tuple[str, ...]:
    ids: list[str] = []
    metadata = source_package_metadata(path)
    for key in ("source_id", "package_id", "package_type", "package_type_id", "prefix"):
        value = metadata.get(key)
        if value:
            ids.append(str(value))
    raw_ids = metadata.get("source_ids")
    if isinstance(raw_ids, list):
        ids.extend(str(item) for item in raw_ids)
    for prefix in PACKAGE_DISPLAY_NAMES:
        if f"_{prefix}_" in path.name or path.name.startswith(f"{prefix}_"):
            ids.append(prefix)
    return tuple(dict.fromkeys(ids))


def source_matches_ids(path: Path, expected_ids: Iterable[str]) -> bool:
    expected = {_norm_source_id(item) for item in expected_ids if item}
    actual = {_norm_source_id(item) for item in infer_source_ids(path)}
    return bool(expected & actual)


def source_sort_key(path: Path) -> tuple[str, int, float, str]:
    metadata = source_package_metadata(path)
    created_at = str(metadata.get("created_at") or metadata.get("timestamp") or "")
    version = metadata.get("version")
    try:
        parsed_version = int(version)
    except (TypeError, ValueError):
        parsed_version = _package_version_from_path(path)
    return (created_at, parsed_version, path.stat().st_mtime, path.name)


def display_source_path(path_text: Any) -> str:
    raw = str(path_text).replace("\\", "/")
    name = Path(raw).name
    label = "源资料"
    if "operator_reviews" in raw:
        label = "人工复核记录"
    elif "release_history" in raw:
        label = "发布历史记录"
    else:
        for prefix, display_name in PACKAGE_DISPLAY_NAMES.items():
            if f"_{prefix}_" in name or name.startswith(f"{prefix}_") or prefix.lower() in name.lower():
                label = display_name
                break
    return f"{label}：{raw}"


def stage_report_bundle_passed(row: dict[str, Any]) -> bool:
    return (
        row.get("validation_status") == "success"
        and row.get("valid") is True
        and row.get("review_status") == "success"
        and row.get("artifact_validation_status") == "success"
        and not row.get("missing_groups")
        and bool(row.get("primary_exists"))
        and bool(row.get("reference_manifest_exists"))
    )


def stage_acceptance_passed(row: dict[str, Any]) -> bool:
    return stage_report_bundle_passed(row) and row.get("workbench_run_verified") is True


def display_stage_validation(row: dict[str, Any]) -> str:
    if row.get("validation_status") == "success" and row.get("valid") is True and not row.get("workbench_run_verified"):
        return "导入通过"
    return display_status(row.get("validation_status"))


def stage_ui_state(row: dict[str, Any]) -> dict[str, str]:
    step = int(row.get("step", 0))
    stage = STAGE_BY_NUMBER[step]
    missing_groups = row.get("missing_groups") or []
    missing_upstream = row.get("missing_upstream_artifacts") or []
    source_count = int(row.get("source_count") or 0)
    upstream_required = int(row.get("upstream_required_count") or 0)
    upstream_ready = bool(row.get("upstream_ready"))

    if missing_upstream or (upstream_required and not upstream_ready):
        return {
            "key": "needs_input",
            "label": "上游未通过",
            "hint": "先运行并通过依赖阶段，再运行本阶段。",
        }

    if missing_groups or (stage.package_prefixes and source_count == 0 and (upstream_required == 0 or not upstream_ready)):
        return {
            "key": "needs_input",
            "label": "缺源资料",
            "hint": "先提交本阶段需要的人工源资料 ID，再运行本阶段。",
        }

    if stage_acceptance_passed(row):
        return {
            "key": "passed",
            "label": "已运行通过",
            "hint": "本阶段已有工作台成功运行记录，产物验收也通过。",
        }

    if stage_report_bundle_passed(row):
        return {
            "key": "imported_pending",
            "label": "待重新运行",
            "hint": "产物文件存在，但缺少当前工作台运行证明；请重新运行本阶段确认当前结果。",
        }

    if row.get("validation_status") == "missing":
        return {
            "key": "needs_run",
            "label": "待运行",
            "hint": "已有可用源资料，点击运行选中步骤生成本阶段产物。",
        }

    if (
        row.get("validation_status") == "failed"
        and upstream_ready
        and not missing_groups
        and row.get("optional_missing_groups")
    ):
        return {
            "key": "needs_run",
            "label": "待重跑",
            "hint": "旧报告把同阶段人工包当成必需输入；当前上游产物已满足，请重跑本阶段。",
        }

    return {
        "key": "needs_fix",
        "label": "需处理",
        "hint": "查看验收结果，修正人工输入或上游资料后重新运行。",
    }


def project_health(rows: list[dict[str, Any]]) -> dict[str, int]:
    passed = 0
    needs_input = 0
    needs_run = 0
    needs_fix = 0
    source_total = 0
    for row in rows:
        state = stage_ui_state(row)["key"]
        source_total += int(row.get("source_count") or 0)
        if state == "passed":
            passed += 1
        elif state == "needs_input":
            needs_input += 1
        elif state in {"needs_run", "imported_pending"}:
            needs_run += 1
        else:
            needs_fix += 1
    return {
        "total": len(rows),
        "passed": passed,
        "needs_input": needs_input,
        "needs_run": needs_run,
        "needs_fix": needs_fix,
        "source_total": source_total,
    }


def draft_root(root: Path | None = None) -> Path:
    return source_root(root) / "operator_drafts"


def draft_path(step: int, root: Path | None = None) -> Path:
    return draft_root(root) / f"stage_{step:02d}_draft.json"


def save_stage_draft(
    step: int,
    notes: str,
    decisions: dict[str, bool],
    approved: bool,
    root: Path | None = None,
) -> Path:
    path = draft_path(step, root)
    stage = STAGE_BY_NUMBER[step]
    write_json(
        path,
        {
            "project": PROJECT_DISPLAY_NAME,
            "project_id": PROJECT_NAME,
            "step": step,
            "title": stage.title,
            "updated_at": now_iso(),
            "approved": approved,
            "notes": notes,
            "decisions": decisions,
        },
    )
    return path


def load_stage_draft(step: int, root: Path | None = None) -> dict[str, Any]:
    return read_json(draft_path(step, root), {})


def _is_runtime_root(path: Path) -> bool:
    return (
        (path / "orchestrator.py").exists()
        and (path / "steps").exists()
        and (path / "artifact_layer").exists()
    )


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parents[1]

    candidates = [start]
    for name in (".project_runtime", "project_runtime", "工程运行文件"):
        candidates.append(start / name)
        if start.parent != start:
            candidates.append(start.parent / name)
    candidates.extend(start.parents)

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if _is_runtime_root(candidate):
            return candidate
    return start


def normalize_project_root(root: Path | None = None) -> Path:
    candidate = (root or project_root()).resolve()
    if _is_runtime_root(candidate):
        return candidate
    discovered = project_root().resolve()
    if _is_runtime_root(discovered):
        return discovered
    return candidate


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def date_stamp() -> str:
    return datetime.now().strftime("%Y%m%d")


def safe_slug(value: str, fallback: str = "item") -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return value or fallback


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def source_root(root: Path | None = None) -> Path:
    return (root or project_root()) / "source_artifacts"


def stage_output_dir(step: int, root: Path | None = None) -> Path:
    return (root or project_root()) / "outputs" / "artifacts" / f"stage_{step:02d}"


def project_settings_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "project_settings.json"


def default_development_path(root: Path | None = None) -> str:
    _ = root
    return ""


def default_project_settings(root: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "development_path": default_development_path(root),
        "editor_path": "",
    }


def load_project_settings(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    settings = default_project_settings(root)
    raw = read_json(project_settings_path(root), {})
    if isinstance(raw, dict):
        for key in ("development_path", "editor_path"):
            if isinstance(raw.get(key), str):
                settings[key] = raw[key]
    return settings


def save_project_settings(settings: dict[str, Any], root: Path | None = None) -> Path:
    root = root or project_root()
    data = default_project_settings(root)
    data.update({
        "development_path": str(settings.get("development_path") or "").strip(),
        "editor_path": str(settings.get("editor_path") or "").strip(),
        "updated_at": now_iso(),
    })
    path = project_settings_path(root)
    write_json(path, data)
    return path


def configured_development_path(root: Path | None = None) -> Path:
    settings = load_project_settings(root)
    raw = settings.get("development_path") or ""
    return Path(str(raw)).expanduser()


def configured_editor_path(root: Path | None = None) -> str:
    return str(load_project_settings(root).get("editor_path") or "").strip()


def configured_development_path_text(root: Path | None = None) -> str:
    return str(load_project_settings(root).get("development_path") or "").strip()


def initialize_empty_workspace(root: Path | None = None) -> None:
    save_manager.initialize_active_workspace(root or project_root())


def ensure_current_save(root: Path | None = None, display_name: str | None = None) -> dict[str, Any]:
    return save_manager.ensure_current_save(root or project_root(), display_name)


def sync_current_save(
    root: Path | None = None,
    *,
    event: str,
    stage: int | None = None,
    message: str = "",
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    return save_manager.retry_sync(
        root or project_root(),
        event=event,
        stage=stage,
        message=message,
        log=log,
    )


def save_list(root: Path | None = None) -> list[dict[str, Any]]:
    return save_manager.list_saves(root or project_root())


def save_current_as(root: Path | None = None, display_name: str | None = None) -> dict[str, Any]:
    return save_manager.save_current_as(root or project_root(), display_name)


def overwrite_save(root: Path | None, save_id: str) -> dict[str, Any]:
    return save_manager.overwrite_save(root or project_root(), save_id)


def load_save(root: Path | None, save_id: str) -> dict[str, Any]:
    return save_manager.load_save(root or project_root(), save_id)


def delete_save(root: Path | None, save_id: str) -> None:
    save_manager.delete_save(root or project_root(), save_id)


def workspace_has_state(root: Path | None = None) -> bool:
    return save_manager.workspace_has_state(root or project_root())


def request_soft_stop(root: Path | None = None, *, reason: str = "operator_stop") -> dict[str, Any]:
    return runtime_control.request_stop(root or project_root(), reason=reason)


def clear_soft_stop(root: Path | None = None) -> None:
    runtime_control.clear_stop_request(root or project_root())


def default_save_name() -> str:
    return save_manager.default_display_name()


def registry_artifacts(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or project_root()
    data = read_json(root / "artifact_layer" / "registry.json", {})
    artifacts = data.get("artifacts", []) if isinstance(data, dict) else []
    if not isinstance(artifacts, list):
        return []
    return [item for item in artifacts if isinstance(item, dict)]


def upstream_stage_numbers(step: int, root: Path | None = None) -> tuple[int, ...]:
    artifacts = registry_artifacts(root)
    by_id = {
        str(item.get("id")): item
        for item in artifacts
        if item.get("id") is not None
    }
    upstream: set[int] = set()
    for artifact in artifacts:
        if int(artifact.get("stage", -1)) != step:
            continue
        for dep_id in artifact.get("depends_on", []):
            dep = by_id.get(str(dep_id))
            if dep is not None:
                upstream.add(int(dep.get("stage", -1)))
    return tuple(sorted(item for item in upstream if item >= 0))


def upstream_stage_ready(step: int, root: Path | None = None) -> bool:
    root = root or project_root()
    required = upstream_stage_numbers(step, root)
    if not required:
        return True
    for upstream_step in required:
        stage_dir = stage_output_dir(upstream_step, root)
        validation = read_json(stage_dir / "validation_report.json", {})
        layer = read_json(stage_dir / "artifact_validation_layer.json", {})
        if validation.get("status") != "success" or validation.get("valid") is not True:
            return False
        if layer.get("status") != "success":
            return False
    return True


def next_package_dir(prefix: str, root: Path | None = None, *, step: int | None = None) -> Path:
    root = root or project_root()
    base = source_root(root)
    base.mkdir(parents=True, exist_ok=True)
    short = PACKAGE_SHORT_NAMES.get(prefix, safe_slug(prefix).lower()[:8])
    package_prefix = f"s{step:02d}_{short}_v" if step is not None else f"{short}_v"
    versions: list[int] = []
    for item in base.glob(f"{package_prefix}*"):
        if not item.is_dir():
            continue
        match = re.search(r"_v(\d+)$", item.name)
        if match:
            versions.append(int(match.group(1)))
    version = max(versions or [0]) + 1
    return base / f"{package_prefix}{version}"


def copy_attachments(paths: list[str], dest: Path) -> list[str]:
    copied: list[str] = []
    attachments_dir = dest / "attachments"
    for raw_path in paths:
        if not raw_path:
            continue
        src = Path(raw_path)
        if not src.exists() or not src.is_file():
            continue
        target = attachments_dir / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(str(target.relative_to(dest)).replace("\\", "/"))
    return copied


def invalid_document_attachments(paths: list[str]) -> list[str]:
    invalid: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.suffix.lower() not in ALLOWED_DOCUMENT_ATTACHMENT_SUFFIXES or not path.is_file():
            invalid.append(raw_path)
    return invalid


def markdown_block(title: str, payload: dict[str, Any]) -> str:
    decisions = payload.get("decisions", {})
    lines = [
        f"# {title}",
        "",
        f"- 生成时间：{payload['created_at']}",
        f"- 阶段：{payload['step']:02d} {payload['title']}",
        f"- 人工确认：{display_bool(payload.get('approved', False))}",
        "",
        "## 操作者说明",
        "",
        payload.get("notes", "").strip() or "（未填写）",
        "",
        "## 确认项",
        "",
    ]
    for question, answer in decisions.items():
        lines.append(f"- {question}：{display_bool(answer)}")
    if not decisions:
        lines.append("- （无）")
    lines.extend(["", "## 附件", ""])
    attachments = payload.get("attachments", [])
    for item in attachments:
        lines.append(f"- {item}")
    if not attachments:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines)


def base_payload(stage: StageInteraction, notes: str, decisions: dict[str, bool], attachments: list[str], approved: bool) -> dict[str, Any]:
    return {
        "project": PROJECT_DISPLAY_NAME,
        "project_id": PROJECT_NAME,
        "step": stage.number,
        "slug": stage.slug,
        "title": stage.title,
        "created_at": now_iso(),
        "approved": approved,
        "notes": notes,
        "decisions": decisions,
        "attachments": attachments,
    }


def common_package_files(package_dir: Path, stage: StageInteraction, payload: dict[str, Any]) -> None:
    prefix = payload.get("package_type") or payload.get("source_id") or ""
    if prefix:
        write_json(
            package_dir / "package_manifest.json",
            {
                "schema_version": 1,
                "project": PROJECT_DISPLAY_NAME,
                "project_id": PROJECT_NAME,
                "package_id": f"source:{prefix}",
                "package_type": prefix,
                "package_type_id": safe_slug(str(prefix)).lower(),
                "source_id": prefix,
                "source_ids": [prefix],
                "stage": stage.number,
                "stage_slug": stage.slug,
                "stage_title": stage.title,
                "created_at": payload["created_at"],
                "version": _package_version_from_path(package_dir),
            },
        )
    write_json(package_dir / "operator_submission.json", payload)
    write_json(
        package_dir / "human_approval.json",
        {
            "approved": payload.get("approved", False),
            "approved_at": payload["created_at"],
            "step": stage.number,
            "title": stage.title,
            "decision_count": len(payload.get("decisions", {})),
        },
    )
    write_text(package_dir / "human_review.md", markdown_block(f"人工评审 - {stage.title}", payload))
    write_text(package_dir / "stage_input.md", markdown_block(f"操作者输入 - {stage.title}", payload))


def files_for_prefix(prefix: str, package_dir: Path, stage: StageInteraction, payload: dict[str, Any]) -> None:
    notes = payload.get("notes", "").strip()
    if prefix == "Concept":
        write_json(package_dir / "creative_points.json", {"points": [notes or "操作者提交的玩法想法。"]})
        write_json(package_dir / "prototype_candidates.json", {"candidates": [{"id": "P-001", "summary": notes}]})
        write_text(package_dir / "prototype_cards.md", f"# 玩法原型候选\n\n## P-001\n\n{notes}\n")
        write_json(package_dir / "selected_play_prototype.json", {"id": "P-001", "selected": True, "description": notes})
        write_text(package_dir / "selected_play_prototype.md", f"# 已选择玩法原型\n\n{notes}\n")
        write_json(package_dir / "open_questions.json", {"questions": []})
        write_json(package_dir / "selection_history.json", {"selected": "P-001", "timestamp": now_iso()})
        return

    if prefix == "GameplayFramework":
        write_json(package_dir / "gameplay_framework.json", {"framework": notes, "approved": payload.get("approved", False)})
        write_text(package_dir / "gameplay_framework.md", f"# 玩法框架\n\n{notes}\n")
        write_json(package_dir / "subsystem_queue.json", {"subsystems": [{"id": "SYS-001", "name": "核心玩法", "status": "queued"}]})
        write_json(package_dir / "framework_revision_history.json", {"revisions": [{"version": 1, "notes": notes, "timestamp": now_iso()}]})
        write_json(package_dir / "selected_play_prototype_snapshot.json", {"source": "operator_submission", "description": notes})
        return

    if prefix == "SubsystemDesign":
        write_json(package_dir / "approved_subsystems.json", {"approved": ["SYS-001"]})
        write_json(package_dir / "subsystem_queue.json", {"subsystems": [{"id": "SYS-001", "name": "核心玩法"}]})
        write_json(package_dir / "gameplay_framework_snapshot.json", {"notes": notes})
        write_json(package_dir / "subsystem_review_log.json", {"reviews": [{"id": "SYS-001", "approved": payload.get("approved", False)}]})
        write_json(package_dir / "subsystem_revision_history.json", {"revisions": [{"id": "SYS-001", "notes": notes}]})
        system_dir = package_dir / "systems" / "SYS-001"
        write_text(system_dir / "system_design.md", f"# SYS-001 核心玩法\n\n{notes}\n")
        write_json(system_dir / "system_design.json", {"id": "SYS-001", "name": "核心玩法", "design": notes})
        write_json(system_dir / "approval.json", {"approved": payload.get("approved", False), "timestamp": now_iso()})
        return

    if prefix == "AIDesignScript":
        write_text(package_dir / "ai_design_script.md", f"# AI 理解脚本\n\n{notes}\n")
        write_json(package_dir / "ai_design_script.json", {"script": notes, "approved": payload.get("approved", False)})
        write_json(package_dir / "terminology_index.json", {"terms": []})
        write_json(package_dir / "source_trace.json", {"source": "operator_submission", "step": stage.number})
        write_json(package_dir / "script_validation.json", {"valid": True, "errors": []})
        return

    if prefix == "Design":
        write_text(package_dir / "frozen_game_design.md", f"# 冻结游戏设计\n\n{notes}\n")
        write_json(package_dir / "design_handoff.json", {"frozen": True, "design": notes})
        write_json(package_dir / "final_design_package.json", {"design": notes, "approved": payload.get("approved", False)})
        write_json(package_dir / "quality_summary.json", {"valid": True, "notes": notes})
        write_json(package_dir / "development_system_design.json", {"systems": [{"id": "SYS-001", "name": "核心玩法"}]})
        return

    if prefix == "DevelopmentDesign":
        write_text(package_dir / "development_system_design.md", f"# 开发系统设计\n\n{notes}\n")
        write_json(package_dir / "development_system_design.json", {"systems": [{"id": "SYS-001", "notes": notes}]})
        write_json(package_dir / "feature_matrix.json", {"features": []})
        write_json(package_dir / "function_inventory.json", {"functions": []})
        write_json(package_dir / "skill_usage_plan.json", {"skills": []})
        write_json(package_dir / "development_open_questions.json", {"questions": []})
        write_json(package_dir / "development_design_validation.json", {"valid": True, "errors": []})
        write_json(package_dir / "approval.json", {"approved": payload.get("approved", False)})
        return

    if prefix == "ProgReq":
        write_text(package_dir / "systems.md", f"# 系统清单\n\n{notes}\n")
        write_text(package_dir / "entities.md", "# 实体清单\n\n- 核心玩家\n- 核心目标\n")
        write_text(package_dir / "contracts.md", "# 接口契约\n\n- 核心玩法契约已经由操作者确认。\n")
        write_text(package_dir / "acceptance_criteria.md", "# 验收标准\n\n- 操作者确认程序需求已可进入开发。\n")
        write_text(package_dir / "program_structure_spec.md", "# 程序结构规格\n\n- 运行模块将在开发阶段实现。\n")
        write_text(package_dir / "program_requirements.md", f"# 程序需求\n\n{notes}\n")
        write_json(package_dir / "program_requirements_contract.json", {"valid": True, "notes": notes, "contracts": []})
        write_json(package_dir / "validation_report.json", {"valid": True, "errors": []})
        return

    if prefix == "ArtReq":
        write_text(package_dir / "原画需求.md", f"# 原画需求\n\n{notes}\n")
        write_text(package_dir / "UI需求.md", "# 界面需求\n\n- 操作者已确认界面需求。\n")
        write_text(package_dir / "特效需求.md", "# 特效需求\n\n- 操作者已确认反馈表现需求。\n")
        write_text(package_dir / "art_structure_spec.md", "# 美术结构规格\n\n- 资产目录和命名已由操作者确认。\n")
        write_text(package_dir / "drift_analysis.md", "# 风格漂移分析\n\n- 未记录未解决的风格漂移。\n")
        write_json(package_dir / "asset_registry.json", {"assets": []})
        write_json(package_dir / "art_requirements_contract.json", {"valid": True, "notes": notes})
        write_json(package_dir / "validation_report.json", {"valid": True, "errors": []})
        return

    if prefix in {"ProgReview", "ArtReview"}:
        write_text(package_dir / "review.md", f"# 评审记录\n\n{notes}\n")
        write_text(package_dir / "verdict.md", "# 评审结论\n\n通过\n")
        write_json(package_dir / f"{safe_slug(prefix)}_report.json", {"verdict": "PASS", "notes": notes})
        write_json(package_dir / "validation_report.json", {"valid": True, "errors": []})
        return

    if prefix == "Plans":
        write_text(package_dir / "program_plan_index.md", f"# 程序开发计划\n\n{notes}\n")
        write_text(package_dir / "PLAN-001.md", "# PLAN-001 核心开发\n\n- 实现已确认的核心玩法。\n")
        write_json(package_dir / "build_config.json", {"target": "local", "approved": payload.get("approved", False)})
        write_json(package_dir / "config_schema.json", {"schema": "operator-plan"})
        write_text(package_dir / "program_structure_spec.md", "# 程序结构规格\n\n- 操作者已确认。\n")
        return

    if prefix == "ArtPlans":
        write_text(package_dir / "art_plan_index.md", f"# 美术制作计划\n\n{notes}\n")
        write_text(package_dir / "ART-001.md", "# ART-001 核心资产制作\n\n- 制作已确认的核心视觉资产。\n")
        write_text(package_dir / "art_structure_spec.md", "# 美术结构规格\n\n- 操作者已确认。\n")
        write_json(package_dir / "validation_report.json", {"valid": True, "errors": []})
        return

    if prefix == "Alignment":
        write_text(package_dir / "AlignmentProtocol.md", f"# 资产对齐协议\n\n{notes}\n")
        write_text(package_dir / "program_assets.md", "# 程序资产引用\n\n- 操作者已确认。\n")
        write_text(package_dir / "art_assets.md", "# 美术资产交付\n\n- 操作者已确认。\n")
        write_text(package_dir / "dependency_graph.md", "# 依赖关系图\n\n- 未记录未解决冲突。\n")
        write_text(package_dir / "gap_analysis.md", "# 缺口分析\n\n- 未记录未解决缺口。\n")
        write_json(package_dir / "validation_report.json", {"valid": True, "errors": []})
        return

    if prefix in {"DevExecution", "ArtProduction", "Integration", "Build", "DeltaPatch"}:
        file_stem = safe_slug(prefix).lower()
        write_text(package_dir / f"{file_stem}.md", f"# {display_package_prefix(prefix)}\n\n{notes}\n")
        write_json(package_dir / f"{file_stem}.json", {"approved": payload.get("approved", False), "notes": notes})
        write_json(package_dir / "validation_report.json", {"valid": True, "errors": []})
        if prefix == "Build":
            write_json(package_dir / "build_report.json", {"status": "success", "notes": notes})
        if prefix == "DeltaPatch":
            write_json(package_dir / "patch_manifest.json", {"status": "success", "notes": notes})
        return

    write_text(package_dir / f"{safe_slug(prefix).lower()}.md", f"# {display_package_prefix(prefix)}\n\n{notes}\n")
    write_json(package_dir / f"{safe_slug(prefix).lower()}.json", {"notes": notes})


def create_operator_packages(
    step: int,
    notes: str,
    decisions: dict[str, bool],
    attachments: list[str],
    approved: bool,
    root: Path | None = None,
) -> list[Path]:
    root = root or project_root()
    stage = STAGE_BY_NUMBER[step]
    invalid_attachments = invalid_document_attachments(attachments)
    if invalid_attachments:
        allowed = ", ".join(sorted(ALLOWED_DOCUMENT_ATTACHMENT_SUFFIXES))
        names = ", ".join(Path(item).name for item in invalid_attachments)
        raise ValueError(f"文档附件只允许 {allowed} 文件：{names}")
    if step == 0 and not notes.strip() and not attachments:
        raise ValueError("第 0 阶段必须提交人工输入，或添加一个 .md/.txt 主设计文档附件。")
    if step == 0 and len(attachments) > 1:
        raise ValueError("第 0 阶段只能提交一个主设计文档附件；请删除多余附件后重新提交。")
    if not stage.package_prefixes:
        review_dir = source_root(root) / "operator_reviews" / f"stage_{step:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        payload = base_payload(stage, notes, decisions, [], approved)
        payload["package_type"] = "OperatorReview"
        payload["source_id"] = "OperatorReview"
        copied = copy_attachments(attachments, review_dir)
        payload["attachments"] = copied
        common_package_files(review_dir, stage, payload)
        return [review_dir]

    created: list[Path] = []
    for prefix in stage.package_prefixes:
        package_dir = next_package_dir(prefix, root, step=step)
        package_dir.mkdir(parents=True, exist_ok=False)
        payload = base_payload(stage, notes, decisions, [], approved)
        payload["package_type"] = prefix
        payload["source_id"] = prefix
        copied = copy_attachments(attachments, package_dir)
        payload["attachments"] = copied
        common_package_files(package_dir, stage, payload)
        files_for_prefix(prefix, package_dir, stage, payload)
        created.append(package_dir)
    return created


def source_matches(stage: StageInteraction, root: Path | None = None) -> list[Path]:
    root = root or project_root()
    base = source_root(root)
    matches: dict[Path, Path] = {}
    if base.exists() and stage.package_prefixes:
        for item in base.iterdir():
            if item.is_dir() and source_matches_ids(item, stage.package_prefixes):
                matches[item.resolve()] = item
    if not matches:
        for pattern in stage.source_patterns:
            for item in base.glob(pattern):
                if item.is_dir():
                    matches[item.resolve()] = item
    return sorted(matches.values(), key=source_sort_key, reverse=True)


def successful_workbench_run_evidence(root: Path | None = None) -> dict[int, str]:
    root = normalize_project_root(root)
    log_dir = root / "outputs" / "run_logs"
    evidence: dict[int, str] = {}
    if not log_dir.exists():
        return evidence
    for log_path in sorted(log_dir.glob("*.log"), key=lambda item: item.stat().st_mtime):
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "orchestrator.py" not in text:
            continue
        if not re.search(r"(退出码\s+0|exit code\s+0)", text, re.IGNORECASE):
            continue
        from_match = re.search(r"--from-step(?:=|\s+)(\d+)", text)
        stop_match = re.search(r"--stop-step(?:=|\s+)(\d+)", text)
        if not from_match or not stop_match:
            continue
        from_step = int(from_match.group(1))
        stop_step = int(stop_match.group(1))
        if from_step < 0 or stop_step > 15 or from_step > stop_step:
            continue
        try:
            marker = str(log_path.resolve().relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            marker = str(log_path)
        for step in range(from_step, stop_step + 1):
            evidence[step] = marker
    return evidence


def stage10_runtime_validation(root: Path, stage_dir: Path, validation: dict[str, Any]) -> dict[str, Any]:
    """Stage 10 is only complete when actual development writes its final report."""
    result = dict(validation) if isinstance(validation, dict) else {}
    final_report = read_json(stage_dir / "devexecution.json", {})
    if isinstance(final_report, dict) and final_report.get("status"):
        status = str(final_report.get("status"))
        task_count = int(final_report.get("task_count") or 0)
        successful_count = int(final_report.get("successful_task_count") or 0)
        result.update({
            "status": status,
            "valid": status == "success" and task_count > 0 and successful_count == task_count,
            "business_quality": final_report,
        })
        return result

    progress_report = read_json(stage_dir / "devexecution_progress.json", {})
    task_records = sorted(stage_dir.glob("DEV-*_execution.json"))
    store_path = execution_object_store_path(root)
    execution_store = read_json(store_path, {}) if store_path else {}
    executing_objects = []
    if isinstance(execution_store, dict):
        objects = execution_store.get("objects", [])
        if isinstance(objects, list):
            executing_objects = [
                item
                for item in objects
                if isinstance(item, dict)
                and item.get("state") == "executing"
                and item.get("metadata", {}).get("stage") == 10
            ]

    if isinstance(progress_report, dict) and progress_report.get("status") == "running":
        result.update({
            "status": "running",
            "valid": False,
            "business_quality": progress_report,
        })
        return result

    if isinstance(progress_report, dict) and progress_report.get("status") == "stopped":
        result.update({
            "status": "stopped",
            "valid": False,
            "business_quality": progress_report,
        })
        return result

    if task_records or executing_objects:
        result.update({
            "status": "interrupted",
            "valid": False,
            "business_quality": {
                "status": "interrupted",
                "executed_task_count": len(task_records),
                "executing_execution_object_count": len(executing_objects),
                "message": "Stage 10 has task-level records but no final devexecution.json.",
            },
        })
        return result

    if result.get("status") == "success":
        result.update({
            "status": "incomplete",
            "valid": False,
            "business_quality": {
                "status": "incomplete",
                "message": "Stage 10 import artifacts exist, but actual development has not produced devexecution.json.",
            },
        })
    return result


def summarize_stage(
    step: int,
    root: Path | None = None,
    run_evidence: dict[int, str] | None = None,
) -> dict[str, Any]:
    root = normalize_project_root(root)
    run_evidence = run_evidence if run_evidence is not None else successful_workbench_run_evidence(root)
    stage_dir = stage_output_dir(step, root)
    validation = read_json(stage_dir / "validation_report.json", {})
    if step == 10:
        validation = stage10_runtime_validation(root, stage_dir, validation)
    reviews = read_json(stage_dir / "artifact_reviews.json", {})
    layer = read_json(stage_dir / "artifact_validation_layer.json", {})
    manifest = read_json(stage_dir / "artifact_layer_manifest.json", {})
    reference_path = stage_dir / "reference_manifest.json"
    reference = read_json(reference_path, {})
    if step == 10:
        primary = stage_dir / "devexecution.json"
    else:
        primary = stage_dir / ("migration_audit.json" if step == 15 else "artifact_index.json")
    stage = STAGE_BY_NUMBER[step]
    sources = source_matches(stage, root)
    evidence = run_evidence.get(step, "")
    upstream_stages = upstream_stage_numbers(step, root)
    upstream_ready = upstream_stage_ready(step, root)
    raw_missing_groups = validation.get("missing_groups", [])
    missing_required_groups = validation.get("missing_required_groups")
    if missing_required_groups is None:
        missing_required_groups = [] if upstream_stages and upstream_ready else raw_missing_groups
    optional_missing_groups = validation.get("optional_missing_groups")
    if optional_missing_groups is None:
        optional_missing_groups = raw_missing_groups if upstream_stages and upstream_ready else []
    return {
        "step": step,
        "title": stage.title,
        "stage_dir": stage_dir,
        "exists": stage_dir.exists(),
        "validation_status": validation.get("status", "missing"),
        "valid": validation.get("valid"),
        "review_status": reviews.get("status", "missing"),
        "artifact_validation_status": layer.get("status", "missing"),
        "imported_sources": validation.get("imported_sources", []),
        "imported_upstream_artifacts": validation.get("imported_upstream_artifacts", []),
        "missing_upstream_artifacts": validation.get("missing_upstream_artifacts", []),
        "optional_missing_groups": optional_missing_groups,
        "missing_groups": missing_required_groups,
        "artifact_count": len(manifest.get("artifacts", [])) if isinstance(manifest, dict) else 0,
        "task_count": len(manifest.get("tasks", [])) if isinstance(manifest, dict) else 0,
        "primary_exists": primary.exists(),
        "reference_manifest_exists": reference_path.exists(),
        "reference_file_count": len(reference.get("files", [])) if isinstance(reference, dict) else 0,
        "reference_upstream_file_count": (
            reference.get("summary", {}).get("upstream_file_count", 0)
            if isinstance(reference, dict) and isinstance(reference.get("summary", {}), dict)
            else 0
        ),
        "source_count": len(sources),
        "sources": [str(item.relative_to(root)).replace("\\", "/") for item in sources[:8]],
        "upstream_stages": upstream_stages,
        "upstream_ready": upstream_ready,
        "upstream_required_count": len(upstream_stages),
        "upstream_count": len(validation.get("imported_upstream_artifacts", [])),
        "workbench_run_verified": bool(evidence),
        "run_evidence": evidence,
    }


def summarize_all(root: Path | None = None) -> list[dict[str, Any]]:
    root = normalize_project_root(root)
    run_evidence = successful_workbench_run_evidence(root)
    return [summarize_stage(stage.number, root, run_evidence) for stage in STAGES]


def run_log_dir(root: Path | None = None, *, create: bool = True) -> Path:
    root = normalize_project_root(root)
    path = root / "outputs" / "run_logs"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def format_command(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def command_log_path(args: list[str], root: Path | None = None) -> Path:
    first = Path(args[0]).stem if args else "command"
    if first.lower() in {"python", "pythonw", "py"} and len(args) > 1:
        if args[1] == "-m" and len(args) > 2:
            first = Path(args[2]).stem
        elif args[1] == "-c":
            first = "inline_python"
        else:
            first = Path(args[1]).stem
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", first).strip("_") or "command"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return run_log_dir(root) / f"{stamp}_{label}.log"


def is_admin() -> bool:
    if os.name == "nt":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    geteuid = getattr(os, "geteuid", None)
    return bool(geteuid and geteuid() == 0)


def supports_admin_relaunch() -> bool:
    return os.name == "nt"


def relaunch_as_admin() -> bool:
    if os.name != "nt":
        return False
    if is_admin():
        return True
    try:
        import ctypes

        if getattr(sys, "frozen", False):
            executable = sys.executable
            params = subprocess.list2cmdline(sys.argv[1:])
        else:
            executable_path = Path(sys.executable)
            pythonw = executable_path.with_name("pythonw.exe")
            if pythonw.exists():
                executable_path = pythonw
            executable = str(executable_path)
            script = str(Path(sys.argv[0]).resolve())
            params = subprocess.list2cmdline([script] + sys.argv[1:])
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            str(project_root()),
            1,
        )
        return result > 32
    except Exception:
        return False


def python_command() -> list[str]:
    candidates = [
        [sys.executable] if not getattr(sys, "frozen", False) else [],
        ["python"],
        ["py", "-3"],
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                candidate + ["--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                **hidden_subprocess_kwargs(env=child_process_env()),
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return candidate
    return ["python"]


def popen_kwargs(*, stdin: Any = subprocess.DEVNULL) -> dict[str, Any]:
    return hidden_subprocess_kwargs(stdin=stdin, env=child_process_env())


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                **popen_kwargs(),
            )
            return
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        process.terminate()
    except OSError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass


def run_command(
    args: list[str],
    *,
    root: Path | None = None,
    log: Callable[[str], None] | None = None,
    stop_flag: Callable[[], bool] | None = None,
) -> int:
    root = normalize_project_root(root)
    log = log or (lambda text: None)
    stop_flag = stop_flag or (lambda: False)
    log_path = command_log_path(args, root)
    process: subprocess.Popen[str] | None = None
    stop_logged = False

    def emit(text: str) -> None:
        log(text)
        log_file.write(text)
        log_file.flush()

    try:
        with log_path.open("w", encoding="utf-8", newline="") as log_file:
            emit(f"=== 后台命令开始：{datetime.now().isoformat(timespec='seconds')} ===\n")
            emit(f"工作目录：{root}\n")
            emit(f"命令：{format_command(args)}\n")
            emit(f"运行日志：{log_path}\n")
            try:
                process = subprocess.Popen(
                    args,
                    cwd=str(root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    **popen_kwargs(),
                )
            except OSError as exc:
                emit(f"无法启动后台命令：{exc}\n")
                return 1
            assert process.stdout is not None
            while True:
                if stop_flag() and not stop_logged:
                    emit("操作者已请求软停止；等待当前安全边界后退出。\n")
                    stop_logged = True
                line = process.stdout.readline()
                if line:
                    emit(line)
                if line == "" and process.poll() is not None:
                    break
                time.sleep(0.02)
            code = process.wait()
            emit(f"=== 后台命令结束：退出码 {code} ===\n")
            return code
    except OSError as exc:
        log(f"无法启动后台命令：{exc}\n")
        return 1
    finally:
        if process is not None and process.poll() is None:
            terminate_process_tree(process)


def run_orchestrator_range(
    from_step: int,
    stop_step: int,
    *,
    root: Path | None = None,
    log: Callable[[str], None] | None = None,
    stop_flag: Callable[[], bool] | None = None,
) -> int:
    root = root or project_root()
    run_id = runtime_control.new_run_id()
    clear_soft_stop(root)
    runtime_control.write_run_state(
        root,
        status="starting",
        run_id=run_id,
        from_step=from_step,
        stop_step=stop_step,
        current_step=None,
    )
    preflight = run_actual_development_preflight(root, write_report=True)
    if preflight.get("status") != "passed":
        if log:
            log("正式流水线启动门禁失败，未创建存档，未进入阶段 0。\n")
            for blocker in preflight.get("blockers", []):
                if isinstance(blocker, dict):
                    log(f"- {blocker.get('message')} 修复：{blocker.get('fix')}\n")
        return 1
    try:
        ensure_current_save(root)
        sync_current_save(root, event="run_range_start", stage=from_step, message=f"{from_step:02d}-{stop_step:02d}", log=log)
    except Exception as exc:  # noqa: BLE001
        if log:
            log(f"Save sync failed before run: {exc}\n")
        return 1
    cmd = python_command() + [
        "orchestrator.py",
        "--from-step",
        str(from_step),
        "--stop-step",
        str(stop_step),
        "--run-id",
        run_id,
        "--auto-approve",
    ]
    code = run_command(cmd, root=root, log=log, stop_flag=stop_flag)
    try:
        event = "run_range_success" if code == 0 else "run_range_stopped" if code == 130 else "run_range_failed"
        sync_current_save(
            root,
            event=event,
            stage=stop_step,
            message=f"{from_step:02d}-{stop_step:02d} exit_code={code}",
            log=log,
        )
    except Exception as exc:  # noqa: BLE001
        if log:
            log(f"Save sync failed after run: {exc}\n")
        return 1
    return code


def acceptance_summary(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    rows = summarize_all(root)
    failures = []
    for row in rows:
        if not stage_acceptance_passed(row):
            failures.append(row)
    return {
        "reports": len(rows),
        "failures": failures,
        "rows": rows,
    }


def open_path(path: Path) -> None:
    if not path.exists():
        return
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_development_path(root: Path | None = None) -> None:
    if not configured_development_path_text(root):
        raise RuntimeError("实际开发地址未设置。请先在项目设置中填写。")
    path = configured_development_path(root)
    open_path(path)


def open_with_editor(path: Path, root: Path | None = None) -> None:
    root = root or project_root()
    target = Path(path)
    editor = configured_editor_path(root)
    if not target.exists():
        return
    if not editor:
        open_path(target)
        return
    editor_path = Path(editor).expanduser()
    if editor_path.exists():
        args = [str(editor_path), str(target)]
    else:
        try:
            args = shlex.split(editor)
        except ValueError:
            args = [editor]
        if not args:
            open_path(target)
            return
        args.append(str(target))
    cwd = configured_development_path(root) if configured_development_path_text(root) else root
    if not cwd.exists():
        cwd = root
    subprocess.Popen(args, cwd=str(cwd), **popen_kwargs())


def self_test(root: Path | None = None) -> int:
    root = root or project_root()
    required = [
        root / "orchestrator.py",
        root / "steps",
        root / "artifact_layer" / "registry.json",
        root / "source_artifacts",
    ]
    missing = [str(item) for item in required if not item.exists()]
    if missing:
        print(json.dumps({"status": "failed", "missing": missing}, ensure_ascii=False, indent=2))
        return 1
    result = subprocess.run(
        python_command() + ["orchestrator.py", "--list"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        **popen_kwargs(),
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    return result.returncode
