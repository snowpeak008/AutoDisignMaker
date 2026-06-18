#!/usr/bin/env python3
"""Export the current design data into a DevFlow Stage 00 Concept package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.plugins.adapters.design_export_adapter import export_concept_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", type=Path, default=None, help="Optional package directory override.")
    parser.add_argument(
        "--no-workspace-mirror",
        action="store_true",
        help="Skip writing the workspace/source_artifacts mirror.",
    )
    args = parser.parse_args()

    result = export_concept_package(
        target_dir=args.target_dir,
        mirror_workspace=not args.no_workspace_mirror,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
