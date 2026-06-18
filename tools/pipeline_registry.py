#!/usr/bin/env python3
"""Unified step registry for the migrated 0-15 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PipelineStep:
    number: int
    name: str
    command: str
    description: str
    requires: tuple[int, ...] = ()
    optional_args: str | None = None


STEP_IDEA_INTAKE = 0
STEP_DEMO = 1
STEP_DESIGN_REVIEW = 2
STEP_PROGRAM_REQUIREMENTS = 3
STEP_ART_REQUIREMENTS = 4
STEP_PROGRAM_REQUIREMENTS_REVIEW = 5
STEP_ART_REQUIREMENTS_REVIEW = 6
STEP_DESIGN_TO_PLAN = 7
STEP_ART_PLAN = 8
STEP_ASSET_ALIGNMENT = 9
STEP_DEV_EXECUTION = 10
STEP_ART_PRODUCTION = 11
STEP_INTEGRATION_VALIDATION = 12
STEP_BUILD = 13
STEP_DELTA_PATCH = 14
STEP_MIGRATION_AUDIT = 15


PIPELINE_STEPS = (
    PipelineStep(0, "Idea intake", "python orchestrator.py --from-step 0 --stop-step 0", "Import sources and generate design extraction, option coverage, and scope catalog."),
    PipelineStep(1, "Gameplay framework", "python orchestrator.py --from-step 1 --stop-step 1", "Generate gameplay framework, system graph, resource flow, and phase map.", (0,)),
    PipelineStep(2, "Design review", "python orchestrator.py --from-step 2 --stop-step 2", "Freeze traced design scope and emit review, backlog, and repair-patch records.", (1,)),
    PipelineStep(3, "Program requirements", "python orchestrator.py --from-step 3 --stop-step 3", "Generate source-traced program requirements and traceability matrix.", (2,)),
    PipelineStep(4, "Art requirements", "python orchestrator.py --from-step 4 --stop-step 4", "Generate source-traced art requirements and asset registry.", (3,)),
    PipelineStep(5, "Program review", "python orchestrator.py --from-step 5 --stop-step 5", "Review program requirements for blockers, warnings, weak relations, and missing trace.", (3,)),
    PipelineStep(6, "Art review", "python orchestrator.py --from-step 6 --stop-step 6", "Review art requirements for blockers and source trace.", (4,)),
    PipelineStep(7, "Program plan", "python orchestrator.py --from-step 7 --stop-step 7", "Generate program task breakdown, phase map, and plan files.", (5,)),
    PipelineStep(8, "Art plan", "python orchestrator.py --from-step 8 --stop-step 8", "Generate art task breakdown and production plan.", (6,)),
    PipelineStep(9, "Asset alignment", "python orchestrator.py --from-step 9 --stop-step 9", "Align program asset references with art deliverables and gap analysis.", (7, 8)),
    PipelineStep(10, "Development execution", "python orchestrator.py --from-step 10 --stop-step 10", "Generate traced development execution records.", (9,)),
    PipelineStep(11, "Art production", "python orchestrator.py --from-step 11 --stop-step 11", "Generate traced art production records.", (9,)),
    PipelineStep(12, "Integration validation", "python orchestrator.py --from-step 12 --stop-step 12", "Validate development and art production integration.", (10, 11)),
    PipelineStep(13, "Build package", "python orchestrator.py --from-step 13 --stop-step 13", "Record test build/package manifest from validated stage outputs.", (12,)),
    PipelineStep(14, "Delta patch", "python orchestrator.py --from-step 14 --stop-step 14", "Record test delta patch, release history, and rollback plan.", (13,)),
    PipelineStep(15, "Migration audit", "python orchestrator.py --from-step 15 --stop-step 15", "Audit migrated runtime and artifacts.", (14,)),
)

STEP_BY_NUMBER = {step.number: step for step in PIPELINE_STEPS}
STEP_NAMES = {step.number: step.name for step in PIPELINE_STEPS}
NON_RUNNABLE_STATUSES = frozenset({"success", "failed", "in_progress", "skipped"})


def get_step(step_number: int) -> PipelineStep:
    try:
        return STEP_BY_NUMBER[int(step_number)]
    except KeyError as exc:
        raise ValueError(f"Unknown pipeline step: {step_number}") from exc


def get_step_name(step_number: int) -> str:
    return get_step(step_number).name


def max_step_number() -> int:
    return max(STEP_BY_NUMBER)


def iter_steps() -> tuple[PipelineStep, ...]:
    return PIPELINE_STEPS


def latest_timestamped_dir(source_dir: Path, prefix: str) -> Path | None:
    candidates = sorted((path for path in source_dir.glob(f"*_{prefix}_*") if path.is_dir()), reverse=True)
    if candidates:
        return candidates[0]
    candidates = sorted((path for path in source_dir.glob(f"{prefix}_*") if path.is_dir()), reverse=True)
    return candidates[0] if candidates else None


def latest_step_status(pipeline_state: dict[str, Any], step_number: int) -> str:
    step_state = pipeline_state.get("steps", {}).get(str(step_number), {})
    return step_state.get("status", "not_started")


def completed_dependencies(pipeline_state: dict[str, Any], step: PipelineStep) -> tuple[int, ...]:
    return tuple(
        required
        for required in step.requires
        if latest_step_status(pipeline_state, required) == "success"
    )


def missing_dependencies(pipeline_state: dict[str, Any], step: PipelineStep) -> tuple[int, ...]:
    completed = set(completed_dependencies(pipeline_state, step))
    return tuple(required for required in step.requires if required not in completed)


def dependencies_satisfied(pipeline_state: dict[str, Any], step: PipelineStep) -> bool:
    return not missing_dependencies(pipeline_state, step)


def is_step_runnable(pipeline_state: dict[str, Any], step: PipelineStep) -> bool:
    status = latest_step_status(pipeline_state, step.number)
    return status not in NON_RUNNABLE_STATUSES and dependencies_satisfied(pipeline_state, step)


def runnable_steps(pipeline_state: dict[str, Any]) -> tuple[PipelineStep, ...]:
    return tuple(step for step in PIPELINE_STEPS if is_step_runnable(pipeline_state, step))
