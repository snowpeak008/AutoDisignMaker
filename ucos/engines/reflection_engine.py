from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ucos.engines.memory_engine import MemoryEngine, MemoryTier


@dataclass
class ReflectionResult:
    episode_id: str
    pattern_ids: list[str]
    failure_ids: list[str]


class ReflectionEngine:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.memory = MemoryEngine(self.root)

    def reflect(self, episode_id: str) -> ReflectionResult:
        episode_path = self.root / "ucos" / "knowledge" / "episodic" / "episodes" / f"{episode_id}.json"
        if not episode_path.exists():
            raise FileNotFoundError(episode_path)
        with episode_path.open("r", encoding="utf-8") as handle:
            episode = json.load(handle)
        outcome_status = episode.get("outcome", {}).get("status", "partial")
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        pattern_ids: list[str] = []
        failure_ids: list[str] = []
        if outcome_status == "success":
            pattern_id = f"pat_{uuid.uuid4().hex[:8]}"
            self.memory.write(
                MemoryTier.PATTERN,
                {
                    "schema_version": "1.0",
                    "pattern_id": pattern_id,
                    "name": episode.get("title", "successful episode pattern"),
                    "category": "process",
                    "domain": episode.get("domain", "general"),
                    "problem": episode.get("goal", ""),
                    "solution": episode.get("outcome", {}).get("result_summary", ""),
                    "consequences": {"positive": episode.get("lessons", []), "negative": []},
                    "source_episodes": [episode_id],
                    "confidence": 0.8,
                    "usage_count": 0,
                    "human_verified": False,
                    "created_at": now,
                },
                "reflection",
                0.8,
            )
            pattern_ids.append(pattern_id)
        else:
            failure_id = f"fail_{uuid.uuid4().hex[:8]}"
            self.memory.write(
                MemoryTier.FAILURE,
                {
                    "schema_version": "1.0",
                    "failure_id": failure_id,
                    "title": episode.get("title", "episode failure"),
                    "status": "open" if outcome_status == "failure" else "resolved",
                    "severity": "medium",
                    "domain": episode.get("domain", "general"),
                    "failure": episode.get("outcome", {}).get("result_summary", ""),
                    "reason": episode.get("reason", ""),
                    "diagnosis_steps": episode.get("lessons", []),
                    "solution": "",
                    "prevention": "",
                    "source_file": "",
                    "source_episode": episode_id,
                    "related_pattern_ids": [],
                    "created_at": now,
                    "resolved_at": None,
                },
                "reflection",
                0.8,
            )
            failure_ids.append(failure_id)
        episode["reflection_done"] = True
        episode["pattern_ids_extracted"] = pattern_ids
        episode["failure_ids_extracted"] = failure_ids
        with episode_path.open("w", encoding="utf-8") as handle:
            json.dump(episode, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return ReflectionResult(episode_id, pattern_ids, failure_ids)

    def batch_reflect(self, episode_ids: list[str]) -> list[ReflectionResult]:
        return [self.reflect(episode_id) for episode_id in episode_ids]

    def abstract_pattern(self, episode_ids: list[str], domain: str) -> str | None:
        if len(episode_ids) < 2:
            return None
        pattern_id = f"pat_{uuid.uuid4().hex[:8]}"
        self.memory.write(
            MemoryTier.PATTERN,
            {
                "schema_version": "1.0",
                "pattern_id": pattern_id,
                "name": f"{domain} repeated success pattern",
                "category": "process",
                "domain": domain,
                "problem": "Repeated related episodes need reusable guidance.",
                "solution": "Reuse the decisions and checks shared by the source episodes.",
                "consequences": {"positive": ["faster planning"], "negative": ["requires human verification"]},
                "source_episodes": episode_ids,
                "confidence": 0.7,
                "usage_count": 0,
                "human_verified": False,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            },
            "reflection",
            0.7,
        )
        return pattern_id

