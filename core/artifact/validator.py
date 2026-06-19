"""Artifact validator — runs 7 validators after each stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.io import now_iso, write_json
from core.stage import stage_dir
from core.artifact.registry_loader import artifacts_for_step, artifacts_by_id, PROJECT_ROOT
from core.artifact.preflight import _knowledge_refs_exist, _schema_refs, _dependency_status_failures
from core.source.importer import refresh_reference_manifest_file_inventory


SCHEMA_RELATIVE_PATH = Path("knowledge") / "schemas"


def _result(status: str, name: str, message: str, *, severity: str = "info") -> dict:
    return {"name": name, "status": status, "severity": severity, "message": message}


def _stage_validation_path(step_number: int) -> Path:
    return stage_dir(step_number) / "artifact_validation_layer.json"


def _stage_reviews_path(step_number: int) -> Path:
    return stage_dir(step_number) / "artifact_reviews.json"


def _stage_layer_manifest_path(step_number: int) -> Path:
    return stage_dir(step_number) / "artifact_layer_manifest.json"


def _run_schema_contract_refs(artifact: dict) -> list[dict]:
    from tools.contract_validator import validate_contract_file
    results = []
    for ref in _schema_refs(artifact):
        contract_path = PROJECT_ROOT / ref["path"]
        schema_path = PROJECT_ROOT / ref["schema"]
        if not contract_path.exists():
            results.append(_result("fail", "schema_contract_validator",
                                   f"Contract file missing: {ref['path']}", severity="error"))
            continue
        if not schema_path.exists():
            results.append(_result("fail", "schema_contract_validator",
                                   f"Schema file missing: {ref['schema']}", severity="error"))
            continue
        errors = validate_contract_file(contract_path, schema_path)
        if errors:
            results.append(_result("fail", "schema_contract_validator",
                                   f"{ref['path']} failed {ref['schema']}: {errors[:5]}", severity="error"))
        else:
            results.append(_result("pass", "schema_contract_validator",
                                   f"{ref['path']} matches {ref['schema']}."))
    return results


def _load_stage_report(step_number: int) -> dict | None:
    path = stage_dir(step_number) / "validation_report.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_json", "valid": False}


def run_artifact_validators(step_number: int) -> dict[str, Any]:
    artifacts = artifacts_for_step(step_number)
    stage_path = stage_dir(step_number)
    stage_report = _load_stage_report(step_number)
    review_path = _stage_reviews_path(step_number)
    manifest_path = _stage_layer_manifest_path(step_number)
    validation_results = []
    by_id = artifacts_by_id()

    for artifact in artifacts:
        aid = artifact["id"]
        results = []

        # validator_first_contract
        if artifact.get("validators") and artifact.get("reviewers") and artifact.get("tasks"):
            results.append(_result("pass", "validator_first_contract", "Artifact declares validators, reviewers, and tasks."))
        else:
            results.append(_result("fail", "validator_first_contract", "Artifact contract is incomplete.", severity="error"))

        # stage_files_validator
        if stage_report and stage_report.get("status") == "success" and stage_report.get("valid") is True:
            required = stage_path / ("migration_audit.json" if step_number == 15 else "artifact_index.json")
            reference = stage_path / "reference_manifest.json"
            if required.exists() and reference.exists():
                results.append(_result("pass", "stage_files_validator", "Stage files satisfy the migrated contract."))
            else:
                results.append(_result("fail", "stage_files_validator",
                                       "Required stage files are missing.", severity="error"))
        else:
            results.append(_result("fail", "stage_files_validator",
                                   "Stage validation report is missing or failed.", severity="error"))

        # review_report_validator
        if review_path.exists():
            rr = json.loads(review_path.read_text(encoding="utf-8"))
            if rr.get("status") == "success":
                results.append(_result("pass", "review_report_validator", "Review report passed."))
            else:
                results.append(_result("fail", "review_report_validator", "Review report failed.", severity="error"))
        else:
            results.append(_result("fail", "review_report_validator", "Review report is missing.", severity="error"))

        # manifest_validator
        if manifest_path.exists():
            mp = json.loads(manifest_path.read_text(encoding="utf-8"))
            if mp.get("artifacts") and mp.get("tasks"):
                results.append(_result("pass", "manifest_validator", "Artifact layer manifest declares artifacts and tasks."))
            else:
                results.append(_result("fail", "manifest_validator", "Artifact layer manifest is incomplete.", severity="error"))
        else:
            results.append(_result("fail", "manifest_validator", "Artifact layer manifest is missing.", severity="error"))

        # knowledge_refs_validator
        mk = _knowledge_refs_exist(artifact)
        if mk:
            results.append(_result("fail", "knowledge_refs_validator", f"Missing knowledge references: {mk}", severity="error"))
        else:
            results.append(_result("pass", "knowledge_refs_validator", "Knowledge references exist."))

        # schema_contract_validator
        if "schema_contract_validator" in artifact.get("validators", []):
            schema_results = _run_schema_contract_refs(artifact)
            results.extend(schema_results if schema_results else [
                _result("fail", "schema_contract_validator",
                        "schema_contract_validator declared but no schema_refs provided.", severity="error")
            ])

        # dependency_status_validator
        df = _dependency_status_failures(artifact, by_id)
        if df:
            results.append(_result("fail", "dependency_status_validator", f"Unsatisfied dependencies: {df}", severity="error"))
        else:
            results.append(_result("pass", "dependency_status_validator", "Upstream artifact validations passed."))

        status = "fail" if any(r["status"] == "fail" for r in results) else "pass"
        validation_results.append({"artifact_id": aid, "status": status, "results": results})

    report = {
        "step": step_number, "timestamp": now_iso(),
        "status": "failed" if any(v["status"] == "fail" for v in validation_results) else "success",
        "phase": "validation", "validations": validation_results,
    }
    write_json(_stage_validation_path(step_number), report)
    refresh_reference_manifest_file_inventory(step_number)
    if report["status"] != "success":
        raise RuntimeError(f"Artifact validation failed for stage {step_number:02d}")
    return report
