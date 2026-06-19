#!/usr/bin/env python3
"""Backfill save_id into execution-object stores inside save workspaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STORE_RELATIVE_PATH = Path("workspace") / "outputs" / "execution_objects" / "execution_objects.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Store must be a JSON object: {path}")
    return data


def iter_save_stores(save_root: Path) -> list[tuple[str, Path, dict[str, Any] | None]]:
    stores: list[tuple[str, Path, dict[str, Any] | None]] = []
    for save_dir in sorted(path for path in save_root.glob("save_*") if path.is_dir()):
        store_path = save_dir / STORE_RELATIVE_PATH
        stores.append((save_dir.name, store_path, _load_json(store_path)))
    return stores


def status_for(save_id: str, data: dict[str, Any] | None) -> str:
    if data is None:
        return "missing"
    current = data.get("save_id")
    if current == save_id:
        return "consistent"
    if current:
        return f"mismatch:{current}"
    return "missing_save_id"


def migrate(save_root: Path, *, apply: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for save_id, store_path, data in iter_save_stores(save_root):
        status = status_for(save_id, data)
        action = "none"
        if data is not None and status == "missing_save_id":
            action = "would_update"
            if apply:
                backup_path = store_path.with_name(store_path.name + ".bak")
                if not backup_path.exists():
                    backup_path.write_text(store_path.read_text(encoding="utf-8-sig"), encoding="utf-8")
                data["save_id"] = save_id
                store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                action = "updated"
        rows.append({
            "save_id": save_id,
            "path": store_path.as_posix(),
            "status": status,
            "action": action,
        })
    return rows


def write_markdown(rows: list[dict[str, str]], report_path: Path) -> None:
    lines = [
        "# Execution Object Save ID Migration Dry Run",
        "",
        "| save_id | status | action | path |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| `{row['save_id']}` | {row['status']} | {row['action']} | `{row['path']}` |")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    save_root = args.project_root / "save"
    rows = migrate(save_root, apply=args.apply)
    if args.report:
        write_markdown(rows, args.report)
    for row in rows:
        print(f"{row['save_id']} {row['status']} {row['action']} {row['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
