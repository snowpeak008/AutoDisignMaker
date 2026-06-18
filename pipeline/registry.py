"""Disabled registry for the retired stage engine.

The supported execution path is `orchestrator.py` with modules under `steps/`.
This module remains only to fail fast if older code tries to use the retired
pipeline/stages engine.
"""

from __future__ import annotations

from pipeline.controller import ProjectController


def get_stage(stage_number: int, controller: ProjectController) -> None:
    _ = stage_number, controller
    raise RuntimeError("The retired pipeline/stages engine is disabled. Use orchestrator.py.")
