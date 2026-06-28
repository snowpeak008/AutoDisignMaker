#!/usr/bin/env python3
"""Project-save scoped execution object workflow.

This module implements the confirmed execution-object workflow gates without
introducing accounts, roles, or permissions. All confirmation records are
project-save scoped facts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


STATES = {
    "draft",
    "stale_draft",
    "submitted",
    "analyzing",
    "awaiting_confirmation",
    "approved",
    "conflict_blocked",
    "stale_before_execution",
    "executing",
    "cancellation_requested",
    "execution_failed",
    "verified",
    "rejected",
    "cancelled",
    "superseded",
}

FORMAL_ACTIVE_STATES = {
    "submitted",
    "analyzing",
    "awaiting_confirmation",
    "approved",
    "conflict_blocked",
    "stale_before_execution",
    "executing",
    "cancellation_requested",
    "execution_failed",
}

DIRECTLY_CANCELLABLE_STATES = {
    "draft",
    "stale_draft",
    "submitted",
    "analyzing",
    "awaiting_confirmation",
    "conflict_blocked",
    "stale_before_execution",
}

CONFIRMATION_LEVELS = {
    "normal_confirm",
    "elevated_confirm",
    "t3_art_confirm",
    "destructive_confirm",
}

OBJECT_REQUIRED_CONFIRMATION_LEVELS = {
    "asset_contract_change": "elevated_confirm",
    "reference_migration": "elevated_confirm",
    "unity_replacement_batch": "destructive_confirm",
    "rollback_plan": "destructive_confirm",
    "t3_art_baseline_change": "t3_art_confirm",
    "relationship_graph_correction": "elevated_confirm",
    "merged_execution_object": "elevated_confirm",
    "integration_validation": "normal_confirm",
}

CONFLICT_RELEASE_STATES = {"verified", "cancelled", "superseded"}

AUDIT_SPINE_KEYS = {
    "submission_snapshot",
    "final_submitted_content",
    "confirmation_level",
    "impact_analysis",
    "drift_checks",
    "conflict_checks",
    "approval_records",
    "cancellation_records",
    "failure_records",
    "supersession_relationships",
    "partial_write_facts",
    "verified_file_hashes",
    "rollback_sources",
    "reverse_execution_links",
}

CLEANABLE_DERIVED_MATERIALS = {
    "stale_draft_diagnostic_cache",
    "regenerable_preview",
    "temporary_diff_view",
    "duplicate_gui_display_cache",
    "large_intermediate_log",
}

TYPE_SPECIFIC_VERIFICATION_REQUIREMENTS = {
    "asset_contract_change": {
        "contract_version_updated",
        "invalidation_propagated",
    },
    "reference_migration": {
        "old_references_handled",
        "asset_id_mapping_stable",
        "runtime_paths_consistent",
    },
    "unity_replacement_batch": {
        "files_exist",
        "hashes_match",
        "unity_import_refreshed",
    },
    "rollback_plan": {
        "target_matches_rollback_source",
        "reverse_links_preserved",
    },
    "t3_art_baseline_change": {
        "baseline_relationships_updated",
        "downstream_impacts_marked",
    },
    "relationship_graph_correction": {
        "graph_edges_checked",
        "dependency_subgraph_checked",
        "dangling_references_checked",
    },
}


class ExecutionObjectError(RuntimeError):
    """Raised when an execution-object transition violates workflow gates."""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "Docs" / "governance" / "schemas" / "execution_object_workflow.schema.json"


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def deep_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    return [value]


def _as_string_set(value: Any) -> set[str]:
    return {str(item) for item in _as_list(value) if str(item)}


def _required_confirmation_level(object_type: str) -> str:
    return OBJECT_REQUIRED_CONFIRMATION_LEVELS.get(object_type, "normal_confirm")


def _require_state(obj: dict[str, Any], allowed: set[str], action: str) -> None:
    state = obj.get("state")
    if state not in allowed:
        raise ExecutionObjectError(
            f"{action} requires state {sorted(allowed)}, got {state!r} for {obj.get('execution_object_id')}"
        )


def drift_diff(snapshot_facts: dict[str, Any], current_facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return relevant fact differences between a snapshot and current facts."""
    diff: dict[str, dict[str, Any]] = {}
    keys = set(snapshot_facts) | set(current_facts)
    for key in sorted(keys):
        old = snapshot_facts.get(key)
        new = current_facts.get(key)
        if old != new:
            diff[key] = {"snapshot": deep_copy(old), "current": deep_copy(new)}
    return diff


class ExecutionObjectStore:
    """JSON-backed execution-object workflow store."""

    def __init__(self, path: str | Path, *, expected_save_id: str | None = None):
        raw_path = Path(path)
        if raw_path.suffix.lower() == ".json":
            self.path = raw_path
        else:
            self.path = raw_path / "execution_objects.json"
        self.expected_save_id = expected_save_id
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": 1,
                "generated_at": now_iso(),
                "updated_at": now_iso(),
                "objects": [],
                "audit_cleanup_evidence": [],
            }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ExecutionObjectError(f"Invalid execution object store JSON: {self.path}") from exc
        if not isinstance(data, dict):
            raise ExecutionObjectError("Execution object store must be a JSON object.")
        data.setdefault("schema_version", 1)
        data.setdefault("generated_at", now_iso())
        data.setdefault("updated_at", now_iso())
        data.setdefault("objects", [])
        data.setdefault("audit_cleanup_evidence", [])
        return data

    def save(self) -> Path:
        existing_save_id = self.data.get("save_id")
        if self.expected_save_id:
            if existing_save_id and existing_save_id != self.expected_save_id:
                raise ExecutionObjectError(
                    f"Execution object store save_id {existing_save_id!r} does not match expected save_id {self.expected_save_id!r}."
                )
            self.data["save_id"] = self.expected_save_id
        self.data["updated_at"] = now_iso()
        schema_path = _default_schema_path()
        if schema_path.exists():
            try:
                from tools.contract_validator import validate_contract_file
            except ImportError as exc:
                raise ExecutionObjectError(f"Unable to import contract validator: {exc}") from exc
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(self.data, handle, ensure_ascii=False, indent=2)
            try:
                errors = validate_contract_file(temp_path, schema_path)
            finally:
                temp_path.unlink(missing_ok=True)
            if errors:
                raise ExecutionObjectError(f"Execution object store failed schema validation: {errors}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path

    def _next_id(self, prefix: str = "EO") -> str:
        used = {
            str(obj.get("execution_object_id", ""))
            for obj in self.data.get("objects", [])
            if isinstance(obj, dict)
        }
        index = len(used) + 1
        while True:
            candidate = f"{prefix}-{index:06d}"
            if candidate not in used:
                return candidate
            index += 1

    def get(self, execution_object_id: str) -> dict[str, Any]:
        for obj in self.data.get("objects", []):
            if isinstance(obj, dict) and obj.get("execution_object_id") == execution_object_id:
                return obj
        raise ExecutionObjectError(f"Unknown execution object: {execution_object_id}")

    def list_objects(self, *, states: set[str] | None = None) -> list[dict[str, Any]]:
        result = [obj for obj in self.data.get("objects", []) if isinstance(obj, dict)]
        if states is not None:
            result = [obj for obj in result if obj.get("state") in states]
        return result

    def _append_history(self, obj: dict[str, Any], new_state: str, reason: str, evidence: dict[str, Any] | None = None) -> None:
        if new_state not in STATES:
            raise ExecutionObjectError(f"Unknown execution object state: {new_state}")
        old_state = obj.get("state")
        obj["state"] = new_state
        obj["updated_at"] = now_iso()
        obj.setdefault("state_history", []).append({
            "at": obj["updated_at"],
            "from": old_state,
            "to": new_state,
            "reason": reason,
            "evidence": deep_copy(evidence or {}),
        })

    def create_draft(
        self,
        *,
        object_type: str,
        title: str,
        source_diagnostic_id: str = "",
        prefilled_content: dict[str, Any] | None = None,
        user_content: dict[str, Any] | None = None,
        related_facts: dict[str, Any] | None = None,
        write_scope: list[str] | None = None,
        source_execution_object_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        obj = {
            "execution_object_id": self._next_id(),
            "object_type": object_type,
            "title": title,
            "state": "draft",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "source_diagnostic_id": source_diagnostic_id,
            "source_execution_object_id": source_execution_object_id,
            "prefilled_content": deep_copy(prefilled_content or {}),
            "user_content": deep_copy(user_content or {}),
            "related_facts": deep_copy(related_facts or {}),
            "write_scope": sorted(_as_string_set(write_scope)),
            "submission_snapshot": None,
            "impact_analysis": None,
            "confirmation_records": [],
            "drift_checks": [],
            "conflict_checks": [],
            "execution_records": [],
            "failure_records": [],
            "verification_records": [],
            "audit_cleanup_evidence": [],
            "state_history": [],
            "metadata": deep_copy(metadata or {}),
        }
        obj["state_history"].append({
            "at": obj["created_at"],
            "from": None,
            "to": "draft",
            "reason": "created",
            "evidence": {},
        })
        self.data.setdefault("objects", []).append(obj)
        self.save()
        return deep_copy(obj)

    def mark_draft_stale(self, execution_object_id: str, *, reason: str, changed_facts: dict[str, Any]) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"draft"}, "mark_draft_stale")
        obj["stale_reason"] = reason
        obj["stale_changed_facts"] = deep_copy(changed_facts)
        self._append_history(obj, "stale_draft", "draft dependencies changed", {"reason": reason})
        self.save()
        return deep_copy(obj)

    def refresh_stale_draft(
        self,
        execution_object_id: str,
        *,
        refreshed_prefill: dict[str, Any],
        diff: dict[str, Any],
        migrate_user_content: bool = False,
    ) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"stale_draft"}, "refresh_stale_draft")
        new_user_content = deep_copy(obj.get("user_content", {})) if migrate_user_content else {}
        refreshed = self.create_draft(
            object_type=obj.get("object_type", ""),
            title=obj.get("title", ""),
            source_diagnostic_id=obj.get("source_diagnostic_id", ""),
            prefilled_content=refreshed_prefill,
            user_content=new_user_content,
            related_facts=obj.get("related_facts", {}),
            write_scope=obj.get("write_scope", []),
            metadata={
                "refreshed_from_draft_id": execution_object_id,
                "refresh_diff": deep_copy(diff),
                "migrated_user_content": bool(migrate_user_content),
            },
        )
        obj["superseded_draft_id"] = refreshed["execution_object_id"]
        obj.setdefault("refresh_records", []).append({
            "at": now_iso(),
            "refreshed_draft_id": refreshed["execution_object_id"],
            "diff_hash": stable_hash(diff),
            "migrated_user_content": bool(migrate_user_content),
        })
        self.save()
        return refreshed

    def submit(
        self,
        execution_object_id: str,
        *,
        final_content: dict[str, Any],
        confirmation_level: str,
        submission_confirmation_marker: str,
        submitter_marker: str = "project_save_operator",
    ) -> dict[str, Any]:
        if confirmation_level not in CONFIRMATION_LEVELS:
            raise ExecutionObjectError(f"Unknown confirmation level: {confirmation_level}")
        obj = self.get(execution_object_id)
        _require_state(obj, {"draft"}, "submit")
        required_level = _required_confirmation_level(str(obj.get("object_type") or ""))
        if confirmation_level != required_level:
            raise ExecutionObjectError(
                f"{obj.get('object_type')} requires confirmation level {required_level}, got {confirmation_level}."
            )
        snapshot = {
            "snapshot_id": f"SS-{execution_object_id}",
            "execution_object_id": execution_object_id,
            "draft_id": execution_object_id,
            "source_diagnostic_id": obj.get("source_diagnostic_id", ""),
            "submitted_at": now_iso(),
            "submitter_marker": submitter_marker,
            "submission_confirmation_marker": submission_confirmation_marker,
            "confirmation_level": confirmation_level,
            "related_facts": deep_copy(obj.get("related_facts", {})),
            "write_scope": deep_copy(obj.get("write_scope", [])),
            "prefilled_content_hash": stable_hash(obj.get("prefilled_content", {})),
            "final_content": deep_copy(final_content),
            "final_content_hash": stable_hash(final_content),
            "prefill_to_final_diff_hash": stable_hash({
                "prefilled": obj.get("prefilled_content", {}),
                "final": final_content,
            }),
            "stale_draft_refresh_source": obj.get("metadata", {}).get("refreshed_from_draft_id", ""),
        }
        obj["submission_snapshot"] = snapshot
        obj["final_submitted_content"] = deep_copy(final_content)
        obj["confirmation_level"] = confirmation_level
        self._append_history(obj, "submitted", "submitted with immutable snapshot", {"snapshot_id": snapshot["snapshot_id"]})
        self.save()
        return deep_copy(obj)

    def start_analysis(self, execution_object_id: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"submitted"}, "start_analysis")
        if not obj.get("submission_snapshot"):
            raise ExecutionObjectError("Submitted execution object requires a submission snapshot.")
        self._append_history(obj, "analyzing", "impact analysis started")
        self.save()
        return deep_copy(obj)

    def complete_impact_analysis(
        self,
        execution_object_id: str,
        *,
        affected_scopes: list[str],
        summary: str,
        invalidation_scope: list[str] | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"analyzing"}, "complete_impact_analysis")
        analysis = {
            "analysis_id": f"IA-{execution_object_id}",
            "based_on_snapshot_id": obj["submission_snapshot"]["snapshot_id"],
            "created_at": now_iso(),
            "affected_scopes": sorted(_as_string_set(affected_scopes)),
            "invalidation_scope": sorted(_as_string_set(invalidation_scope)),
            "summary": summary,
            "diagnostics": deep_copy(diagnostics or {}),
            "is_empty": not bool(affected_scopes),
        }
        obj["impact_analysis"] = analysis
        if affected_scopes:
            obj["write_scope"] = sorted(_as_string_set(obj.get("write_scope", [])) | _as_string_set(affected_scopes))
        self._append_history(obj, "awaiting_confirmation", "impact analysis completed", {
            "analysis_id": analysis["analysis_id"],
            "is_empty": analysis["is_empty"],
        })
        self.save()
        return deep_copy(obj)

    def reject_empty_impact(self, execution_object_id: str, *, reason: str = "no_effect") -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"awaiting_confirmation"}, "reject_empty_impact")
        analysis = obj.get("impact_analysis") or {}
        if not analysis.get("is_empty"):
            raise ExecutionObjectError("reject_empty_impact is allowed only for empty impact analysis.")
        obj["rejection"] = {"at": now_iso(), "reason": reason}
        self._append_history(obj, "rejected", "empty impact rejected", {"reason": reason})
        self.save()
        return deep_copy(obj)

    def approve(self, execution_object_id: str, *, confirmation_evidence: dict[str, Any]) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"awaiting_confirmation"}, "approve")
        level = obj.get("confirmation_level")
        self.validate_confirmation_gate(level, confirmation_evidence)
        record = {
            "at": now_iso(),
            "confirmation_level": level,
            "evidence": deep_copy(confirmation_evidence),
            "impact_analysis_id": (obj.get("impact_analysis") or {}).get("analysis_id", ""),
        }
        obj.setdefault("confirmation_records", []).append(record)
        self._append_history(obj, "approved", "approved after confirmation gate", {"confirmation_level": level})
        self.save()
        return deep_copy(obj)

    def validate_confirmation_gate(self, level: str, evidence: dict[str, Any]) -> None:
        if level not in CONFIRMATION_LEVELS:
            raise ExecutionObjectError(f"Unknown confirmation level: {level}")
        if not evidence.get("confirmed"):
            raise ExecutionObjectError("Confirmation evidence must include confirmed=true.")
        if level == "normal_confirm":
            return
        if level == "elevated_confirm":
            required = {"impact_scope_displayed", "invalidation_scope_displayed", "snapshot_summary_displayed"}
        elif level == "t3_art_confirm":
            required = {"impact_scope_displayed", "baseline_or_rule_impact_expanded", "snapshot_summary_displayed"}
        else:
            required = {
                "second_confirmation",
                "affected_files_displayed",
                "old_hashes_displayed",
                "new_hashes_displayed",
                "rollback_source_displayed",
                "unity_risk_displayed",
                "non_automatic_recovery_risk_displayed",
            }
        missing = sorted(key for key in required if not evidence.get(key))
        if missing:
            raise ExecutionObjectError(f"{level} missing confirmation gate evidence: {missing}")

    def run_pre_execution_drift_check(
        self,
        execution_object_id: str,
        *,
        current_facts: dict[str, Any],
    ) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"approved"}, "run_pre_execution_drift_check")
        snapshot = obj.get("submission_snapshot") or {}
        diff = drift_diff(snapshot.get("related_facts", {}), current_facts)
        check = {
            "drift_check_id": f"DC-{execution_object_id}-{len(obj.get('drift_checks', [])) + 1:03d}",
            "at": now_iso(),
            "current_facts_hash": stable_hash(current_facts),
            "diff": diff,
            "status": "stale_before_execution" if diff else "passed",
        }
        obj.setdefault("drift_checks", []).append(check)
        if diff:
            obj["stale_before_execution"] = {
                "drift_check_id": check["drift_check_id"],
                "diff": diff,
            }
            self._append_history(obj, "stale_before_execution", "relevant pre-execution drift", {
                "drift_check_id": check["drift_check_id"],
            })
        self.save()
        return deep_copy(check)

    def refresh_stale_before_execution(
        self,
        execution_object_id: str,
        *,
        current_facts: dict[str, Any],
        refreshed_content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"stale_before_execution"}, "refresh_stale_before_execution")
        stale = obj.get("stale_before_execution") or {}
        refreshed = self.create_draft(
            object_type=obj.get("object_type", ""),
            title=obj.get("title", ""),
            source_diagnostic_id=obj.get("source_diagnostic_id", ""),
            prefilled_content=refreshed_content or obj.get("final_submitted_content", {}),
            user_content={},
            related_facts=current_facts,
            write_scope=obj.get("write_scope", []),
            source_execution_object_id=execution_object_id,
            metadata={
                "refreshed_from_execution_object_id": execution_object_id,
                "drift_check_id": stale.get("drift_check_id", ""),
                "drift_diff": deep_copy(stale.get("diff", {})),
            },
        )
        obj["pending_refreshed_object_id"] = refreshed["execution_object_id"]
        self.save()
        return refreshed

    def check_concurrency_conflicts(self, execution_object_id: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        if obj.get("state") not in {"approved", "conflict_blocked", "awaiting_confirmation"}:
            raise ExecutionObjectError("Concurrency checks require an approved, awaiting, or conflict-blocked object.")
        scope = _as_string_set(obj.get("write_scope", []))
        conflicts: list[dict[str, Any]] = []
        for other in self.list_objects(states=FORMAL_ACTIVE_STATES):
            if other.get("execution_object_id") == execution_object_id:
                continue
            other_scope = _as_string_set(other.get("write_scope", []))
            overlap = sorted(scope & other_scope)
            if overlap:
                conflicts.append({
                    "execution_object_id": other.get("execution_object_id"),
                    "state": other.get("state"),
                    "overlap": overlap,
                })
        check = {
            "conflict_check_id": f"CC-{execution_object_id}-{len(obj.get('conflict_checks', [])) + 1:03d}",
            "at": now_iso(),
            "status": "blocked" if conflicts else "passed",
            "conflicts": conflicts,
        }
        obj.setdefault("conflict_checks", []).append(check)
        if conflicts:
            obj["conflict_block"] = {
                "conflict_check_id": check["conflict_check_id"],
                "conflicts": conflicts,
                "waiting": False,
            }
            self._append_history(obj, "conflict_blocked", "overlapping high-risk write scope", {
                "conflict_check_id": check["conflict_check_id"],
            })
        self.save()
        return deep_copy(check)

    def wait_for_conflict(self, execution_object_id: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"conflict_blocked"}, "wait_for_conflict")
        block = obj.get("conflict_block")
        if not isinstance(block, dict) or not block.get("conflicts"):
            raise ExecutionObjectError("conflict_blocked object has no conflict block details.")
        block["waiting"] = True
        block["waiting_since"] = now_iso()
        self.save()
        return deep_copy(obj)

    def recheck_waiting_conflict(
        self,
        execution_object_id: str,
        *,
        current_facts: dict[str, Any],
    ) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"conflict_blocked"}, "recheck_waiting_conflict")
        block = obj.get("conflict_block") or {}
        if not block.get("waiting"):
            raise ExecutionObjectError("Conflict recheck requires a waiting conflict block.")
        blockers: list[dict[str, Any]] = []
        for conflict in block.get("conflicts", []):
            other = self.get(conflict["execution_object_id"])
            if other.get("state") == "execution_failed":
                blockers.append({
                    "execution_object_id": other["execution_object_id"],
                    "state": other["state"],
                    "reason": "execution_failed_does_not_release_conflict",
                })
            elif other.get("state") not in CONFLICT_RELEASE_STATES:
                blockers.append({
                    "execution_object_id": other["execution_object_id"],
                    "state": other["state"],
                    "reason": "conflicting_object_not_released",
                })
        recheck = {
            "at": now_iso(),
            "blockers": blockers,
        }
        if blockers:
            block.setdefault("rechecks", []).append(recheck)
            self.save()
            return {"status": "blocked", **deep_copy(recheck)}

        drift = drift_diff((obj.get("submission_snapshot") or {}).get("related_facts", {}), current_facts)
        recheck["drift"] = drift
        if drift:
            obj["stale_before_execution"] = {
                "drift_check_id": f"DC-{execution_object_id}-conflict-recheck",
                "diff": drift,
            }
            self._append_history(obj, "stale_before_execution", "drift found after conflict wait recheck")
            status = "stale_before_execution"
        else:
            obj["conflict_block"] = None
            obj["reconfirmation_required"] = True
            self._append_history(obj, "awaiting_confirmation", "conflict wait recheck passed")
            status = "awaiting_confirmation"
        block.setdefault("rechecks", []).append(recheck)
        self.save()
        return {"status": status, **deep_copy(recheck)}

    def create_merge_draft(self, source_execution_object_ids: list[str], *, title: str) -> dict[str, Any]:
        if len(source_execution_object_ids) < 2:
            raise ExecutionObjectError("A merge draft requires at least two source execution objects.")
        sources = [self.get(source_id) for source_id in source_execution_object_ids]
        for source in sources:
            _require_state(source, {"conflict_blocked"}, "create_merge_draft")
        merged_scope: set[str] = set()
        source_snapshots = []
        for source in sources:
            merged_scope.update(_as_string_set(source.get("write_scope", [])))
            source_snapshots.append({
                "execution_object_id": source["execution_object_id"],
                "submission_snapshot": deep_copy(source.get("submission_snapshot")),
                "impact_analysis": deep_copy(source.get("impact_analysis")),
                "user_content": deep_copy(source.get("user_content", {})),
                "conflict_block": deep_copy(source.get("conflict_block", {})),
            })
        draft = self.create_draft(
            object_type="merged_execution_object",
            title=title,
            source_diagnostic_id="",
            prefilled_content={"source_snapshots": source_snapshots},
            related_facts={"merge_sources": source_execution_object_ids},
            write_scope=sorted(merged_scope),
            metadata={"source_execution_object_ids": list(source_execution_object_ids)},
        )
        for source in sources:
            source["pending_merge_draft_id"] = draft["execution_object_id"]
        self.save()
        return draft

    def supersede_merge_sources(self, merged_execution_object_id: str) -> dict[str, Any]:
        merged = self.get(merged_execution_object_id)
        if merged.get("object_type") != "merged_execution_object":
            raise ExecutionObjectError("Only merged execution objects can supersede merge sources.")
        _require_state(merged, {"approved", "verified"}, "supersede_merge_sources")
        source_ids = merged.get("metadata", {}).get("source_execution_object_ids", [])
        for source_id in source_ids:
            source = self.get(source_id)
            _require_state(source, {"conflict_blocked"}, "supersede_merge_sources")
            source["superseded_by_merged_object"] = merged_execution_object_id
            self._append_history(source, "superseded", "merged object confirmed", {
                "merged_execution_object_id": merged_execution_object_id,
            })
        self.save()
        return deep_copy(merged)

    def cancel(self, execution_object_id: str, *, reason: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, DIRECTLY_CANCELLABLE_STATES, "cancel")
        obj.setdefault("cancellation_records", []).append({
            "at": now_iso(),
            "reason": reason,
            "preserved_submission_snapshot": bool(obj.get("submission_snapshot")),
            "preserved_impact_analysis": bool(obj.get("impact_analysis")),
        })
        self._append_history(obj, "cancelled", "cancelled before execution", {"reason": reason})
        self.save()
        return deep_copy(obj)

    def force_cancel(self, execution_object_id: str, *, reason: str) -> dict[str, Any]:
        """Cancel an execution object in any non-terminal state.

        Used when a new version supersedes all previous objects regardless of their
        current workflow state (e.g., design_project saves always supersede old ones).
        Terminal states (verified, cancelled, superseded, rejected) are left unchanged.
        """
        terminal_states = {"verified", "cancelled", "superseded", "rejected"}
        obj = self.get(execution_object_id)
        if obj.get("state") in terminal_states:
            return deep_copy(obj)
        obj.setdefault("cancellation_records", []).append({
            "at": now_iso(),
            "reason": reason,
            "forced": True,
            "prior_state": obj.get("state"),
            "preserved_submission_snapshot": bool(obj.get("submission_snapshot")),
            "preserved_impact_analysis": bool(obj.get("impact_analysis")),
        })
        self._append_history(obj, "cancelled", f"force-cancelled: {reason}", {"forced": True})
        self.save()
        return deep_copy(obj)

    def start_execution(self, execution_object_id: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"approved"}, "start_execution")
        last_drift = (obj.get("drift_checks") or [{}])[-1]
        last_conflict = (obj.get("conflict_checks") or [{}])[-1]
        if last_drift.get("status") != "passed":
            raise ExecutionObjectError("Execution requires a passed pre-execution drift check.")
        if last_conflict.get("status") != "passed":
            raise ExecutionObjectError("Execution requires a passed concurrency conflict check.")
        record = {
            "execution_record_id": f"ER-{execution_object_id}-{len(obj.get('execution_records', [])) + 1:03d}",
            "started_at": now_iso(),
            "written_files": [],
            "changed_state": [],
        }
        obj.setdefault("execution_records", []).append(record)
        self._append_history(obj, "executing", "execution started", {
            "execution_record_id": record["execution_record_id"],
        })
        self.save()
        return deep_copy(obj)

    def request_cancellation_during_execution(self, execution_object_id: str, *, reason: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"executing"}, "request_cancellation_during_execution")
        obj.setdefault("cancellation_records", []).append({
            "at": now_iso(),
            "reason": reason,
            "type": "cancellation_requested",
        })
        self._append_history(obj, "cancellation_requested", "cancellation requested during execution", {"reason": reason})
        self.save()
        return deep_copy(obj)

    def record_execution_failure(
        self,
        execution_object_id: str,
        *,
        failure_stage: str,
        written_files: list[str],
        changed_state: list[str],
        unfinished_actions: list[str],
        retryable: bool,
        rollback_needed: bool,
        remediation_needed: bool,
        validation_needed: bool,
        error: str,
    ) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"executing", "cancellation_requested"}, "record_execution_failure")
        failure = {
            "failure_record_id": f"EF-{execution_object_id}-{len(obj.get('failure_records', [])) + 1:03d}",
            "at": now_iso(),
            "failure_stage": failure_stage,
            "written_files": list(written_files),
            "changed_state": list(changed_state),
            "unfinished_actions": list(unfinished_actions),
            "retryable": bool(retryable),
            "rollback_needed": bool(rollback_needed),
            "remediation_needed": bool(remediation_needed),
            "validation_needed": bool(validation_needed),
            "error": error,
        }
        obj.setdefault("failure_records", []).append(failure)
        obj["latest_failure_record_id"] = failure["failure_record_id"]
        self._append_history(obj, "execution_failed", "execution failed with partial facts", {
            "failure_record_id": failure["failure_record_id"],
        })
        self.save()
        return deep_copy(obj)

    def confirm_retry_from_safe_point(
        self,
        execution_object_id: str,
        *,
        evidence: dict[str, Any],
        current_facts: dict[str, Any],
    ) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"execution_failed"}, "confirm_retry_from_safe_point")
        required = {"failure_stage_displayed", "written_files_displayed", "unfinished_actions_displayed", "confirmed"}
        missing = sorted(key for key in required if not evidence.get(key))
        if missing:
            raise ExecutionObjectError(f"Retry confirmation missing evidence: {missing}")
        remaining_scope = _as_string_set(evidence.get("remaining_write_scope", []))
        approved_scope = _as_string_set(obj.get("write_scope", []))
        if not remaining_scope.issubset(approved_scope):
            raise ExecutionObjectError("Retry scope exceeds approved scope; resubmit or escalate confirmation.")
        drift = drift_diff((obj.get("submission_snapshot") or {}).get("related_facts", {}), current_facts)
        if drift:
            obj["stale_before_execution"] = {
                "drift_check_id": f"DC-{execution_object_id}-retry",
                "diff": drift,
            }
            self._append_history(obj, "stale_before_execution", "retry blocked by drift")
        else:
            obj["retry_from_safe_point"] = {
                "at": now_iso(),
                "evidence": deep_copy(evidence),
            }
            self._append_history(obj, "approved", "retry from safe point confirmed")
        self.save()
        return deep_copy(obj)

    def create_rollback_plan_from_failure(self, execution_object_id: str, *, title: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"execution_failed"}, "create_rollback_plan_from_failure")
        return self.create_draft(
            object_type="rollback_plan",
            title=title,
            source_execution_object_id=execution_object_id,
            prefilled_content={
                "failure_records": deep_copy(obj.get("failure_records", [])),
                "rollback_source": execution_object_id,
            },
            related_facts=(obj.get("submission_snapshot") or {}).get("related_facts", {}),
            write_scope=obj.get("write_scope", []),
            metadata={"rollback_source_execution_object_id": execution_object_id},
        )

    def record_manual_remediation(self, execution_object_id: str, *, evidence: dict[str, Any]) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"execution_failed"}, "record_manual_remediation")
        required = {"remediation_note", "affected_files", "final_hashes", "validation_result"}
        missing = sorted(key for key in required if not evidence.get(key))
        if missing:
            raise ExecutionObjectError(f"Manual remediation missing evidence: {missing}")
        affected_scope = _as_string_set(evidence.get("affected_scopes", []))
        approved_scope = _as_string_set(obj.get("write_scope", []))
        if affected_scope and not affected_scope.issubset(approved_scope):
            raise ExecutionObjectError("Manual remediation scope exceeds original approved scope.")
        forbidden_keys = {
            "unplanned_file_writes",
            "asset_contract_changes",
            "reference_migrations",
            "relationship_graph_changes",
            "t3_or_art_baseline_changes",
            "style_branch_changes",
            "replacement_batch_changes",
            "rollback_source_changes",
            "new_asset_ids",
            "new_unity_runtime_files",
        }
        forbidden = sorted(key for key in forbidden_keys if evidence.get(key))
        if forbidden:
            raise ExecutionObjectError(f"Manual remediation requires a new execution object: {forbidden}")
        obj["manual_remediation"] = {
            "at": now_iso(),
            "evidence": deep_copy(evidence),
        }
        self.save()
        return deep_copy(obj)

    def record_automated_remediation(self, execution_object_id: str, *, evidence: dict[str, Any]) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"execution_failed", "approved"}, "record_automated_remediation")
        required = {
            "repair_attempt_id",
            "correction_id",
            "affected_files",
            "final_hashes",
            "validation_result",
            "scope_verified",
            "allowed_write_paths_checked",
        }
        missing = sorted(key for key in required if not evidence.get(key))
        if missing:
            raise ExecutionObjectError(f"Automated remediation missing evidence: {missing}")
        if evidence.get("unexpected_changes"):
            raise ExecutionObjectError("Automated remediation cannot verify unexpected changes.")
        affected_scope = _as_string_set(evidence.get("affected_scopes", []))
        approved_scope = _as_string_set(obj.get("write_scope", []))
        if affected_scope and not affected_scope.issubset(approved_scope):
            raise ExecutionObjectError("Automated remediation scope exceeds original approved scope.")
        obj["automated_remediation"] = {
            "at": now_iso(),
            "evidence": deep_copy(evidence),
        }
        self.save()
        return deep_copy(obj)

    def cancel_after_failure(self, execution_object_id: str, *, reason: str) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"execution_failed"}, "cancel_after_failure")
        obj.setdefault("cancellation_records", []).append({
            "at": now_iso(),
            "reason": reason,
            "type": "cancel_after_failure",
            "preserved_failure_records": [item.get("failure_record_id") for item in obj.get("failure_records", [])],
        })
        self._append_history(obj, "cancelled", "cancelled after failure", {"reason": reason})
        self.save()
        return deep_copy(obj)

    def verify(self, execution_object_id: str, *, evidence: dict[str, Any]) -> dict[str, Any]:
        obj = self.get(execution_object_id)
        _require_state(obj, {"executing", "approved", "execution_failed"}, "verify")
        if (
            obj.get("state") == "execution_failed"
            and not obj.get("manual_remediation")
            and not obj.get("automated_remediation")
        ):
            raise ExecutionObjectError("execution_failed requires manual remediation or another recovery path before verification.")
        required_shared = {
            "execution_logs_complete",
            "written_files_recorded",
            "final_hashes_recorded",
            "project_state_updated",
            "no_unresolved_execution_failed",
            "no_blocking_drift_or_conflict",
        }
        missing_shared = sorted(key for key in required_shared if not evidence.get(key))
        if missing_shared:
            raise ExecutionObjectError(f"Verification missing shared facts: {missing_shared}")
        object_type = obj.get("object_type", "")
        required_type = TYPE_SPECIFIC_VERIFICATION_REQUIREMENTS.get(object_type, set())
        type_checks = evidence.get("type_specific_checks", {})
        missing_type = sorted(key for key in required_type if not type_checks.get(key))
        if missing_type:
            raise ExecutionObjectError(f"Verification missing {object_type} checks: {missing_type}")
        record = {
            "verification_record_id": f"VR-{execution_object_id}-{len(obj.get('verification_records', [])) + 1:03d}",
            "at": now_iso(),
            "evidence": deep_copy(evidence),
        }
        obj.setdefault("verification_records", []).append(record)
        self._append_history(obj, "verified", "verification standard passed", {
            "verification_record_id": record["verification_record_id"],
        })
        self.save()
        return deep_copy(obj)

    def record_audit_cleanup_evidence(
        self,
        execution_object_id: str,
        *,
        material_kind: str,
        source_path: str,
        summary_hash: str,
        reason: str,
        remaining_trace_location: str,
    ) -> dict[str, Any]:
        if material_kind in AUDIT_SPINE_KEYS:
            raise ExecutionObjectError(f"Audit spine material cannot be cleaned: {material_kind}")
        if material_kind not in CLEANABLE_DERIVED_MATERIALS:
            raise ExecutionObjectError(f"Unknown cleanable derived material kind: {material_kind}")
        obj = self.get(execution_object_id)
        evidence = {
            "at": now_iso(),
            "execution_object_id": execution_object_id,
            "material_kind": material_kind,
            "source_path": source_path,
            "summary_hash": summary_hash,
            "reason": reason,
            "remaining_trace_location": remaining_trace_location,
        }
        obj.setdefault("audit_cleanup_evidence", []).append(evidence)
        self.data.setdefault("audit_cleanup_evidence", []).append(evidence)
        self.save()
        return deep_copy(evidence)
