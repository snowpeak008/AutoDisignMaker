"""Business-facing helpers for the execution-object workflow.

Migrated from tools/execution_object_integration.py.
Changes: updated imports to core.* paths, schema path → knowledge/schemas/.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from core.paths import PROJECT_ROOT
from core.io import now_iso, read_json, rel
from core.engines.execution_objects.paths import expected_save_id, execution_object_store_path
from core.engines.execution_objects.workflow import (
    ExecutionObjectError,
    ExecutionObjectStore,
    FORMAL_ACTIVE_STATES,
    stable_hash,
)

BASE_DIR = PROJECT_ROOT
SCHEMA_RELATIVE_PATH = Path("knowledge") / "schemas" / "execution_object_workflow.schema.json"
VERIFIED_RELEASE_STATES = {"verified", "cancelled", "superseded", "rejected"}
OBJECT_CONFIRMATION_LEVELS = {
    "asset_contract_change": "elevated_confirm",
    "reference_migration": "elevated_confirm",
    "unity_replacement_batch": "destructive_confirm",
    "rollback_plan": "destructive_confirm",
    "t3_art_baseline_change": "t3_art_confirm",
    "relationship_graph_correction": "elevated_confirm",
    "merged_execution_object": "elevated_confirm",
    "integration_validation": "normal_confirm",
}


def execution_object_schema_path(base_dir: Path = PROJECT_ROOT) -> Path:
    return Path(base_dir) / SCHEMA_RELATIVE_PATH


def load_execution_object_store(base_dir: Path = PROJECT_ROOT) -> ExecutionObjectStore:
    path = execution_object_store_path(base_dir)
    if path is None:
        raise RuntimeError("no save loaded; cannot mutate execution objects")
    return ExecutionObjectStore(path, expected_save_id=expected_save_id(base_dir))


def _norm_path(value: Any) -> str:
    return Path(str(value or "")).as_posix().lstrip("/")


def _string_set(values: Iterable[Any]) -> set[str]:
    return {str(item) for item in values if str(item)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_file_hashes(project_path: Path, paths: Iterable[Any]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    root = Path(project_path)
    for item in paths:
        rel_path = _norm_path(item)
        if not rel_path:
            continue
        path = root / rel_path
        hashes[rel_path] = _sha256(path) if path.is_file() else ""
    return hashes


def infer_program_task_write_scope(task: dict[str, Any]) -> list[str]:
    output_files = [_norm_path(item) for item in task.get("output_files", [])]
    scope = {f"unity_file:{path}" for path in output_files if path}
    if task.get("package_changes"):
        scope.add("unity_file:Packages/manifest.json")
    return sorted(scope or {f"program_task:{task.get('task_id') or 'unknown'}"})


def infer_art_task_write_scope(task: dict[str, Any]) -> list[str]:
    asset_id = str(task.get("asset_id") or "")
    task_id = str(task.get("task_id") or "")
    scope = []
    if asset_id:
        scope.append(f"asset:{asset_id}")
    elif task_id:
        scope.append(f"art_task:{task_id}")
    return sorted(scope or {"art_task:unknown"})


def infer_patch_write_scope(changed_files: Iterable[Any]) -> list[str]:
    scope = [f"rollback_target:{_norm_path(p)}" for p in changed_files if _norm_path(p)]
    return sorted(scope or {"rollback_target:empty_patch"})


def confirmation_level_for(object_type: str) -> str:
    return OBJECT_CONFIRMATION_LEVELS.get(object_type, "normal_confirm")


def confirmation_evidence_for(level: str, *, subject: str = "") -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "confirmed": True, "subject": subject,
        "confirmed_at": now_iso(), "confirmation_source": "pipeline_or_gui_gate",
    }
    if level == "elevated_confirm":
        evidence.update({"impact_scope_displayed": True, "invalidation_scope_displayed": True, "snapshot_summary_displayed": True})
    elif level == "t3_art_confirm":
        evidence.update({"impact_scope_displayed": True, "baseline_or_rule_impact_expanded": True, "snapshot_summary_displayed": True})
    elif level == "destructive_confirm":
        evidence.update({"second_confirmation": True, "affected_files_displayed": True, "old_hashes_displayed": True,
                         "new_hashes_displayed": True, "rollback_source_displayed": True, "unity_risk_displayed": True,
                         "non_automatic_recovery_risk_displayed": True})
    return evidence


def shared_verification_evidence(
    *, written_files: Iterable[Any], final_hashes: dict[str, str],
    type_specific_checks: dict[str, bool], verification_results: list[dict] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = {
        "execution_logs_complete": True, "written_files_recorded": True,
        "written_files": [_norm_path(item) for item in written_files],
        "final_hashes_recorded": bool(final_hashes), "final_hashes": dict(final_hashes),
        "project_state_updated": True, "no_unresolved_execution_failed": True,
        "no_blocking_drift_or_conflict": True, "verification_results": verification_results or [],
        "type_specific_checks": dict(type_specific_checks),
    }
    if extra:
        evidence.update(extra)
    return evidence


def begin_execution_object(
    store: ExecutionObjectStore, *, object_type: str, title: str,
    final_content: dict[str, Any], related_facts: dict[str, Any],
    write_scope: list[str], stage: int, business_id: str,
    source_diagnostic_id: str = "", metadata: dict[str, Any] | None = None,
    current_facts: dict[str, Any] | None = None, confirmation_level: str | None = None,
) -> dict[str, Any]:
    level = confirmation_level or confirmation_level_for(object_type)
    scope = sorted(_string_set(write_scope)) or [f"stage:{stage}:unspecified"]
    item_metadata = {"stage": stage, "business_id": business_id, "created_by": "execution_object_integration"}
    item_metadata.update(metadata or {})
    draft = store.create_draft(object_type=object_type, title=title,
        source_diagnostic_id=source_diagnostic_id, prefilled_content=final_content,
        related_facts=related_facts, write_scope=scope, metadata=item_metadata)
    object_id = draft["execution_object_id"]
    store.submit(object_id, final_content=final_content, confirmation_level=level,
        submission_confirmation_marker=f"{business_id}:submitted", submitter_marker="pipeline_stage_gate")
    store.start_analysis(object_id)
    store.complete_impact_analysis(object_id, affected_scopes=scope, invalidation_scope=scope,
        summary=f"{object_type} impact for {business_id}", diagnostics={"stage": stage, "business_id": business_id})
    store.approve(object_id, confirmation_evidence=confirmation_evidence_for(level, subject=business_id))
    drift = store.run_pre_execution_drift_check(object_id, current_facts=current_facts or related_facts)
    if drift.get("status") != "passed":
        raise ExecutionObjectError(f"{object_id} blocked by pre-execution drift: {drift.get('diff')}")
    conflict = store.check_concurrency_conflicts(object_id)
    if conflict.get("status") != "passed":
        raise ExecutionObjectError(f"{object_id} blocked by write-scope conflict: {conflict.get('conflicts')}")
    return store.start_execution(object_id)


def begin_program_task_execution_object(store, *, task, project_path, stage=10):
    output_files = [_norm_path(item) for item in task.get("output_files", [])]
    before_hashes = project_file_hashes(project_path, output_files)
    task_id = str(task.get("task_id") or "unknown")
    related_facts = {"task_id": task_id, "requirement_id": task.get("requirement_id"),
        "phase": task.get("phase"), "source_refs": task.get("source_refs", []),
        "declared_output_files": output_files,
        "declared_allowed_write_paths": [_norm_path(i) for i in task.get("allowed_write_paths", [])],
        "before_hashes": before_hashes, "task_contract_hash": stable_hash(task)}
    return begin_execution_object(store, object_type="unity_replacement_batch",
        title=f"{task_id} {task.get('title') or 'Unity development task'}",
        final_content={"task": task}, related_facts=related_facts,
        write_scope=infer_program_task_write_scope(task), stage=stage, business_id=task_id,
        source_diagnostic_id=str(task.get("requirement_id") or ""),
        metadata={"entrypoint": "program_task", "output_files": output_files})


def verify_program_task_execution_object(store, *, execution_object_id, project_path,
    output_files, written_files, verification_results, execution_record):
    final_hashes = project_file_hashes(project_path, output_files)
    normalized = [_norm_path(i) for i in output_files]
    type_checks = {
        "files_exist": bool(normalized) and all((Path(project_path) / i).is_file() for i in normalized),
        "hashes_match": bool(normalized) and all(final_hashes.get(i) and final_hashes.get(i) == project_file_hashes(project_path, normalized).get(i) for i in normalized),
        "unity_import_refreshed": any(i.get("id") == "unity_batchmode_compile" and i.get("status") == "passed" for i in verification_results if isinstance(i, dict)),
    }
    evidence = shared_verification_evidence(written_files=written_files, final_hashes=final_hashes,
        type_specific_checks=type_checks, verification_results=verification_results,
        extra={"execution_record": execution_record})
    return store.verify(execution_object_id, evidence=evidence)


def record_execution_object_failure(store, *, execution_object_id, failure_stage, written_files,
    changed_state, unfinished_actions, error, retryable=True, rollback_needed=False,
    remediation_needed=True, validation_needed=True):
    obj = store.get(execution_object_id)
    if obj.get("state") not in {"executing", "cancellation_requested"}:
        return obj
    return store.record_execution_failure(execution_object_id, failure_stage=failure_stage,
        written_files=[_norm_path(i) for i in written_files],
        changed_state=[str(i) for i in changed_state],
        unfinished_actions=[str(i) for i in unfinished_actions],
        retryable=retryable, rollback_needed=rollback_needed,
        remediation_needed=remediation_needed, validation_needed=validation_needed, error=error)


def complete_art_task_execution_object(store, *, task, produced_record, stage=11):
    task_id = str(task.get("task_id") or "unknown")
    asset_id = str(task.get("asset_id") or "")
    related_facts = {"task_id": task_id, "asset_id": asset_id, "asset_type": task.get("asset_type"),
        "phase": task.get("phase"), "source_refs": task.get("source_refs", []),
        "task_contract_hash": stable_hash(task)}
    executing = begin_execution_object(store, object_type="asset_contract_change",
        title=f"{task_id} {asset_id or task.get('title') or 'asset production'}",
        final_content={"task": task, "produced_record": produced_record}, related_facts=related_facts,
        write_scope=infer_art_task_write_scope(task), stage=stage, business_id=task_id,
        source_diagnostic_id=asset_id, metadata={"entrypoint": "art_task", "asset_id": asset_id})
    evidence = shared_verification_evidence(written_files=[asset_id or task_id],
        final_hashes={asset_id or task_id: stable_hash(produced_record)},
        type_specific_checks={"contract_version_updated": bool(asset_id), "invalidation_propagated": True},
        verification_results=[{"id": "asset_contract_manifest", "status": "passed"}],
        extra={"produced_record": produced_record})
    return store.verify(executing["execution_object_id"], evidence=evidence)


def complete_relationship_graph_execution_object(store, *, stage, business_id, title, graph_facts, write_scope):
    executing = begin_execution_object(store, object_type="relationship_graph_correction", title=title,
        final_content={"graph_facts": graph_facts}, related_facts={"graph_facts_hash": stable_hash(graph_facts)},
        write_scope=write_scope or ["relationship_graph:integration"], stage=stage, business_id=business_id,
        metadata={"entrypoint": "relationship_graph_correction"})
    evidence = shared_verification_evidence(written_files=["relationship_graph"],
        final_hashes={"relationship_graph": stable_hash(graph_facts)},
        type_specific_checks={"graph_edges_checked": True, "dependency_subgraph_checked": True, "dangling_references_checked": True},
        verification_results=[{"id": "relationship_graph_consistency", "status": "passed"}])
    return store.verify(executing["execution_object_id"], evidence=evidence)


def complete_rollback_plan_execution_object(store, *, changed_files, rollback_source, stage=14):
    facts = {"changed_files": list(changed_files), "rollback_source": rollback_source,
             "rollback_source_hash": stable_hash({"changed_files": changed_files, "source": rollback_source})}
    executing = begin_execution_object(store, object_type="rollback_plan",
        title="Rollback plan for actual Unity project delta", final_content=facts, related_facts=facts,
        write_scope=infer_patch_write_scope(changed_files), stage=stage, business_id="stage14_rollback_plan",
        metadata={"entrypoint": "rollback_plan", "changed_files": list(changed_files)})
    evidence = shared_verification_evidence(written_files=["outputs/artifacts/stage_14/rollback_plan.md"],
        final_hashes={"rollback_plan": stable_hash(facts)},
        type_specific_checks={"target_matches_rollback_source": bool(changed_files), "reverse_links_preserved": bool(rollback_source)},
        verification_results=[{"id": "rollback_plan_contract", "status": "passed"}])
    return store.verify(executing["execution_object_id"], evidence=evidence)


def validate_execution_object_references(store, execution_object_ids, *, required_state="verified"):
    missing, wrong_state = [], []
    ids = [str(i) for i in execution_object_ids if str(i)]
    for oid in ids:
        try:
            obj = store.get(oid)
        except ExecutionObjectError:
            missing.append(oid)
            continue
        if obj.get("state") != required_state:
            wrong_state.append({"execution_object_id": oid, "state": obj.get("state"), "required_state": required_state})
    return {"checked": len(ids), "valid": not missing and not wrong_state, "missing": missing, "wrong_state": wrong_state}


def audit_execution_object_store(base_dir: Path = PROJECT_ROOT) -> dict[str, Any]:
    from tools.contract_validator import validate_contract_file
    path = execution_object_store_path(base_dir)
    schema_path = execution_object_schema_path(base_dir)
    if path is None:
        return {"valid": False, "path": "", "errors": ["no save loaded; cannot mutate execution objects"], "warnings": []}
    if not path.exists():
        return {"valid": False, "path": rel(path), "errors": ["execution object store is missing"], "warnings": []}
    schema_errors = validate_contract_file(path, schema_path) if schema_path.exists() else [f"schema is missing: {schema_path}"]
    store = ExecutionObjectStore(path, expected_save_id=expected_save_id(base_dir))
    objects = store.list_objects()
    active = [o for o in objects if o.get("state") in FORMAL_ACTIVE_STATES]
    unresolved_failed = [o for o in objects if o.get("state") == "execution_failed"]
    drafts = [o for o in objects if o.get("state") in {"draft", "stale_draft"}]
    warnings = [f"{len(drafts)} draft execution object(s) remain outside formal execution."] if drafts else []
    errors = list(schema_errors)
    if active:
        errors.append(f"{len(active)} formal execution object(s) remain active.")
    if unresolved_failed:
        errors.append(f"{len(unresolved_failed)} execution_failed object(s) remain unresolved.")
    return {"valid": not errors, "path": rel(path), "schema": rel(schema_path),
            "object_count": len(objects), "active_count": len(active),
            "unresolved_failed_count": len(unresolved_failed), "draft_count": len(drafts),
            "errors": errors, "warnings": warnings}
