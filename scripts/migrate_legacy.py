"""Copy legacy project data into the AutoDesignMaker workspace.

The tool is intentionally conservative:
- defaults to dry-run,
- skips build/cache artifacts,
- never deletes source files,
- writes a migration report under workspace/outputs.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXCLUDES = {
    "__pycache__",
    ".git",
    "build",
    "dist",
}


@dataclass
class MigrationItem:
    source: str
    target: str
    size: int
    action: str


def should_skip(path: Path) -> bool:
    return any(part in DEFAULT_EXCLUDES for part in path.parts)


def plan_copy(source: Path, target: Path) -> list[MigrationItem]:
    items: list[MigrationItem] = []
    if source.is_file():
        items.append(MigrationItem(str(source), str(target), source.stat().st_size, "copy"))
        return items
    for path in source.rglob("*"):
        if not path.is_file() or should_skip(path.relative_to(source)):
            continue
        relative = path.relative_to(source)
        items.append(MigrationItem(str(path), str(target / relative), path.stat().st_size, "copy"))
    return items


def write_report(items: list[MigrationItem], *, source: Path, target: Path, dry_run: bool) -> Path:
    report = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "dryRun": dry_run,
        "source": str(source),
        "target": str(target),
        "fileCount": len(items),
        "totalBytes": sum(item.size for item in items),
        "items": [asdict(item) for item in items[:1000]],
        "truncated": len(items) > 1000,
    }
    report_path = PROJECT_ROOT / "workspace" / "outputs" / "migration_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def run_migration(source: Path, target: Path, *, dry_run: bool = True) -> tuple[list[MigrationItem], Path]:
    source = source.resolve()
    target = (PROJECT_ROOT / target).resolve() if not target.is_absolute() else target.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    items = plan_copy(source, target)
    if not dry_run:
        for item in items:
            source_path = Path(item.source)
            target_path = Path(item.target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
    report_path = write_report(items, source=source, target=target, dry_run=dry_run)
    return items, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy files into AutoDesignMaker.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--apply", action="store_true", help="Actually copy files.")
    args = parser.parse_args(argv)

    dry_run = not args.apply or args.dry_run
    items, report_path = run_migration(args.source, args.target, dry_run=dry_run)
    print(f"Migration plan: {len(items)} files, {sum(item.size for item in items)} bytes")
    print(f"Report: {report_path}")
    print("Mode: dry-run" if dry_run else "Mode: apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

