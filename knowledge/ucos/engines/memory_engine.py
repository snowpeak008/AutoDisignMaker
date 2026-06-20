from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from filelock import FileLock


class MemoryTier(str, Enum):
    WORKING = "working"
    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PATTERN = "patterns"
    FAILURE = "failures"


@dataclass
class MemoryEntry:
    entry_id: str
    tier: MemoryTier
    content: dict[str, Any]
    relevance: float = 1.0


class MemoryEngine:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.knowledge_dir = self.root / "ucos" / "knowledge"

    def write(
        self,
        tier: MemoryTier,
        content: dict[str, Any],
        source: str,
        importance: float = 0.5,
    ) -> str:
        now = _now()
        if tier == MemoryTier.WORKING:
            context_path = self.knowledge_dir / "working" / "context.json"
            data = self._read_json(context_path, default={})
            data.update(content)
            data["updated_at"] = now
            self._safe_write(context_path, data)
            return str(data.get("session_id", "working_context"))

        if tier == MemoryTier.SHORT_TERM:
            entry_id = content.get("stm_id") or f"stm_{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:8]}"
            entry = {
                "schema_version": "1.0",
                "stm_id": entry_id,
                "type": content.get("type", "observation"),
                "title": content.get("title", ""),
                "content": content.get("content", ""),
                "source": {"type": source, "session_id": content.get("session_id", ""), "file_ref": content.get("file_ref", "")},
                "tags": content.get("tags", []),
                "importance": importance,
                "created_at": content.get("created_at", now),
                "last_accessed": now,
                "decay_rate": content.get("decay_rate", 0.05),
                "current_relevance": importance,
                "consolidate_to_episodic": False,
            }
            path = self.knowledge_dir / "short_term" / "entries" / f"{entry_id}.json"
            self._safe_write(path, entry)
            self._upsert_index(MemoryTier.SHORT_TERM, entry_id, path)
            return str(entry_id)

        if tier == MemoryTier.SEMANTIC:
            entry_id = content.get("fact_id") or f"sf_{content.get('domain', 'general')}_{uuid.uuid4().hex[:8]}"
            staged = dict(content)
            staged.setdefault("schema_version", "1.0")
            staged.setdefault("fact_id", entry_id)
            staged.setdefault("type", "fact")
            staged.setdefault("source", {"type": source, "ref": "", "episode_id": ""})
            staged.setdefault("confidence", importance)
            staged["review_required"] = True
            staged.setdefault("version", 1)
            staged.setdefault("last_verified", now)
            staged.setdefault("tags", [])
            staged.setdefault("created_at", now)
            path = self.knowledge_dir / "semantic" / "staging" / f"staged_{entry_id}.json"
            self._safe_write(path, staged)
            return str(entry_id)

        entry_id = content.get("episode_id") or content.get("pattern_id") or content.get("failure_id") or uuid.uuid4().hex[:8]
        path = self._entry_path_for(tier, str(entry_id))
        data = dict(content)
        data.setdefault("created_at", now)
        self._safe_write(path, data)
        self._upsert_index(tier, str(entry_id), path)
        return str(entry_id)

    def query(
        self,
        tier: MemoryTier,
        keywords: list[str],
        top_k: int = 5,
        min_decay: float = 0.2,
    ) -> list[MemoryEntry]:
        entries = []
        for path in self._iter_entry_paths(tier):
            data = self._read_json(path, default={})
            text = json.dumps(data, ensure_ascii=False).lower()
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            relevance = float(data.get("current_relevance", data.get("importance", 1.0)))
            if score > 0 and relevance >= min_decay:
                entry_id = str(data.get("stm_id") or data.get("episode_id") or data.get("pattern_id") or data.get("failure_id") or path.stem)
                entries.append((score, relevance, MemoryEntry(entry_id, tier, data, relevance)))
        entries.sort(key=lambda item: (item[0], item[1]), reverse=True)
        result = [item[2] for item in entries[:top_k]]
        for entry in result:
            self.refresh_access(tier, entry.entry_id)
        return result

    def consolidate(self, from_tier: MemoryTier, to_tier: MemoryTier, entry_id: str) -> str:
        if from_tier != MemoryTier.SHORT_TERM or to_tier != MemoryTier.EPISODIC:
            raise ValueError("only short_term to episodic consolidation is supported in v1")
        source_path = self.knowledge_dir / "short_term" / "entries" / f"{entry_id}.json"
        data = self._read_json(source_path, default={})
        if not data:
            raise FileNotFoundError(source_path)
        if float(data.get("current_relevance", 1.0)) >= 0.3 or float(data.get("importance", 0.0)) < 0.7:
            raise ValueError("entry does not meet consolidation gate")
        episode_id = f"ep_{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:8]}"
        episode = {
            "schema_version": "1.0",
            "episode_id": episode_id,
            "title": data.get("title", ""),
            "domain": "devflow",
            "goal": data.get("content", ""),
            "reason": "short_term_consolidation",
            "key_decisions": [],
            "outcome": {"status": "partial", "result_summary": data.get("content", "")},
            "lessons": [],
            "related_episodes": [],
            "skill_ids": [],
            "pattern_ids_extracted": [],
            "failure_ids_extracted": [],
            "reflection_done": False,
            "created_at": _now(),
            "source_files": [str(source_path)],
        }
        return self.write(MemoryTier.EPISODIC, episode, "consolidate", float(data.get("importance", 0.7)))

    def decay_pass(self, tier: MemoryTier) -> int:
        if tier != MemoryTier.SHORT_TERM:
            return 0
        changed = 0
        for path in self._iter_entry_paths(tier):
            data = self._read_json(path, default={})
            last = _parse_time(data.get("last_accessed") or data.get("created_at"))
            days = max((datetime.now(timezone.utc) - last).total_seconds() / 86400, 0)
            importance = float(data.get("importance", 0.5))
            decay_rate = float(data.get("decay_rate", 0.05))
            relevance = importance * math.pow(1 - decay_rate, days)
            data["current_relevance"] = round(relevance, 4)
            data["consolidate_to_episodic"] = relevance < 0.3 and importance >= 0.7
            self._safe_write(path, data)
            changed += 1
        return changed

    def refresh_access(self, tier: MemoryTier, entry_id: str) -> None:
        if tier != MemoryTier.SHORT_TERM:
            return
        path = self.knowledge_dir / "short_term" / "entries" / f"{entry_id}.json"
        if not path.exists():
            return
        data = self._read_json(path, default={})
        data["last_accessed"] = _now()
        data["current_relevance"] = data.get("importance", data.get("current_relevance", 1.0))
        self._safe_write(path, data)

    def _entry_path_for(self, tier: MemoryTier, entry_id: str) -> Path:
        if tier == MemoryTier.EPISODIC:
            return self.knowledge_dir / "episodic" / "episodes" / f"{entry_id}.json"
        if tier == MemoryTier.PATTERN:
            return self.knowledge_dir / "patterns" / "entries" / f"{entry_id}.json"
        if tier == MemoryTier.FAILURE:
            return self.knowledge_dir / "failures" / "entries" / f"{entry_id}.json"
        raise ValueError(f"unsupported entry tier: {tier}")

    def _iter_entry_paths(self, tier: MemoryTier) -> list[Path]:
        if tier == MemoryTier.SHORT_TERM:
            base = self.knowledge_dir / "short_term" / "entries"
        elif tier == MemoryTier.EPISODIC:
            base = self.knowledge_dir / "episodic" / "episodes"
        elif tier == MemoryTier.PATTERN:
            base = self.knowledge_dir / "patterns" / "entries"
        elif tier == MemoryTier.FAILURE:
            base = self.knowledge_dir / "failures" / "entries"
        else:
            return []
        if not base.exists():
            return []
        return sorted(base.glob("*.json"))

    def _upsert_index(self, tier: MemoryTier, entry_id: str, path: Path) -> None:
        index_dir = {
            MemoryTier.SHORT_TERM: self.knowledge_dir / "short_term",
            MemoryTier.EPISODIC: self.knowledge_dir / "episodic",
            MemoryTier.PATTERN: self.knowledge_dir / "patterns",
            MemoryTier.FAILURE: self.knowledge_dir / "failures",
        }.get(tier)
        if index_dir is None:
            return
        index_path = index_dir / "index.json"
        index = self._read_json(index_path, default={"schema_version": "1.0", "entries": []})
        entries = [item for item in index.get("entries", []) if item.get("id") != entry_id]
        entries.append({"id": entry_id, "path": str(path.relative_to(self.root)), "updated_at": _now()})
        index["entries"] = entries
        self._safe_write(index_path, index)

    @staticmethod
    def _read_json(path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _safe_write(path: Path, content: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = f"{path}.lock"
        with FileLock(lock_path, timeout=5):
            with path.open("w", encoding="utf-8") as handle:
                json.dump(content, handle, ensure_ascii=False, indent=2)
                handle.write("\n")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)

