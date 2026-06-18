"""Build helper for AutoDesignMaker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "AutoDesignMaker",
        "--paths",
        str(PROJECT_ROOT),
        "--hidden-import",
        "design_tool.ui.app_window",
        "--add-data",
        f"{PROJECT_ROOT / 'data'};data",
        str(PROJECT_ROOT / "src" / "gui_app.py"),
    ]
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
