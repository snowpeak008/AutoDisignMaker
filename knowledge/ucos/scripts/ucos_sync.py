from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ucos.engines.memory_engine import MemoryEngine, MemoryTier
from ucos.output.context_builder import build
from ucos.output.formatters import agents_md, json_format, summary


ENTRY_FILES = ["CLAUDE.md", "AGENTS.md", "README.md"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", choices=["session_start", "session_end", "post_tool", "pre_tool", "code_changed"], default="session_start")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--format", choices=["json", "agents-md", "summary"], default="summary")
    parser.add_argument("--flush-facts", action="store_true")
    args = parser.parse_args(argv)
    root = _find_root(Path.cwd())
    payload = _read_stdin_json()
    result = handle_event(root, args.event, payload)
    if args.event == "session_start":
        sync_entry_files(root)
    if args.print_summary:
        context = build(root)
        print(_format(context, args.format))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


def handle_event(root: str | Path, event: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    project_root = Path(root)
    payload = payload or {}
    memory = MemoryEngine(project_root)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if event == "session_start":
        memory.write(MemoryTier.WORKING, {"updated_at": now}, "session_start", 0.5)
        return {"ok": True, "event": event}
    if event == "post_tool":
        memory.write(MemoryTier.WORKING, {"last_tool_event": {"event": event, "payload": payload, "updated_at": now}}, "post_tool", 0.5)
        return {"ok": True, "event": event}
    if event == "pre_tool":
        return {"ok": True, "event": event}
    if event == "code_changed":
        memory.write(MemoryTier.SHORT_TERM, {"type": "recent_event", "title": "Code changed", "content": json.dumps(payload, ensure_ascii=False), "tags": ["code_changed"]}, "code_changed", 0.6)
        return {"ok": True, "event": event}
    if event == "session_end":
        checkpoint = checkpoint_working(project_root)
        decayed = memory.decay_pass(MemoryTier.SHORT_TERM)
        memory.write(MemoryTier.WORKING, {"last_session_end": now}, "session_end", 0.5)
        return {"ok": True, "event": event, "checkpoint": str(checkpoint), "decayed": decayed}
    return {"ok": False, "event": event, "error": "unknown event"}


def sync_entry_files(root: Path) -> None:
    context = build(root)
    body = agents_md.format_context(context)
    header = (
        "<!-- 此文件由 ucos/scripts/ucos_sync.py 自动生成，请勿直接编辑 -->\n"
        "<!-- 编辑源: ucos/ 与 memory/AI_ENTRY.md；运行 python ucos/scripts/ucos_sync.py --event session_start 同步 -->\n\n"
    )
    ai_entry = root / "memory" / "AI_ENTRY.md"
    legacy = ai_entry.read_text(encoding="utf-8") if ai_entry.exists() else ""
    content = header + body + "\n---\n\n" + legacy
    for name in ENTRY_FILES:
        (root / name).write_text(content, encoding="utf-8")


def checkpoint_working(root: Path) -> Path:
    source = root / "ucos" / "knowledge" / "working"
    checkpoints = root / "ucos" / "_checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    target = checkpoints / datetime.now().strftime("%Y%m%d_%H%M%S")
    if source.exists():
        shutil.copytree(source, target, dirs_exist_ok=True)
    all_checkpoints = sorted([item for item in checkpoints.iterdir() if item.is_dir()], key=lambda p: p.stat().st_mtime)
    while len(all_checkpoints) > 10:
        shutil.rmtree(all_checkpoints.pop(0))
    return target


def _format(context: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json_format.format_context(context)
    if fmt == "agents-md":
        return agents_md.format_context(context)
    return summary.format_context(context)


def _read_stdin_json() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _find_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "memory").exists() and (candidate / "sync_entry.py").exists():
            return candidate
    return current


if __name__ == "__main__":
    raise SystemExit(main())
