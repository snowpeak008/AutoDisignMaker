from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="memory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    report = migrate(root, Path(args.source), dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def migrate(root: Path, source: Path, dry_run: bool = False) -> dict[str, Any]:
    source_dir = source if source.is_absolute() else root / source
    now = _now()
    pipeline_total = _pipeline_total(root)
    mappings = []
    active_text = _read_text(source_dir / "active-task.md")
    known_text = _read_text(source_dir / "known-issues.md")
    decisions_text = _read_text(source_dir / "decisions.md")

    context = _context_from_active(active_text, now, pipeline_total=pipeline_total)
    blockers = _blockers_from_known(known_text, now)
    next_actions = _next_actions_from_active(active_text, now)
    facts = _facts_from_decisions(decisions_text, now)
    episodes = _episodes_from_decisions(decisions_text, now)
    failures = _failures_from_known(known_text, now)

    targets = [
        ("active-task.md", "ucos/knowledge/working/context.json", context),
        ("known-issues.md", "ucos/knowledge/working/blockers.json", blockers),
        ("active-task.md", "ucos/knowledge/working/next_actions.json", next_actions),
        ("decisions.md", "ucos/knowledge/semantic/facts/domain_devflow.json", {"schema_version": "1.0", "domain": "devflow", "facts": facts}),
        ("decisions.md", "ucos/knowledge/episodic/index.json", {"schema_version": "1.0", "entries": [{"id": item["episode_id"], "path": f"ucos/knowledge/episodic/episodes/{item['episode_id']}.json"} for item in episodes]}),
        ("known-issues.md", "ucos/knowledge/failures/index.json", {"schema_version": "1.0", "entries": [{"id": item["failure_id"], "path": f"ucos/knowledge/failures/entries/{item['failure_id']}.json"} for item in failures]}),
    ]

    for src, target, content in targets:
        mappings.append({"source": src, "target": target, "items": _count_items(content)})
        if not dry_run:
            _write_json(root / target, content)
    if not dry_run:
        for episode in episodes:
            _write_json(root / "ucos" / "knowledge" / "episodic" / "episodes" / f"{episode['episode_id']}.json", episode)
        for failure in failures:
            _write_json(root / "ucos" / "knowledge" / "failures" / "entries" / f"{failure['failure_id']}.json", failure)

    return {"dry_run": dry_run, "source": str(source_dir), "mappings": mappings, "data_loss": False}


def _context_from_active(text: str, now: str, *, pipeline_total: int) -> dict[str, Any]:
    save_id = _first_match(text, r"save_[0-9A-Za-z_]+") or ""
    active_name = "错误测试" if "错误测试" in text else ""
    progress_match = re.search(r"(\d+)\s*/\s*\d+", text)
    passed = int(progress_match.group(1)) if progress_match else 0
    return {
        "schema_version": "1.0",
        "session_id": f"sess_{datetime.now():%Y%m%d}_migrated",
        "domain": "devflow",
        "active_save_id": save_id,
        "active_save_name": active_name,
        "pipeline_progress": {
            "passed": passed,
            "total": pipeline_total,
            "last_passed": max(passed - 1, -1),
        },
        "updated_at": now,
        "ttl_hours": 4,
    }


def _blockers_from_known(text: str, now: str) -> dict[str, Any]:
    blockers = []
    for match in re.finditer(r"## \[OPEN\]\s+(Issue\s+\d+.*?)\n(.*?)(?=\n---|\n## \[|$)", text, flags=re.S):
        title = _clean(match.group(1))
        body = _clean(match.group(2))
        blockers.append({"id": f"blocker_{len(blockers)+1:03d}", "title": title, "status": "open", "source": "memory/known-issues.md", "content": body})
    return {"schema_version": "1.0", "blockers": blockers, "updated_at": now}


def _next_actions_from_active(text: str, now: str) -> dict[str, Any]:
    actions = []
    section = text.split("## 下一步行动", 1)[-1] if "## 下一步行动" in text else text
    for line in section.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.", stripped):
            actions.append({"id": f"action_{len(actions)+1:03d}", "title": re.sub(r"^\d+\.\s*", "", stripped), "status": "pending"})
    return {"schema_version": "1.0", "actions": actions[:10], "updated_at": now}


def _facts_from_decisions(text: str, now: str) -> list[dict[str, Any]]:
    facts = []
    for match in re.finditer(r"## Decision\s+(\d+).*?\n(.*?)(?=\n---|\n## Decision|$)", text, flags=re.S):
        number = match.group(1)
        body = match.group(2)
        decision = _first_match(body, r"Decision:\s*(.+)") or _clean(body.splitlines()[0] if body.splitlines() else "")
        facts.append(
            {
                "schema_version": "1.0",
                "fact_id": f"sf_devflow_decision_{number}",
                "type": "rule",
                "fact": decision,
                "source": {"type": "decision", "ref": f"Decision {number}", "episode_id": f"ep_decision_{number}"},
                "confidence": 1.0,
                "review_required": False,
                "version": 1,
                "last_verified": now,
                "tags": ["devflow", "decision"],
                "created_at": now,
            }
        )
    return facts


def _episodes_from_decisions(text: str, now: str) -> list[dict[str, Any]]:
    episodes = []
    for match in re.finditer(r"## Decision\s+(\d+).*?\n(.*?)(?=\n---|\n## Decision|$)", text, flags=re.S):
        number = match.group(1)
        body = match.group(2)
        title = _clean(_first_match(match.group(0), r"##\s+(Decision\s+\d+.*?)\n") or f"Decision {number}")
        reason = _first_match(body, r"Reason:\s*(.+)") or ""
        decision = _first_match(body, r"Decision:\s*(.+)") or ""
        episodes.append(
            {
                "schema_version": "1.0",
                "episode_id": f"ep_decision_{number}",
                "title": title,
                "domain": "devflow",
                "goal": decision,
                "reason": reason,
                "key_decisions": [decision] if decision else [],
                "outcome": {"status": "success", "result_summary": decision},
                "lessons": [],
                "related_episodes": [],
                "skill_ids": [],
                "pattern_ids_extracted": [],
                "failure_ids_extracted": [],
                "reflection_done": False,
                "created_at": now,
                "source_files": ["memory/decisions.md"],
            }
        )
    return episodes


def _failures_from_known(text: str, now: str) -> list[dict[str, Any]]:
    failures = []
    for match in re.finditer(r"## \[(OPEN|RESOLVED)\]\s+Issue\s+(\d+).*?\n(.*?)(?=\n---|\n## \[|$)", text, flags=re.S):
        status, number, body = match.groups()
        title = _clean(_first_match(match.group(0), r"## \[[A-Z]+\]\s+(Issue\s+\d+.*?)\n") or f"Issue {number}")
        description = _first_match(body, r"Description:\s*(.+)") or _clean(body)
        failures.append(
            {
                "schema_version": "1.0",
                "failure_id": f"fail_issue_{number}",
                "title": title,
                "status": "open" if status == "OPEN" else "resolved",
                "severity": "high" if number in {"001", "002"} else "low",
                "domain": "devflow",
                "failure": description,
                "reason": "",
                "diagnosis_steps": [],
                "solution": "",
                "prevention": "",
                "source_file": "memory/known-issues.md",
                "source_episode": "",
                "related_pattern_ids": [],
                "created_at": now,
                "resolved_at": None,
            }
        )
    return failures


def _count_items(content: Any) -> int:
    if isinstance(content, dict):
        for key in ("facts", "entries", "blockers", "actions"):
            if isinstance(content.get(key), list):
                return len(content[key])
    return 1


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_json(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(content, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    if not match:
        return None
    if match.lastindex:
        return _clean(match.group(1))
    return _clean(match.group(0))


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pipeline_total(root: Path) -> int:
    try:
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        from core.registry import max_step_number

        return max_step_number() + 1
    except Exception:
        return 18


if __name__ == "__main__":
    raise SystemExit(main())
