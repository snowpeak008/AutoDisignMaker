"""Scan project source files for hardcoded legacy absolute paths."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SKIP_PARTS = {
    ".git",
    "__pycache__",
    "build",
    "dist",
    "_archive",
    "workspace",
}

TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".toml",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".ps1",
    ".spec",
    ".csv",
}

PATTERNS = [
    re.compile(r"E:\\\\workwork\\\\CrewAi\\\\newdemotower", re.IGNORECASE),
    re.compile(r"E:/workwork/CrewAi/newdemotower", re.IGNORECASE),
    re.compile(r"E:\\\\workwork\\\\CrewAi\\\\.*new_tools", re.IGNORECASE),
    re.compile(r"E:/workwork/CrewAi/.*/new_tools", re.IGNORECASE),
    re.compile(r"newdemotower[\\\\/]工程运行文件", re.IGNORECASE),
    re.compile(r"全流程ai设计[\\\\/]new_tools", re.IGNORECASE),
]


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if any(part in SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def scan(root: Path = PROJECT_ROOT) -> list[str]:
    hits: list[str] = []
    for path in iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            hits.append(f"{path.relative_to(root)}: read failed: {exc}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in PATTERNS):
                hits.append(f"{path.relative_to(root)}:{line_number}: {line.strip()[:240]}")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check hardcoded legacy absolute paths.")
    parser.add_argument("--allow-docs", action="store_true", help="Do not fail on documentation hits.")
    args = parser.parse_args(argv)
    hits = scan()
    if args.allow_docs:
        hits = [hit for hit in hits if not hit.lower().startswith("docs")]
    if hits:
        print("Hardcoded legacy path scan found matches:")
        for hit in hits:
            safe_hit = hit.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8"
            )
            print(f"- {safe_hit}")
        return 1
    print("No hardcoded legacy absolute paths found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
