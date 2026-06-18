#!/usr/bin/env python3
"""Inspect failed migrated pipeline reports and print actionable context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BASE_DIR = Path(__file__).parent
ARTIFACTS_DIR = BASE_DIR / "outputs" / "artifacts"


def _load_report(step: int) -> dict:
    path = ARTIFACTS_DIR / f"stage_{step:02d}" / "validation_report.json"
    layer_path = ARTIFACTS_DIR / f"stage_{step:02d}" / "artifact_validation_layer.json"
    if not path.exists():
        return {"step": step, "status": "missing", "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"step": step, "status": "invalid_json", "path": str(path), "error": str(exc)}
    data["path"] = str(path.relative_to(BASE_DIR)).replace("\\", "/")
    if layer_path.exists():
        try:
            data["artifact_layer"] = json.loads(layer_path.read_text(encoding="utf-8"))
        except Exception as exc:
            data["artifact_layer"] = {"status": "invalid_json", "error": str(exc)}
    else:
        data["artifact_layer"] = {"status": "missing", "path": str(layer_path)}
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect migrated pipeline validation reports.")
    parser.add_argument("--step", type=int)
    args = parser.parse_args()

    if args.step is None:
        reports = [_load_report(step) for step in range(16)]
    else:
        reports = [_load_report(args.step)]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
