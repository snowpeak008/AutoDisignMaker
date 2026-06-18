"""Strict sequential workflow engine."""

from __future__ import annotations

import json

from pipeline.controller import ProjectController
from pipeline.registry import get_stage
from pipeline.rollback import rollback_to_stage


class WorkflowEngine:
    def __init__(self, controller: ProjectController) -> None:
        self.controller = controller

    def print_status(self) -> None:
        print(json.dumps(self.controller.state, ensure_ascii=False, indent=2))

    def run_current_stage(self, mode: str = "run") -> int:
        if self.controller.current_stage > 14:
            self.controller.logger.info("pipeline already complete")
            self.controller.set_status("complete")
            return 0
        stage_number = self.controller.current_stage
        self.controller.logger.info(f"running current stage {stage_number} mode={mode}")
        stage = get_stage(stage_number, self.controller)
        self.controller.mark_stage(stage_number, "in_progress", f"mode={mode}")
        result = stage.run(mode=mode)
        if result.status == "success":
            self.controller.mark_stage(stage_number, "success", result.message)
            self.controller.freeze_stage(stage_number)
            self.controller.advance_to_next_stage()
            self.controller.logger.info(f"stage {stage_number} success")
            return 0
        self.controller.mark_stage(stage_number, "failed", result.message)
        self.controller.logger.error(f"stage {stage_number} failed: {result.errors}")
        return 1

    def run_all(self, mode: str = "run") -> int:
        while self.controller.current_stage <= 14:
            code = self.run_current_stage(mode=mode)
            if code != 0:
                return code
        self.controller.set_status("complete")
        return 0

    def rollback(self, stage: int) -> int:
        return rollback_to_stage(self.controller, stage)
