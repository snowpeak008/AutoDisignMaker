#!/usr/bin/env python3
"""Artifact/task/reviewer/validator runtime for the migrated pipeline."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from steps.common import (
    ARTIFACTS_DIR,
    BASE_DIR,
    OUTPUTS_DIR,
    file_manifest,
    now_iso,
    refresh_reference_manifest_file_inventory,
    rel,
    stage_dir,
    write_json,
)
from tools.contract_validator import validate_contract_file


REGISTRY_PATH = BASE_DIR / "artifact_layer" / "registry.json"
GRAPH_PATH = BASE_DIR / "artifact_layer" / "dependency_graph.json"
OUTPUT_GRAPH_PATH = OUTPUTS_DIR / "dependency_graph.json"
LAYER_OUTPUT_DIR = OUTPUTS_DIR / "artifact_layer"

KNOWN_REVIEWERS = {
    "structure_reviewer",
    "source_trace_reviewer",
    "task_reviewer",
    "dependency_reviewer",
}

KNOWN_VALIDATORS = {
    "validator_first_contract",
    "stage_files_validator",
    "review_report_validator",
    "manifest_validator",
    "schema_contract_validator",
    "knowledge_refs_validator",
    "dependency_status_validator",
}


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing artifact layer registry: {REGISTRY_PATH}")
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    artifacts = data.get("artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("artifact_layer/registry.json must declare a non-empty artifacts list.")
    return data


def artifacts_by_id(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry or load_registry()
    result: dict[str, dict[str, Any]] = {}
    for artifact in registry["artifacts"]:
        artifact_id = artifact.get("id")
        if not artifact_id:
            raise RuntimeError("Every artifact must have an id.")
        if artifact_id in result:
            raise RuntimeError(f"Duplicate artifact id: {artifact_id}")
        result[artifact_id] = artifact
    return result


def artifacts_for_step(step_number: int, registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    registry = registry or load_registry()
    return [artifact for artifact in registry["artifacts"] if int(artifact.get("stage", -1)) == step_number]


def build_dependency_graph(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    by_id = artifacts_by_id(registry)
    nodes = []
    edges = []
    errors = []

    for artifact in registry["artifacts"]:
        artifact_id = artifact["id"]
        nodes.append({
            "id": artifact_id,
            "stage": artifact["stage"],
            "kind": artifact.get("kind", "artifact"),
            "tasks": [task.get("id") for task in artifact.get("tasks", [])],
        })
        for dep_id in artifact.get("depends_on", []):
            if dep_id not in by_id:
                errors.append(f"{artifact_id} depends on unknown artifact {dep_id}")
            edges.append({"from": dep_id, "to": artifact_id})

    order, topo_errors = topological_artifact_order(registry)
    errors.extend(topo_errors)
    return {
        "version": registry.get("version", 1),
        "nodes": sorted(nodes, key=lambda node: (int(node["stage"]), node["id"])),
        "edges": sorted(edges, key=lambda edge: (edge["from"], edge["to"])),
        "topological_order": order,
        "errors": errors,
    }


def topological_artifact_order(registry: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    registry = registry or load_registry()
    by_id = artifacts_by_id(registry)
    indegree = {artifact_id: 0 for artifact_id in by_id}
    dependents: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []

    for artifact_id, artifact in by_id.items():
        for dep_id in artifact.get("depends_on", []):
            if dep_id not in by_id:
                errors.append(f"{artifact_id} depends on unknown artifact {dep_id}")
                continue
            dependents[dep_id].append(artifact_id)
            indegree[artifact_id] += 1

    def sort_key(artifact_id: str) -> tuple[int, str]:
        artifact = by_id[artifact_id]
        return int(artifact.get("stage", 9999)), artifact_id

    ready = deque(sorted((item for item, degree in indegree.items() if degree == 0), key=sort_key))
    order: list[str] = []
    while ready:
        artifact_id = ready.popleft()
        order.append(artifact_id)
        for child_id in sorted(dependents[artifact_id], key=sort_key):
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                ready.append(child_id)
        ready = deque(sorted(ready, key=sort_key))

    if len(order) != len(by_id):
        cycle_nodes = sorted(artifact_id for artifact_id, degree in indegree.items() if degree > 0)
        errors.append(f"Dependency cycle detected: {cycle_nodes}")
    return order, errors


def emit_dependency_graph() -> dict[str, Any]:
    graph = build_dependency_graph()
    write_json(GRAPH_PATH, graph)
    write_json(OUTPUT_GRAPH_PATH, graph)
    if graph["errors"]:
        raise RuntimeError("Artifact dependency graph is invalid: " + "; ".join(graph["errors"]))
    return graph


def topological_step_order(from_step: int, stop_step: int) -> list[int]:
    registry = load_registry()
    artifact_order, errors = topological_artifact_order(registry)
    if errors:
        raise RuntimeError("Artifact dependency graph is invalid: " + "; ".join(errors))
    by_id = artifacts_by_id(registry)
    ordered_steps: list[int] = []
    seen: set[int] = set()
    for artifact_id in artifact_order:
        step_number = int(by_id[artifact_id]["stage"])
        if from_step <= step_number <= stop_step and step_number not in seen:
            ordered_steps.append(step_number)
            seen.add(step_number)
    return ordered_steps


def _stage_layer_manifest_path(step_number: int) -> Path:
    return stage_dir(step_number) / "artifact_layer_manifest.json"


def _stage_reviews_path(step_number: int) -> Path:
    return stage_dir(step_number) / "artifact_reviews.json"


def _stage_validation_path(step_number: int) -> Path:
    return stage_dir(step_number) / "artifact_validation_layer.json"


def _knowledge_refs_exist(artifact: dict[str, Any]) -> list[str]:
    missing = []
    for ref_path in artifact.get("knowledge_refs", []):
        if not (BASE_DIR / ref_path).exists():
            missing.append(ref_path)
    return missing


def _schema_refs(artifact: dict[str, Any]) -> list[dict[str, str]]:
    refs = artifact.get("schema_refs", [])
    if not isinstance(refs, list):
        return []
    result: list[dict[str, str]] = []
    for item in refs:
        if not isinstance(item, dict):
            continue
        result.append({
            "path": str(item.get("path") or ""),
            "schema": str(item.get("schema") or ""),
            "description": str(item.get("description") or ""),
        })
    return result


def _schema_ref_preflight_errors(artifact: dict[str, Any]) -> list[str]:
    if "schema_contract_validator" not in artifact.get("validators", []):
        return []
    refs = _schema_refs(artifact)
    if not refs:
        return ["schema_contract_validator declared without schema_refs"]
    errors = []
    for ref_item in refs:
        contract_path = ref_item["path"]
        schema_path = ref_item["schema"]
        if not contract_path:
            errors.append("schema_ref is missing path")
        if not schema_path:
            errors.append(f"schema_ref for {contract_path or '<missing>'} is missing schema")
        elif not (BASE_DIR / schema_path).exists():
            errors.append(f"schema file does not exist: {schema_path}")
    return errors


def _run_schema_contract_refs(artifact: dict[str, Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for ref_item in _schema_refs(artifact):
        contract_path = BASE_DIR / ref_item["path"]
        schema_path = BASE_DIR / ref_item["schema"]
        if not contract_path.exists():
            results.append(_result(
                "fail",
                "schema_contract_validator",
                f"Contract file missing: {ref_item['path']}",
                severity="error",
            ))
            continue
        if not schema_path.exists():
            results.append(_result(
                "fail",
                "schema_contract_validator",
                f"Schema file missing: {ref_item['schema']}",
                severity="error",
            ))
            continue
        errors = validate_contract_file(contract_path, schema_path)
        if errors:
            results.append(_result(
                "fail",
                "schema_contract_validator",
                f"{ref_item['path']} failed {ref_item['schema']}: {errors[:5]}",
                severity="error",
            ))
        else:
            results.append(_result(
                "pass",
                "schema_contract_validator",
                f"{ref_item['path']} matches {ref_item['schema']}.",
            ))
    return results


def _dependency_status_failures(artifact: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for dep_id in artifact.get("depends_on", []):
        dep = by_id.get(dep_id)
        if dep is None:
            failures.append(f"{dep_id}: unknown dependency")
            continue
        dep_stage = int(dep["stage"])
        dep_report_path = stage_dir(dep_stage) / "artifact_validation_layer.json"
        if not dep_report_path.exists():
            failures.append(f"{dep_id}: missing artifact validation report at {rel(dep_report_path)}")
            continue
        try:
            dep_report = json.loads(dep_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append(f"{dep_id}: artifact validation report is invalid JSON")
            continue
        if dep_report.get("status") != "success":
            failures.append(f"{dep_id}: artifact validation status is {dep_report.get('status')}")
    return failures


def preflight_stage_contract(step_number: int) -> dict[str, Any]:
    artifacts = artifacts_for_step(step_number)
    errors: list[str] = []
    warnings: list[str] = []

    if not artifacts:
        errors.append(f"No artifacts declared for stage {step_number:02d}.")

    by_id = artifacts_by_id()
    registry_ids = set(by_id)
    task_ids: set[str] = set()
    for artifact in artifacts:
        artifact_id = artifact.get("id", "<missing>")
        tasks = artifact.get("tasks", [])
        reviewers = artifact.get("reviewers", [])
        validators = artifact.get("validators", [])
        if not tasks:
            errors.append(f"{artifact_id} has no tasks.")
        if not reviewers:
            errors.append(f"{artifact_id} has no reviewers.")
        if not validators:
            errors.append(f"{artifact_id} has no validators.")
        unknown_reviewers = sorted(set(reviewers) - KNOWN_REVIEWERS)
        unknown_validators = sorted(set(validators) - KNOWN_VALIDATORS)
        if unknown_reviewers:
            errors.append(f"{artifact_id} has unknown reviewers: {unknown_reviewers}")
        if unknown_validators:
            errors.append(f"{artifact_id} has unknown validators: {unknown_validators}")
        for task in tasks:
            task_id = task.get("id")
            if not task_id:
                errors.append(f"{artifact_id} has a task without id.")
                continue
            if task_id in task_ids:
                errors.append(f"Duplicate task id in stage {step_number:02d}: {task_id}")
            task_ids.add(task_id)
        for dep_id in artifact.get("depends_on", []):
            if dep_id not in registry_ids:
                errors.append(f"{artifact_id} depends on unknown artifact {dep_id}")
        missing_knowledge = _knowledge_refs_exist(artifact)
        if missing_knowledge:
            errors.append(f"{artifact_id} references missing knowledge files: {missing_knowledge}")
        schema_errors = _schema_ref_preflight_errors(artifact)
        if schema_errors:
            errors.append(f"{artifact_id} has invalid schema refs: {schema_errors}")
        dependency_failures = _dependency_status_failures(artifact, by_id)
        if dependency_failures:
            errors.append(f"{artifact_id} has unsatisfied dependencies: {dependency_failures}")

    report = {
        "step": step_number,
        "timestamp": now_iso(),
        "status": "failed" if errors else "success",
        "phase": "validator_first_preflight",
        "artifacts": [artifact.get("id") for artifact in artifacts],
        "errors": errors,
        "warnings": warnings,
    }
    LAYER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(LAYER_OUTPUT_DIR / f"preflight_stage_{step_number:02d}.json", report)
    if errors:
        raise RuntimeError(f"Artifact preflight failed for stage {step_number:02d}: {errors}")
    return report


def write_stage_artifact_manifest(step_number: int) -> dict[str, Any]:
    artifacts = artifacts_for_step(step_number)
    stage_path = stage_dir(step_number)
    tasks = []
    for artifact in artifacts:
        for task in artifact.get("tasks", []):
            item = dict(task)
            item["artifact_id"] = artifact["id"]
            tasks.append(item)
    manifest = {
        "step": step_number,
        "timestamp": now_iso(),
        "stage_dir": rel(stage_path),
        "artifacts": artifacts,
        "tasks": tasks,
        "file_manifest": file_manifest(stage_path) if stage_path.exists() else [],
    }
    write_json(_stage_layer_manifest_path(step_number), manifest)
    return manifest


def _result(status: str, reviewer_or_validator: str, message: str, *, severity: str = "info") -> dict[str, str]:
    return {
        "name": reviewer_or_validator,
        "status": status,
        "severity": severity,
        "message": message,
    }


def _load_stage_report(step_number: int) -> dict[str, Any] | None:
    path = stage_dir(step_number) / "validation_report.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_json", "valid": False}


def run_review_pipeline(step_number: int) -> dict[str, Any]:
    manifest = write_stage_artifact_manifest(step_number)
    stage_path = stage_dir(step_number)
    by_id = artifacts_by_id()
    stage_report = _load_stage_report(step_number)
    reviews = []

    for artifact in manifest["artifacts"]:
        artifact_id = artifact["id"]
        artifact_results = []

        if stage_path.exists():
            artifact_results.append(_result("pass", "structure_reviewer", "Stage artifact directory exists."))
        else:
            artifact_results.append(_result("fail", "structure_reviewer", "Stage artifact directory is missing.", severity="error"))

        if step_number == 15:
            required = stage_path / "migration_audit.json"
        else:
            required = stage_path / "artifact_index.json"
        if required.exists():
            artifact_results.append(_result("pass", "structure_reviewer", f"Required file exists: {required.name}."))
        else:
            artifact_results.append(_result("fail", "structure_reviewer", f"Required file missing: {required.name}.", severity="error"))

        reference_manifest = stage_path / "reference_manifest.json"
        if reference_manifest.exists():
            artifact_results.append(_result("pass", "structure_reviewer", "Required file exists: reference_manifest.json."))
        else:
            artifact_results.append(_result("fail", "structure_reviewer", "Required file missing: reference_manifest.json.", severity="error"))

        if stage_report is None:
            artifact_results.append(_result("fail", "source_trace_reviewer", "Stage validation_report.json is missing.", severity="error"))
        elif stage_report.get("status") == "success" and stage_report.get("valid") is True:
            imported = len(stage_report.get("imported_sources", []))
            upstream = len(stage_report.get("imported_upstream_artifacts", []))
            missing = stage_report.get("missing_groups", [])
            optional_missing = stage_report.get("optional_missing_groups", [])
            if imported:
                artifact_results.append(_result("pass", "source_trace_reviewer", f"{imported} source group(s) imported."))
            elif upstream:
                artifact_results.append(_result("pass", "source_trace_reviewer", f"{upstream} upstream artifact(s) imported."))
            elif missing:
                artifact_results.append(_result("pass", "source_trace_reviewer", "Missing source artifact groups are explicitly recorded.", severity="warning"))
            elif optional_missing:
                artifact_results.append(_result("pass", "source_trace_reviewer", "Optional source artifact groups are absent and explicitly recorded.", severity="warning"))
            elif step_number == 15:
                artifact_results.append(_result("pass", "source_trace_reviewer", "Audit artifact has no source import by design."))
            else:
                artifact_results.append(_result("fail", "source_trace_reviewer", "No imported sources and no missing source groups recorded.", severity="error"))
        else:
            artifact_results.append(_result("fail", "source_trace_reviewer", "Stage validation report is not successful.", severity="error"))

        task_ids = [task.get("id") for task in artifact.get("tasks", []) if task.get("id")]
        if task_ids and len(task_ids) == len(set(task_ids)):
            artifact_results.append(_result("pass", "task_reviewer", f"{len(task_ids)} task(s) declared."))
        else:
            artifact_results.append(_result("fail", "task_reviewer", "Tasks are missing or duplicated.", severity="error"))

        unknown_deps = [dep_id for dep_id in artifact.get("depends_on", []) if dep_id not in by_id]
        if unknown_deps:
            artifact_results.append(_result("fail", "dependency_reviewer", f"Unknown dependencies: {unknown_deps}", severity="error"))
        else:
            dependency_failures = _dependency_status_failures(artifact, by_id)
            if dependency_failures:
                artifact_results.append(_result("fail", "dependency_reviewer", f"Unsatisfied dependencies: {dependency_failures}", severity="error"))
            else:
                artifact_results.append(_result("pass", "dependency_reviewer", "Dependencies resolve and upstream artifact validations passed."))

        status = "fail" if any(item["status"] == "fail" for item in artifact_results) else "pass"
        reviews.append({
            "artifact_id": artifact_id,
            "status": status,
            "results": artifact_results,
        })

    report = {
        "step": step_number,
        "timestamp": now_iso(),
        "status": "failed" if any(item["status"] == "fail" for item in reviews) else "success",
        "phase": "review",
        "reviews": reviews,
    }
    write_json(_stage_reviews_path(step_number), report)
    if report["status"] != "success":
        raise RuntimeError(f"Artifact review failed for stage {step_number:02d}")
    return report


def run_artifact_validators(step_number: int) -> dict[str, Any]:
    artifacts = artifacts_for_step(step_number)
    stage_path = stage_dir(step_number)
    stage_report = _load_stage_report(step_number)
    review_path = _stage_reviews_path(step_number)
    manifest_path = _stage_layer_manifest_path(step_number)

    validation_results = []
    by_id = artifacts_by_id()
    for artifact in artifacts:
        artifact_id = artifact["id"]
        results = []

        if artifact.get("validators") and artifact.get("reviewers") and artifact.get("tasks"):
            results.append(_result("pass", "validator_first_contract", "Artifact declares validators, reviewers, and tasks."))
        else:
            results.append(_result("fail", "validator_first_contract", "Artifact contract is incomplete.", severity="error"))

        if stage_report and stage_report.get("status") == "success" and stage_report.get("valid") is True:
            if step_number == 15:
                required_exists = (stage_path / "migration_audit.json").exists()
            else:
                required_exists = (stage_path / "artifact_index.json").exists()
            reference_exists = (stage_path / "reference_manifest.json").exists()
            if required_exists and reference_exists:
                results.append(_result("pass", "stage_files_validator", "Stage files satisfy the migrated contract."))
            elif not reference_exists:
                results.append(_result("fail", "stage_files_validator", "Required reference_manifest.json is missing.", severity="error"))
            else:
                results.append(_result("fail", "stage_files_validator", "Required stage artifact index/audit file is missing.", severity="error"))
        else:
            results.append(_result("fail", "stage_files_validator", "Stage validation report is missing or failed.", severity="error"))

        if review_path.exists():
            review_report = json.loads(review_path.read_text(encoding="utf-8"))
            if review_report.get("status") == "success":
                results.append(_result("pass", "review_report_validator", "Review report passed."))
            else:
                results.append(_result("fail", "review_report_validator", "Review report failed.", severity="error"))
        else:
            results.append(_result("fail", "review_report_validator", "Review report is missing.", severity="error"))

        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("artifacts") and manifest.get("tasks"):
                results.append(_result("pass", "manifest_validator", "Artifact layer manifest declares artifacts and tasks."))
            else:
                results.append(_result("fail", "manifest_validator", "Artifact layer manifest is incomplete.", severity="error"))
        else:
            results.append(_result("fail", "manifest_validator", "Artifact layer manifest is missing.", severity="error"))

        reference_path = stage_path / "reference_manifest.json"
        if reference_path.exists():
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            files = reference.get("files", [])
            relations = reference.get("relations", [])
            inputs = reference.get("inputs", {})
            if isinstance(files, list) and isinstance(relations, list) and isinstance(inputs, dict):
                results.append(_result("pass", "reference_manifest_validator", "Reference manifest declares files, inputs, and relations."))
            else:
                results.append(_result("fail", "reference_manifest_validator", "Reference manifest is incomplete.", severity="error"))
        else:
            results.append(_result("fail", "reference_manifest_validator", "Reference manifest is missing.", severity="error"))

        missing_knowledge = _knowledge_refs_exist(artifact)
        if missing_knowledge:
            results.append(_result("fail", "knowledge_refs_validator", f"Missing knowledge references: {missing_knowledge}", severity="error"))
        else:
            results.append(_result("pass", "knowledge_refs_validator", "Knowledge references exist."))

        if "schema_contract_validator" in artifact.get("validators", []):
            schema_results = _run_schema_contract_refs(artifact)
            if schema_results:
                results.extend(schema_results)
            else:
                results.append(_result(
                    "fail",
                    "schema_contract_validator",
                    "schema_contract_validator declared but no schema_refs were provided.",
                    severity="error",
                ))

        dependency_failures = _dependency_status_failures(artifact, by_id)
        if dependency_failures:
            results.append(_result("fail", "dependency_status_validator", f"Unsatisfied dependencies: {dependency_failures}", severity="error"))
        else:
            results.append(_result("pass", "dependency_status_validator", "Upstream artifact validations passed."))

        status = "fail" if any(item["status"] == "fail" for item in results) else "pass"
        validation_results.append({
            "artifact_id": artifact_id,
            "status": status,
            "results": results,
        })

    report = {
        "step": step_number,
        "timestamp": now_iso(),
        "status": "failed" if any(item["status"] == "fail" for item in validation_results) else "success",
        "phase": "validation",
        "validations": validation_results,
    }
    write_json(_stage_validation_path(step_number), report)
    refresh_reference_manifest_file_inventory(step_number)
    if report["status"] != "success":
        raise RuntimeError(f"Artifact validation failed for stage {step_number:02d}")
    return report
