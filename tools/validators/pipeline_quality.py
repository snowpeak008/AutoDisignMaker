#!/usr/bin/env python3
"""Collect repeatable quality metrics for pipeline stages 00-06."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.io import now_iso, read_json  # noqa: E402
from core.paths import DRAFTS_DIR  # noqa: E402
from core.stage import stage_dir  # noqa: E402


EXPECTED_METRIC_FILES = (
    (0, "core_question_coverage_report.json"),
    (1, "core_loop.json"),
    (1, "system_definitions.json"),
    (2, "entity_coverage_report.json"),
    (3, "requirement_quality_report.json"),
    (4, "asset_registry.json"),
    (5, "intelligent_review_report.json"),
)
PLAN_002_MIN_ENTITY_COVERAGE = 0.38


def _stage_path(artifacts_root: Path, stage_number: int, filename: str) -> Path:
    return artifacts_root / f"stage_{stage_number:02d}" / filename


def _has_metric_artifacts(artifacts_root: Path) -> bool:
    return any(
        _stage_path(artifacts_root, stage_number, filename).is_file()
        for stage_number, filename in EXPECTED_METRIC_FILES
    )


def _metric_mtime(artifacts_root: Path) -> float:
    mtimes = [
        _stage_path(artifacts_root, stage_number, filename).stat().st_mtime
        for stage_number, filename in EXPECTED_METRIC_FILES
        if _stage_path(artifacts_root, stage_number, filename).is_file()
    ]
    if mtimes:
        return max(mtimes)
    return artifacts_root.stat().st_mtime if artifacts_root.exists() else 0.0


def discover_artifacts_root() -> Path:
    current_root = stage_dir(0).parent
    if _has_metric_artifacts(current_root):
        return current_root

    candidates: list[Path] = []
    if DRAFTS_DIR.exists():
        for draft_dir in DRAFTS_DIR.iterdir():
            artifacts_root = draft_dir / "outputs" / "artifacts"
            if artifacts_root.is_dir() and _has_metric_artifacts(artifacts_root):
                candidates.append(artifacts_root)
    if candidates:
        return max(candidates, key=_metric_mtime)
    return current_root


def collect_quality_metrics(artifacts_root: Path | None = None) -> dict[str, Any]:
    root = artifacts_root or discover_artifacts_root()
    question_coverage = read_json(_stage_path(root, 0, "core_question_coverage_report.json"), {})
    core_loop = read_json(_stage_path(root, 1, "core_loop.json"), {})
    systems = read_json(_stage_path(root, 1, "system_definitions.json"), {})
    entity_coverage = read_json(_stage_path(root, 2, "entity_coverage_report.json"), {})
    requirement_quality = read_json(_stage_path(root, 3, "requirement_quality_report.json"), {})
    assets = read_json(_stage_path(root, 4, "asset_registry.json"), {})
    program_review = read_json(_stage_path(root, 5, "intelligent_review_report.json"), {})

    asset_items = assets.get("assets", []) if isinstance(assets, dict) else []
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "artifacts_root": str(root),
        "metrics": {
            "question_coverage_rate": question_coverage.get("coverage_rate", 0.0),
            "core_loop_output_rate": 1.0 if core_loop.get("loop") else 0.0,
            "system_definition_rate": systems.get("definition_rate", 0.0),
            "design_entity_coverage_rate": entity_coverage.get("entity_coverage_rate", 0.0),
            "design_entity_count": entity_coverage.get("entity_count", 0),
            "requirement_system_binding_rate": requirement_quality.get("system_binding_rate", 0.0),
            "requirement_placeholder_rate": requirement_quality.get("placeholder_rate", 1.0),
            "asset_count": len(asset_items) if isinstance(asset_items, list) else 0,
            "stage05_warning_count": program_review.get("warning_count", 0),
            "stage05_blocking_issue_count": program_review.get("blocking_issue_count", 0),
        },
        "targets": {
            "question_coverage_rate": ">= 0.55 for v5 Phase 1",
            "core_loop_output_rate": ">= 1.00",
            "design_entity_coverage_rate": ">= 0.38 for PLAN-002; >= 0.75 with real L5 entities",
            "requirement_system_binding_rate": ">= 0.90",
            "requirement_placeholder_rate": "<= 0.25",
            "asset_count": ">= 50 synthetic; >= 80 with real L5 entities",
            "stage05_warning_count": "<= 15 after full configured run",
        },
    }


def check_plan_002(artifacts_root: Path | None = None) -> dict[str, Any]:
    """Check the PLAN-002 entity coverage regression threshold."""
    payload = collect_quality_metrics(artifacts_root)
    metrics = payload["metrics"]
    actual = float(metrics.get("design_entity_coverage_rate") or 0.0)
    passed = actual >= PLAN_002_MIN_ENTITY_COVERAGE
    payload["checks"] = {
        "plan-002": {
            "passed": passed,
            "metric": "design_entity_coverage_rate",
            "actual": actual,
            "minimum": PLAN_002_MIN_ENTITY_COVERAGE,
        }
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(
        description="Collect repeatable quality metrics for pipeline stages 00-06."
    )
    parser.add_argument(
        "--artifacts-dir", type=Path, help="Explicit artifacts root containing stage_00..stage_06."
    )
    parser.add_argument("--check", choices=("plan-002",), help="Run a named regression check.")
    args = parser.parse_args(argv)
    if args.check == "plan-002":
        payload = check_plan_002(args.artifacts_dir)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["checks"]["plan-002"]["passed"] else 1
    print(json.dumps(collect_quality_metrics(args.artifacts_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
