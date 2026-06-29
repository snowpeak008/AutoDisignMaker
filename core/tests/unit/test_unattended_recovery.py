from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from core.context import StageContext
from core.engines import generation
from core.engines.execution_objects.correction_queue import load_queue, save_queue_json
from core.engines.execution_objects.unattended_recovery import (
    build_failure_event,
    build_resume_cursor,
    dependency_skip_ids,
    upsert_failure_queue,
    write_reproduction_payload,
)
from core.engines.execution_objects.workflow import ExecutionObjectError, ExecutionObjectStore
from core.io import read_json, write_json
from pipeline.step_13_integration_validation import plugin as step13_plugin


def _patch_stage11_stage_dir(monkeypatch, tmp_path: Path) -> Path:
    artifacts_root = tmp_path / "outputs" / "artifacts"

    def fake_stage_dir(stage: int) -> Path:
        return artifacts_root / f"stage_{stage:02d}"

    monkeypatch.setattr(generation, "stage_dir", fake_stage_dir)
    monkeypatch.setattr(generation, "BASE_DIR", tmp_path)
    return artifacts_root / "stage_11"


def _write_task_record(stage_path: Path, task_id: str, status: str) -> None:
    stage_path.mkdir(parents=True, exist_ok=True)
    write_json(
        stage_path / f"{task_id}_execution.json",
        {"task_id": task_id, "status": status},
    )


def test_unattended_queue_preserves_extra_fields_roundtrip(tmp_path):
    record = {
        "task_id": "DEV-014",
        "group_id": "PG-003-ui",
        "status": "failed",
        "codex_errors": ["compile failed"],
        "changed_files": ["Assets/Scripts/Foo.cs"],
        "execution_object_id": "EO-001",
        "reproduction_payload_path": "stage_11/reproduction_payload_DEV-014.md",
    }
    event = build_failure_event(
        stage=11,
        record=record,
        reproduction_payload_path=record["reproduction_payload_path"],
    )

    upsert_failure_queue(
        tmp_path,
        stage=11,
        events=[event],
        reviewed_contract="program_task_breakdown.json",
        source_review="stage_11_unattended_execution",
    )
    queue = load_queue(tmp_path / "correction_queue.json")
    assert queue.items[0].extras["task_id"] == "DEV-014"
    assert queue.items[0].extras["error_hash"] == event.error_hash
    assert queue.items[0].extras["reproduction_payload_path"].endswith("DEV-014.md")

    save_queue_json(queue, tmp_path / "roundtrip.json")
    raw = json.loads((tmp_path / "roundtrip.json").read_text(encoding="utf-8"))
    correction = raw["corrections"][0]
    assert correction["task_id"] == "DEV-014"
    assert correction["error_hash"] == event.error_hash


def test_resume_cursor_uses_counts_not_completed_task_array():
    records = [
        {"task_id": "DEV-001", "status": "success"},
        {"task_id": "DEV-002", "status": "auto_repaired"},
        {"task_id": "DEV-003", "status": "failed"},
        {"task_id": "DEV-004", "status": "skipped_by_dependency"},
    ]

    cursor = build_resume_cursor(
        stage=11,
        records=records,
        current_group_id="PG-002",
        current_task_id="DEV-003",
        next_task_id="DEV-005",
    )

    assert cursor["completed_task_count"] == 2
    assert cursor["failed_task_ids"] == ["DEV-003"]
    assert cursor["skipped_task_count"] == 1
    assert "completed_task_ids" not in cursor
    assert cursor["task_record_source"] == "stage_11/DEV-*_execution.json"


def test_stage11_has_no_local_import_shadowing_module_names():
    source_path = Path(inspect.getsourcefile(generation) or "")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            module_names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Import):
            module_names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    start = next(node.lineno for node in functions if node.name == "_stage11_checkpoint_root")
    end = next(node.lineno for node in functions if node.name == "_stage12_outputs")

    class Scanner(ast.NodeVisitor):
        def __init__(self) -> None:
            self.loads: list[tuple[str, int]] = []
            self.defs: list[tuple[str, int]] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            self.defs.extend(
                (alias.asname or alias.name.split(".")[0], node.lineno)
                for alias in node.names
            )

        def visit_Import(self, node: ast.Import) -> None:
            self.defs.extend(
                (alias.asname or alias.name.split(".")[0], node.lineno)
                for alias in node.names
            )

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load):
                self.loads.append((node.id, node.lineno))
            elif isinstance(node.ctx, (ast.Store, ast.Del)):
                self.defs.append((node.id, node.lineno))

    suspicious: list[tuple[str, str, int, int]] = []
    for func in functions:
        if not (start <= func.lineno < end):
            continue
        scanner = Scanner()
        for child in func.body:
            scanner.visit(child)
        for name in {item[0] for item in scanner.defs} & module_names:
            first_def = min(line for def_name, line in scanner.defs if def_name == name)
            earlier_loads = [
                line for load_name, line in scanner.loads if load_name == name and line < first_def
            ]
            if earlier_loads:
                suspicious.append((func.name, name, min(earlier_loads), first_def))

    assert suspicious == []


def test_stage11_task_records_write_to_stage11_resume_dir(tmp_path, monkeypatch):
    stage11 = _patch_stage11_stage_dir(monkeypatch, tmp_path)
    record = {"task_id": "DEV-001", "status": "success"}

    generation._write_stage11_task_record(stage11, "DEV-001", record)

    assert (stage11 / "DEV-001_execution.json").exists()
    assert (
        tmp_path
        / "outputs"
        / "checkpoints"
        / "stage_11_resume_records"
        / "DEV-001_execution.json"
    ).exists()
    assert not (
        tmp_path
        / "outputs"
        / "checkpoints"
        / "stage_12_resume_records"
        / "DEV-001_execution.json"
    ).exists()


def test_stage11_previous_records_read_legacy_stage12_resume_dir(tmp_path, monkeypatch):
    _patch_stage11_stage_dir(monkeypatch, tmp_path)
    legacy = tmp_path / "outputs" / "checkpoints" / "stage_12_resume_records"
    _write_task_record(legacy, "DEV-001", "legacy")

    records = generation._previous_records_by_task()

    assert records["DEV-001"]["status"] == "legacy"


def test_stage11_previous_records_prefer_stage11_resume_dir_over_legacy(tmp_path, monkeypatch):
    _patch_stage11_stage_dir(monkeypatch, tmp_path)
    checkpoints = tmp_path / "outputs" / "checkpoints"
    _write_task_record(checkpoints / "stage_12_resume_records", "DEV-001", "legacy")
    _write_task_record(checkpoints / "stage_11_resume_records", "DEV-001", "current")

    records = generation._previous_records_by_task()

    assert records["DEV-001"]["status"] == "current"


def test_stage11_previous_records_read_current_save_workspace_from_saves(tmp_path, monkeypatch):
    _patch_stage11_stage_dir(monkeypatch, tmp_path)
    save_workspace = tmp_path / "saves" / "save-1" / "workspace"
    save_stage = save_workspace / "outputs" / "artifacts" / "stage_11"
    _write_task_record(save_stage, "DEV-001", "saved")
    monkeypatch.setattr(
        generation.save_manager,
        "current_save_workspace_dir",
        lambda _root: save_workspace,
    )

    records = generation._previous_records_by_task()

    assert records["DEV-001"]["status"] == "saved"


def test_stage11_previous_records_prefer_active_stage_over_save_workspace(tmp_path, monkeypatch):
    active_stage = _patch_stage11_stage_dir(monkeypatch, tmp_path)
    save_workspace = tmp_path / "saves" / "save-1" / "workspace"
    save_stage = save_workspace / "outputs" / "artifacts" / "stage_11"
    _write_task_record(save_stage, "DEV-001", "saved")
    _write_task_record(active_stage, "DEV-001", "active")
    monkeypatch.setattr(
        generation.save_manager,
        "current_save_workspace_dir",
        lambda _root: save_workspace,
    )

    records = generation._previous_records_by_task()

    assert records["DEV-001"]["status"] == "active"
    assert "setdefault" not in inspect.getsource(generation._previous_records_by_task)


def test_stage11_run_state_uses_stage11_task_unit_type(tmp_path, monkeypatch):
    run_state_path = tmp_path / "run_state.json"
    monkeypatch.setattr(
        generation.runtime_control,
        "run_state_path",
        lambda _root: run_state_path,
    )

    generation._write_stage11_progress(
        tmp_path,
        project_path=tmp_path / "unity",
        editor_path=tmp_path / "Unity.exe",
        expected_count=1,
        execution_records=[{"task_id": "DEV-001", "status": "success"}],
        package_reports=[],
        changed_files_manifest=[],
    )

    state = read_json(run_state_path, {})
    progress = read_json(tmp_path / "devexecution_progress.json", {})
    assert state["current_step"] == 11
    assert state["unit_type"] == "stage11_task"
    assert "Stage 12" not in progress["note"]


def test_stage11_stop_report_uses_stage_11(tmp_path):
    report = generation._write_stage11_stop_report(
        tmp_path,
        expected_count=1,
        execution_records=[{"task_id": "DEV-001", "status": "auto_repaired"}],
        current_group_id="PG-001",
        current_task_id="DEV-001",
        next_task_id="",
        stop_reason="operator stop",
    )

    assert report["stage"] == 11
    assert report["successful_task_count"] == 1
    saved = read_json(tmp_path / "devexecution_stop_report.json", {})
    assert saved["stage"] == 11


def test_stage11_execution_object_fallback_uses_stage11_constant():
    source = inspect.getsource(generation._stage11_outputs)

    assert 'obj.get("metadata", {}).get("stage") == DEV_EXECUTION_STAGE' in source
    assert 'obj.get("metadata", {}).get("stage") == 10' not in source


def test_step13_development_blocker_messages_reference_step11():
    source = inspect.getsource(generation._stage13_outputs)

    assert "Stage 12 produced no real development records." not in source
    assert "Stage 12 did not record Unity batchmode validation." not in source
    assert "Stage 12/13 execution objects must be verified before integration." not in source
    assert "Step 11 produced no real development records." in source
    assert "Step 11 did not record Unity batchmode validation." in source
    assert "Step 11/12 execution objects must be verified before integration." in source


def test_dependency_skip_marks_group_and_transitive_dependents():
    skipped = dependency_skip_ids(
        failed_task_ids={"DEV-001"},
        current_group_id="PG-001",
        parallel_groups=[
            {"group_id": "PG-001", "task_ids": ["DEV-001", "DEV-002"]},
            {"group_id": "PG-002", "task_ids": ["DEV-003"], "depends_on_groups": ["PG-001"]},
            {"group_id": "PG-003", "task_ids": ["DEV-004"], "depends_on_groups": []},
        ],
        dependencies=[{"from": "DEV-001", "to": "DEV-003"}],
    )

    assert skipped["DEV-002"]["status"] == "skipped_by_failed_group"
    assert skipped["DEV-003"]["status"] == "skipped_by_dependency"
    assert "DEV-004" not in skipped


def test_reproduction_payload_contains_original_prompt(tmp_path):
    rel_path = write_reproduction_payload(
        tmp_path,
        task={"task_id": "DEV-014", "title": "Implement combat", "acceptance": "passes"},
        prompt="ORIGINAL TASK PROMPT",
        adapter_name="codex",
        timeout_seconds=720,
        allowed_write_paths=["Assets/Scripts"],
        output_files=["Assets/Scripts/Foo.cs"],
        package_changes=[],
    )

    payload_path = tmp_path / "reproduction_payload_DEV-014.md"
    assert payload_path.exists()
    text = payload_path.read_text(encoding="utf-8")
    assert "ORIGINAL TASK PROMPT" in text
    assert "Assets/Scripts/Foo.cs" in text
    assert rel_path.endswith("reproduction_payload_DEV-014.md")


def test_completed_with_review_stage_report_is_valid(tmp_path):
    updated = generation._update_stage_report(
        11,
        tmp_path,
        {
            "status": "completed_with_review",
            "content_exists": True,
            "blocking_issues": 0,
            "review_items_count": 1,
            "traceability_valid": True,
        },
    )

    assert updated["status"] == "completed_with_review"
    assert updated["valid"] is True
    assert updated["review_items_count"] == 1
    saved = read_json(tmp_path / "validation_report.json", {})
    assert saved["valid"] is True


def test_execution_object_allows_automated_remediation_before_verify(tmp_path):
    store = ExecutionObjectStore(tmp_path / "execution_objects.json", expected_save_id="save-1")
    store.data["objects"].append(
        {
            "execution_object_id": "EO-001",
            "object_type": "integration_validation",
            "title": "recoverable object",
            "state": "execution_failed",
            "created_at": "2026-06-28T00:00:00",
            "updated_at": "2026-06-28T00:00:00",
            "source_diagnostic_id": "",
            "prefilled_content": {},
            "user_content": {},
            "related_facts": {},
            "write_scope": ["unity_file:Assets/Scripts/Foo.cs"],
            "failure_records": [],
            "state_history": [],
            "metadata": {},
        }
    )

    store.record_automated_remediation(
        "EO-001",
        evidence={
            "repair_attempt_id": "RA-001",
            "correction_id": "CQ-001",
            "affected_files": ["Assets/Scripts/Foo.cs"],
            "affected_scopes": ["unity_file:Assets/Scripts/Foo.cs"],
            "final_hashes": {"Assets/Scripts/Foo.cs": "abc"},
            "validation_result": {"status": "passed"},
            "scope_verified": True,
            "unexpected_changes": [],
            "allowed_write_paths_checked": True,
        },
    )
    verified = store.verify(
        "EO-001",
        evidence={
            "execution_logs_complete": True,
            "written_files_recorded": True,
            "final_hashes_recorded": True,
            "project_state_updated": True,
            "no_unresolved_execution_failed": True,
            "no_blocking_drift_or_conflict": True,
            "type_specific_checks": {},
        },
    )

    assert verified["state"] == "verified"


def test_execution_object_save_id_mismatch_still_raises(tmp_path):
    store = ExecutionObjectStore(tmp_path / "execution_objects.json", expected_save_id="save-B")
    store.data["save_id"] = "save-A"

    with pytest.raises(ExecutionObjectError, match="does not match expected save_id"):
        store.save()


def test_execution_object_transfer_ownership_records_audit(tmp_path):
    store = ExecutionObjectStore(tmp_path / "execution_objects.json", expected_save_id=None)
    store.data["save_id"] = "save-A"

    record = store.transfer_ownership_to_save(
        "save-B",
        source_save_id="save-A",
        reason="manual_save_new",
    )
    store.save()

    assert record["from_save_id"] == "save-A"
    assert record["to_save_id"] == "save-B"
    assert store.data["save_id"] == "save-B"
    assert store.data["ownership_migrations"][-1]["reason"] == "manual_save_new"
    saved = json.loads((tmp_path / "execution_objects.json").read_text(encoding="utf-8"))
    assert saved["save_id"] == "save-B"
    assert saved["ownership_migrations"][-1]["from_save_id"] == "save-A"


def test_execution_object_transfer_rejects_wrong_source_save_id(tmp_path):
    store = ExecutionObjectStore(tmp_path / "execution_objects.json", expected_save_id=None)
    store.data["save_id"] = "save-A"

    with pytest.raises(ExecutionObjectError, match="transfer source_save_id"):
        store.transfer_ownership_to_save(
            "save-B",
            source_save_id="save-X",
            reason="manual_save_new",
        )

    assert store.data["save_id"] == "save-A"


def test_step13_blocks_direct_run_when_step11_or_step12_completed_with_review(monkeypatch, tmp_path):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("Step13 should block before importing or generating outputs.")

    monkeypatch.setattr(step13_plugin, "get_config", lambda key, default=None: False)
    monkeypatch.setattr(step13_plugin, "run_import_step", unexpected_call)
    monkeypatch.setattr(step13_plugin, "apply_development_plan_outputs", unexpected_call)

    for step_num in (11, 12):
        monkeypatch.setattr(
            step13_plugin,
            "load_pipeline_state",
            lambda project_root, step_num=step_num: {
                "steps": {str(step_num): {"status": "completed_with_review"}},
            },
        )

        result = step13_plugin.Plugin().execute(StageContext(stage_id="13", project_root=tmp_path))

        assert result.status == "blocked"
        assert result.outputs["blocked_step"] == step_num
        assert "Handle correction_queue first" in result.outputs["message"]


def test_step13_direct_run_can_continue_when_review_override_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(
        step13_plugin,
        "load_pipeline_state",
        lambda project_root: {"steps": {"11": {"status": "completed_with_review"}}},
    )
    monkeypatch.setattr(step13_plugin, "get_config", lambda key, default=None: True)
    monkeypatch.setattr(step13_plugin, "run_import_step", lambda *args, **kwargs: {"imported": True})
    monkeypatch.setattr(
        step13_plugin,
        "apply_development_plan_outputs",
        lambda stage, report: {"status": "success", "imported": report["imported"]},
    )

    result = step13_plugin.Plugin().execute(StageContext(stage_id="13", project_root=tmp_path))

    assert result.status == "success"
    assert result.outputs["imported"] is True
