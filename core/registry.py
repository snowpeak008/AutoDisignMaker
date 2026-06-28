"""Step registry for the AutoDesignMaker 0-16 pipeline.

Merged from:
- steps/common.py::STEP_SPECS / StepSpec
- tools/pipeline_registry.py::PipelineStep / PIPELINE_STEPS

Single source of truth for step metadata and dependency ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepSpec:
    number: int
    slug: str
    title: str
    requires: tuple[int, ...] = field(default_factory=tuple)
    design_doc: str | None = None


STEP_SPECS: dict[int, StepSpec] = {
    0:  StepSpec(0,  "idea_intake",            "Idea Intake"),
    1:  StepSpec(1,  "demo",                   "Gameplay Framework",      (0,)),
    2:  StepSpec(2,  "design_review",          "Design Review Freeze",    (1,)),
    3:  StepSpec(3,  "program_requirements",   "Program Requirements",    (2,)),
    4:  StepSpec(4,  "art_requirements",       "Art Requirements",        (3,)),
    5:  StepSpec(5,  "program_review",         "Program Review",          (3,)),
    6:  StepSpec(6,  "art_review",             "Art Review",              (4,)),
    7:  StepSpec(7,  "art_style_generation",   "Art Style Generation & Confirmation", (6,)),
    8:  StepSpec(8,  "design_to_plan",         "Program Plan",            (5,)),
    9:  StepSpec(9,  "art_plan",               "Art Plan",                (7,)),
    10: StepSpec(10, "asset_alignment",        "Asset Alignment",         (8, 9)),
    11: StepSpec(11, "dev_execution",          "Dev Execution",           (10,)),
    12: StepSpec(12, "art_production",         "Art Production",          (10,)),
    13: StepSpec(13, "integration_validation", "Integration Validation",  (11, 12)),
    14: StepSpec(14, "build_package",          "Build Package",           (13,)),
    15: StepSpec(15, "delta_patch",            "Delta Patch",             (14,)),
    16: StepSpec(16, "migration_audit",        "Migration Audit",         (15,)),
}

# Design stages (D1-D4) that run before the 0-16 pipeline
DESIGN_STEP_SPECS: dict[str, StepSpec] = {
    "D1": StepSpec(1, "project_portrait",   "Project Portrait"),
    "D2": StepSpec(2, "design_decisions",   "Design Decisions"),
    "D3": StepSpec(3, "design_validation",  "Design Validation"),
    "D4": StepSpec(4, "devflow_handoff",    "DevFlow Handoff"),
}

NON_RUNNABLE_STATUSES = frozenset({"success", "failed", "in_progress", "skipped"})


def get_step(number: int) -> StepSpec:
    try:
        return STEP_SPECS[int(number)]
    except KeyError as exc:
        raise ValueError(f"Unknown pipeline step: {number}") from exc


def get_step_name(number: int) -> str:
    return get_step(number).title


def iter_steps() -> tuple[StepSpec, ...]:
    return tuple(STEP_SPECS[n] for n in sorted(STEP_SPECS))


def latest_step_status(pipeline_state: dict[str, Any], step_number: int) -> str:
    step_state = pipeline_state.get("steps", {}).get(str(step_number), {})
    return step_state.get("status", "not_started")


def dependencies_satisfied(pipeline_state: dict[str, Any], step: StepSpec) -> bool:
    return all(
        latest_step_status(pipeline_state, req) == "success"
        for req in step.requires
    )


def is_step_runnable(pipeline_state: dict[str, Any], step: StepSpec) -> bool:
    status = latest_step_status(pipeline_state, step.number)
    return status not in NON_RUNNABLE_STATUSES and dependencies_satisfied(pipeline_state, step)


def max_step_number() -> int:
    return max(STEP_SPECS)


__all__ = [
    "StepSpec",
    "STEP_SPECS",
    "DESIGN_STEP_SPECS",
    "NON_RUNNABLE_STATUSES",
    "get_step",
    "get_step_name",
    "iter_steps",
    "latest_step_status",
    "dependencies_satisfied",
    "is_step_runnable",
    "max_step_number",
]
