#!/usr/bin/env python3
"""Verify the PyInstaller one-file build artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _archive_names(exe_path: Path) -> set[str]:
    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ModuleNotFoundError as exc:
        raise RuntimeError("Build verification requires PyInstaller to be installed.") from exc

    try:
        archive = CArchiveReader(str(exe_path))
    except Exception as exc:  # noqa: BLE001 - include path context for CLI users.
        raise RuntimeError(f"Failed to read PyInstaller archive {exe_path}: {exc}") from exc
    return {str(name).replace("\\", "/") for name in archive.toc}


def _contains(names: set[str], prefix: str) -> bool:
    normalized = prefix.strip("/").replace("\\", "/")
    return any(name == normalized or name.startswith(f"{normalized}/") for name in names)


def verify_executable(exe_path: Path) -> list[str]:
    errors: list[str] = []
    if not exe_path.exists():
        return [f"Executable not found: {exe_path}"]
    if exe_path.stat().st_size < 1_000_000:
        errors.append(f"Executable is unexpectedly small: {exe_path.stat().st_size} bytes")

    names = _archive_names(exe_path)
    required_prefixes = [
        "data/design/domains",
        "data/schemas",
        "config/app.toml",
        "gui_app",
    ]
    for prefix in required_prefixes:
        if not _contains(names, prefix):
            errors.append(f"Missing bundled item: {prefix}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", nargs="?", default=str(PROJECT_ROOT / "dist" / "AutoDesignMaker.exe"))
    args = parser.parse_args(argv)

    exe_path = Path(args.exe)
    if not exe_path.is_absolute():
        exe_path = PROJECT_ROOT / exe_path

    errors = verify_executable(exe_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Build verification passed: {exe_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
