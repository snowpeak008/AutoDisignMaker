"""ProjectController for no-CrewAI pipeline state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.logger import PipelineLogger
from pipeline.state import load_state, now_iso, save_state


class ProjectController:
    def __init__(self) -> None:
        self.state = load_state()
        self.logger = PipelineLogger()

    @property
    def current_stage(self) -> int:
        return int(self.state.get("current_stage", 0))

    def save(self) -> Path:
        return save_state(self.state)

    def set_status(self, status: str) -> None:
        self.state["status"] = status
        self.save()

    def mark_stage(self, stage: int, status: str, message: str = "") -> None:
        stages: dict[str, Any] = self.state.setdefault("stages", {})
        item = stages.get(str(stage), {})
        item.update({
            "stage": stage,
            "status": status,
            "message": message,
            "updated_at": now_iso(),
        })
        stages[str(stage)] = item
        self.state["status"] = status
        self.save()

    def mark_artifact(self, artifact_id: str, status: str, path: str = "", errors: list[str] | None = None) -> None:
        artifacts: dict[str, Any] = self.state.setdefault("artifacts", {})
        artifacts[artifact_id] = {
            "artifact_id": artifact_id,
            "status": status,
            "path": path,
            "errors": errors or [],
            "updated_at": now_iso(),
        }
        self.save()

    def freeze_stage(self, stage: int) -> None:
        frozen = set(int(item) for item in self.state.get("frozen_stages", []))
        frozen.add(stage)
        self.state["frozen_stages"] = sorted(frozen)
        self.save()

    def advance_to_next_stage(self) -> None:
        self.state["current_stage"] = self.current_stage + 1
        self.state["status"] = "ready"
        self.state["rollback"] = {"active": False, "target_stage": None}
        self.save()
