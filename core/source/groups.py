"""Source group definitions and source type constants."""

from __future__ import annotations

from dataclasses import dataclass


SOURCE_TYPES = (
    "Concept",
    "GameplayFramework",
    "SubsystemDesign",
    "AIDesignScript",
    "Design",
    "DevelopmentDesign",
    "ProgReq",
    "ArtReq",
    "ProgReview",
    "ArtReview",
    "Plans",
    "ArtPlans",
    "Alignment",
    "DevExecution",
    "ArtProduction",
    "Integration",
    "Build",
    "DeltaPatch",
)

SOURCE_MARKERS = {
    "selected_play_prototype.json": "Concept",
    "gameplay_framework.json": "GameplayFramework",
    "approved_subsystems.json": "SubsystemDesign",
    "ai_design_script.json": "AIDesignScript",
    "frozen_game_design.md": "Design",
    "development_system_design.md": "DevelopmentDesign",
    "program_requirements_contract.json": "ProgReq",
    "art_requirements_contract.json": "ArtReq",
    "ProgReview_report.json": "ProgReview",
    "ArtReview_report.json": "ArtReview",
    "program_plan_index.md": "Plans",
    "art_plan_index.md": "ArtPlans",
    "AlignmentProtocol.md": "Alignment",
    "devexecution.json": "DevExecution",
    "artproduction.json": "ArtProduction",
    "integration.json": "Integration",
    "build_report.json": "Build",
    "patch_manifest.json": "DeltaPatch",
}


@dataclass(frozen=True)
class SourceGroup:
    label: str
    patterns: tuple[str, ...]
    mode: str = "latest"
    required: bool = False
    source_ids: tuple[str, ...] = ()
