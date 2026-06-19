"""Artifact reviewer — runs 4 reviewers after each stage."""

from __future__ import annotations

import json
from typing import Any

from core.io import file_manifest, now_iso, write_json
from core.stage import stage_dir
from core.artifact.registry_loader import artifacts_by_id, artifacts_for_step
from core.artifact.preflight import _dependency_status_failures


def _result(status: str, name: str, message: str, *, severity: str = "info") -> dict[str, str]:
    return {"name": name, "status": status, "severity": severity, "message": message}


def _stage_layer_manifest_path(step_number: int) -> str:
    from core.stage import stage_dir
    return stage_dir(step_number) / "artifact_layer_manifest.json"


def _stage_reviews_path(step_number: int):
    return stage_dir(step_number) / "artifact_reviews.json"


def _load_stage_report(step_number: int) -> dict[str, Any] | None:
    path = stage_dir(step_number) / "validation_report.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_json", "valid": False}


def write_stage_artifact_manifest(step_number: int) -> dict[str, Any]:
    artifacts = artifacts_for_step(step_number)
    stage_path = stage_dir(step_number)
    tasks = [dict(task, artifact_id=a["id"]) for a in artifacts for task in a.get("tasks", [])]
    manifest = {
        "step": step_number, "timestamp": now_iso(), "stage_dir": str(stage_path),
        "artifacts": artifacts, "tasks": tasks,
        "file_manifest": file_manifest(stage_path) if stage_path.exists() else [],
    }
    write_json(_stage_layer_manifest_path(step_number), manifest)
    return manifest


def run_review_pipeline(step_number: int) -> dict[str, Any]:
    manifest = write_stage_artifact_manifest(step_number)
    stage_path = stage_dir(step_number)
    by_id = artifacts_by_id()
    stage_report = _load_stage_report(step_number)
    reviews = []

    for artifact in manifest["artifacts"]:
        aid = artifact["id"]
        results = []

        # structure_reviewer
        if stage_path.exists():
            results.append(_result("pass", "structure_reviewer", "Stage artifact directory exists."))
        else:
            results.append(_result("fail", "structure_reviewer", "Stage artifact directory is missing.", severity="error"))
        required = stage_path / ("migration_audit.json" if step_number == 15 else "artifact_index.json")
        if required.exists():
            results.append(_result("pass", "structure_reviewer", f"Required file exists: {required.name}."))
        else:
            results.append(_result("fail", "structure_reviewer", f"Required file missing: {required.name}.", severity="error"))
        if (stage_path / "reference_manifest.json").exists():
            results.append(_result("pass", "structure_reviewer", "Required file exists: reference_manifest.json."))
        else:
            results.append(_result("fail", "structure_reviewer", "Required file missing: reference_manifest.json.", severity="error"))

        # source_trace_reviewer
        if stage_report is None:
            results.append(_result("fail", "source_trace_reviewer", "Stage validation_report.json is missing.", severity="error"))
        elif stage_report.get("status") == "success" and stage_report.get("valid") is True:
            imported = len(stage_report.get("imported_sources", []))
            upstream = len(stage_report.get("imported_upstream_artifacts", []))
            missing = stage_report.get("missing_groups", [])
            optional_missing = stage_report.get("optional_missing_groups", [])
            if imported:
                results.append(_result("pass", "source_trace_reviewer", f"{imported} source group(s) imported."))
            elif upstream:
                results.append(_result("pass", "source_trace_reviewer", f"{upstream} upstream artifact(s) imported."))
            elif missing or optional_missing or step_number == 15:
                results.append(_result("pass", "source_trace_reviewer", "Missing sources explicitly recorded.", severity="warning"))
            else:
                results.append(_result("fail", "source_trace_reviewer", "No imported sources and no missing source groups recorded.", severity="error"))
        else:
            results.append(_result("fail", "source_trace_reviewer", "Stage validation report is not successful.", severity="error"))

        # task_reviewer
        task_ids = [t.get("id") for t in artifact.get("tasks", []) if t.get("id")]
        if task_ids and len(task_ids) == len(set(task_ids)):
            results.append(_result("pass", "task_reviewer", f"{len(task_ids)} task(s) declared."))
        else:
            results.append(_result("fail", "task_reviewer", "Tasks are missing or duplicated.", severity="error"))

        # dependency_reviewer
        unknown_deps = [d for d in artifact.get("depends_on", []) if d not in by_id]
        if unknown_deps:
            results.append(_result("fail", "dependency_reviewer", f"Unknown dependencies: {unknown_deps}", severity="error"))
        else:
            failures = _dependency_status_failures(artifact, by_id)
            if failures:
                results.append(_result("fail", "dependency_reviewer", f"Unsatisfied dependencies: {failures}", severity="error"))
            else:
                results.append(_result("pass", "dependency_reviewer", "Dependencies resolve and upstream validations passed."))

        status = "fail" if any(r["status"] == "fail" for r in results) else "pass"
        reviews.append({"artifact_id": aid, "status": status, "results": results})

    report = {
        "step": step_number, "timestamp": now_iso(),
        "status": "failed" if any(r["status"] == "fail" for r in reviews) else "success",
        "phase": "review", "reviews": reviews,
    }
    write_json(_stage_reviews_path(step_number), report)
    if report["status"] != "success":
        raise RuntimeError(f"Artifact review failed for stage {step_number:02d}")
    return report
