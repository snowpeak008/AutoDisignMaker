"""Rollback placeholder for strict workflow control."""

from __future__ import annotations

from pipeline.controller import ProjectController


def rollback_to_stage(controller: ProjectController, stage: int) -> int:
    controller.state["rollback"] = {"active": True, "target_stage": stage}
    controller.state["current_stage"] = stage
    controller.state["status"] = "ready"
    controller.save()
    controller.logger.info(f"rollback requested to stage {stage}")
    return 0
