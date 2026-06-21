"""Artifact preflight contract validator."""

from __future__ import annotations

from typing import Any

from core.io import now_iso, write_json
from core.paths import OUTPUTS_DIR, PROJECT_ROOT
from core.stage import stage_dir
from core.artifact.registry_loader import (
    KNOWN_REVIEWERS, KNOWN_VALIDATORS,
    artifacts_by_id, artifacts_for_step, load_registry,
)

LAYER_OUTPUT_DIR = OUTPUTS_DIR / "artifact_layer"


def _knowledge_refs_exist(artifact: dict[str, Any]) -> list[str]:
    return [p for p in artifact.get("knowledge_refs", []) if not (PROJECT_ROOT / p).exists()]


def _schema_refs(artifact: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"path": str(r.get("path") or ""), "schema": str(r.get("schema") or ""),
         "description": str(r.get("description") or "")}
        for r in artifact.get("schema_refs", []) if isinstance(r, dict)
    ]


def _schema_ref_preflight_errors(artifact: dict[str, Any]) -> list[str]:
    if "schema_contract_validator" not in artifact.get("validators", []):
        return []
    refs = _schema_refs(artifact)
    if not refs:
        return ["schema_contract_validator declared without schema_refs"]
    errors = []
    for r in refs:
        if not r["path"]:
            errors.append("schema_ref is missing path")
        if not r["schema"]:
            errors.append(f"schema_ref for {r['path'] or '<missing>'} is missing schema")
        elif not (PROJECT_ROOT / r["schema"]).exists():
            errors.append(f"schema file does not exist: {r['schema']}")
    return errors


def _dependency_status_failures(artifact: dict[str, Any], by_id: dict) -> list[str]:
    import json
    failures = []
    for dep_id in artifact.get("depends_on", []):
        dep = by_id.get(dep_id)
        if dep is None:
            failures.append(f"{dep_id}: unknown dependency")
            continue
        dep_stage = int(dep["stage"])
        dep_report_path = stage_dir(dep_stage) / "artifact_validation_layer.json"
        if not dep_report_path.exists():
            failures.append(f"{dep_id}: missing artifact validation report")
            continue
        try:
            rep = json.loads(dep_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append(f"{dep_id}: artifact validation report is invalid JSON")
            continue
        if rep.get("status") != "success":
            failures.append(f"{dep_id}: artifact validation status is {rep.get('status')}")
    return failures


def preflight_stage_contract(step_number: int) -> dict[str, Any]:
    artifacts = artifacts_for_step(step_number)
    errors: list[str] = []
    if not artifacts:
        errors.append(f"No artifacts declared for stage {step_number:02d}.")
    by_id = artifacts_by_id()
    registry_ids = set(by_id)
    task_ids: set[str] = set()
    for artifact in artifacts:
        aid = artifact.get("id", "<missing>")
        if not artifact.get("tasks"):
            errors.append(f"{aid} has no tasks.")
        if not artifact.get("reviewers"):
            errors.append(f"{aid} has no reviewers.")
        if not artifact.get("validators"):
            errors.append(f"{aid} has no validators.")
        unknown_r = sorted(set(artifact.get("reviewers", [])) - KNOWN_REVIEWERS)
        unknown_v = sorted(set(artifact.get("validators", [])) - KNOWN_VALIDATORS)
        if unknown_r:
            errors.append(f"{aid} has unknown reviewers: {unknown_r}")
        if unknown_v:
            errors.append(f"{aid} has unknown validators: {unknown_v}")
        for task in artifact.get("tasks", []):
            tid = task.get("id")
            if not tid:
                errors.append(f"{aid} has a task without id.")
                continue
            if tid in task_ids:
                errors.append(f"Duplicate task id in stage {step_number:02d}: {tid}")
            task_ids.add(tid)
        for dep_id in artifact.get("depends_on", []):
            if dep_id not in registry_ids:
                errors.append(f"{aid} depends on unknown artifact {dep_id}")
        mk = _knowledge_refs_exist(artifact)
        if mk:
            errors.append(f"{aid} references missing knowledge files: {mk}")
        se = _schema_ref_preflight_errors(artifact)
        if se:
            errors.append(f"{aid} has invalid schema refs: {se}")
        df = _dependency_status_failures(artifact, by_id)
        if df:
            errors.append(f"{aid} has unsatisfied dependencies: {df}")

    report = {
        "step": step_number, "timestamp": now_iso(),
        "status": "failed" if errors else "success",
        "phase": "validator_first_preflight",
        "artifacts": [a.get("id") for a in artifacts],
        "errors": errors, "warnings": [],
    }
    LAYER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(LAYER_OUTPUT_DIR / f"preflight_stage_{step_number:02d}.json", report)
    if errors:
        raise RuntimeError(f"Artifact preflight failed for stage {step_number:02d}: {errors}")
    return report
