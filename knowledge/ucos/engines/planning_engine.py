from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ucos.engines.world_model_engine import WorldModelEngine


class PlanningEngine:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.world_engine = WorldModelEngine(self.root)

    def plan(self, goal: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        target_stage = "stage_10" if "Stage10" in goal or "stage10" in goal.lower() else "stage_15"
        dependencies = self.world_engine.get_dependencies(target_stage)
        task_titles = [
            f"Verify prerequisites for {target_stage}",
            f"Execute governed workflow for {target_stage}",
            f"Validate artifacts and record outcome for {target_stage}",
        ]
        tasks = []
        for index, title in enumerate(task_titles, start=1):
            tasks.append(
                {
                    "task_id": f"task_{index:03d}",
                    "title": title,
                    "required_skills": ["skill_read_file_v1", "skill_validate_schema_v1"],
                    "dependencies": dependencies if index == 1 else [f"task_{index - 1:03d}"],
                    "status": "pending",
                    "output": None,
                }
            )
        snapshot = json.dumps(context, ensure_ascii=False, sort_keys=True)
        return {
            "schema_version": "1.0",
            "plan_id": f"plan_{uuid.uuid4().hex[:8]}",
            "goal_id": context.get("goal_id", f"goal_{uuid.uuid4().hex[:8]}"),
            "tasks": tasks,
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "fact_snapshot_hash": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
        }

