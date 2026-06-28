from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.paths import (
    DRAFT_DIR,
    DRAFTS_DIR,
    PROJECT_ROOT,
    SANDBOX_DIR,
    SOURCE_ARTIFACTS_DIR,
)
from core.registry import max_step_number
from core.save import manager as save_manager


@pytest.fixture
def isolated_project_root(tmp_path, monkeypatch):
    def fail_project_root_lookup(root):
        raise RuntimeError(f"isolated test root: {root}")

    monkeypatch.setattr(save_manager, "locate_project_root", fail_project_root_lookup)
    return tmp_path


def make_draft(root: Path, name: str, meta: dict[str, object] | None = None) -> Path:
    draft = root / "drafts" / name
    draft.mkdir(parents=True)
    if meta is not None:
        (draft / "draft_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )
    return draft


def write_execution_object_store(workspace_root: Path, save_id: str) -> Path:
    path = workspace_root / save_manager._execution_object_store_relpath()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "save_id": save_id,
                "generated_at": "2026-06-28T00:00:00",
                "updated_at": "2026-06-28T00:00:00",
                "objects": [],
                "audit_cleanup_evidence": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def read_execution_object_store(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_paths_use_current_session_draft() -> None:
    assert DRAFT_DIR.parent == DRAFTS_DIR
    assert SANDBOX_DIR == DRAFT_DIR
    assert SANDBOX_DIR != PROJECT_ROOT / "sandbox"
    assert SOURCE_ARTIFACTS_DIR == DRAFT_DIR / "source_artifacts"


def test_formal_archive_excludes_snapshot_history(isolated_project_root) -> None:
    active_source = isolated_project_root / "source_artifacts"
    active_source.mkdir(parents=True)
    (active_source / "idea.txt").write_text("demo", encoding="utf-8")

    manifest = save_manager.create_save(
        isolated_project_root, "Demo", event="unit_test"
    )
    save_path = save_manager.save_dir(isolated_project_root, manifest["save_id"])
    expected_total = max_step_number() + 1

    assert (save_path / "manifest.json").is_file()
    assert manifest["progress"] == {
        "passed": 0,
        "total": expected_total,
        "label": f"已通过 0/{expected_total}",
    }
    assert (save_path / "workspace" / "source_artifacts" / "idea.txt").read_text(
        encoding="utf-8"
    ) == "demo"
    assert not (save_path / "snapshots").exists()
    assert not (save_path / "save_file_map.json").exists()
    assert not (save_path / "timeline.jsonl").exists()
    assert not (save_path / "save_manifest.json").exists()
    draft_meta = json.loads(
        (isolated_project_root / "draft_meta.json").read_text(encoding="utf-8")
    )
    assert draft_meta["linked_save_id"] == manifest["save_id"]
    assert (isolated_project_root / "snapshots").is_dir()
    assert (isolated_project_root / "timeline.jsonl").is_file()


def test_save_progress_uses_dynamic_pipeline_total(isolated_project_root) -> None:
    expected_total = max_step_number() + 1

    progress = save_manager._progress(isolated_project_root)

    assert progress == {
        "passed": 0,
        "total": expected_total,
        "label": f"已通过 0/{expected_total}",
    }


def test_legacy_save_manifest_is_still_readable(isolated_project_root) -> None:
    save_id = "save_legacy"
    legacy_dir = isolated_project_root / "saves" / save_id
    legacy_dir.mkdir(parents=True)
    legacy_manifest = {
        "schema_version": 1,
        "save_id": save_id,
        "display_name": "Legacy",
        "created_at": "2026-01-01T00:00:00",
        "last_worked_at": "2026-01-01T00:00:00",
    }
    (legacy_dir / "save_manifest.json").write_text(
        json.dumps(legacy_manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    assert save_manager.get_save(isolated_project_root, save_id) == legacy_manifest


def test_clear_active_workspace_removes_draft_runtime_history(
    isolated_project_root,
) -> None:
    (isolated_project_root / "snapshots" / "000001_test").mkdir(parents=True)
    (isolated_project_root / "draft_file_map.json").write_text("{}", encoding="utf-8")
    (isolated_project_root / "timeline.jsonl").write_text("{}\n", encoding="utf-8")
    (isolated_project_root / "source_artifacts").mkdir()

    save_manager.clear_active_workspace(isolated_project_root)

    assert not (isolated_project_root / "snapshots").exists()
    assert not (isolated_project_root / "draft_file_map.json").exists()
    assert not (isolated_project_root / "timeline.jsonl").exists()
    assert (isolated_project_root / "source_artifacts").is_dir()


def test_prune_old_drafts_keeps_recent_linked_and_current(
    isolated_project_root,
    monkeypatch,
) -> None:
    current = make_draft(isolated_project_root, "20260101_000002_current")
    monkeypatch.setattr(save_manager, "DRAFT_DIR", current)
    make_draft(isolated_project_root, "20260101_000000_old")
    # linked draft: the save directory actually exists on disk → kept
    save_keep = isolated_project_root / "saves" / "save_keep"
    save_keep.mkdir(parents=True)
    make_draft(
        isolated_project_root,
        "20260101_000001_linked",
        {"linked_archive_path": str(save_keep)},
    )
    make_draft(isolated_project_root, "20260101_000003_old")
    recent_a = make_draft(isolated_project_root, "20260101_000004_recent")
    recent_b = make_draft(isolated_project_root, "20260101_000005_recent")

    deleted = save_manager.prune_old_drafts(isolated_project_root, keep_count=2)

    assert deleted == ["20260101_000000_old", "20260101_000003_old"]
    assert current.exists()
    assert recent_a.exists()
    assert recent_b.exists()
    assert (isolated_project_root / "drafts" / "20260101_000001_linked").exists()


def test_prune_old_drafts_removes_orphan_drafts(
    isolated_project_root,
    monkeypatch,
) -> None:
    current = make_draft(isolated_project_root, "20260101_000002_current")
    monkeypatch.setattr(save_manager, "DRAFT_DIR", current)
    # orphan: linked_save_id points to a save that no longer exists
    make_draft(
        isolated_project_root,
        "20260101_000000_orphan",
        {"linked_save_id": "save_gone"},
    )
    recent = make_draft(isolated_project_root, "20260101_000001_recent")

    deleted = save_manager.prune_old_drafts(isolated_project_root, keep_count=1)

    assert "20260101_000000_orphan" in deleted
    assert recent.exists()
    assert current.exists()


def test_prune_draft_snapshots_prunes_only_pruneable_drafts(
    isolated_project_root,
    monkeypatch,
) -> None:
    current = make_draft(isolated_project_root, "20260101_000000_current")
    current_snapshot = current / "snapshots" / "000001_current"
    current_snapshot.mkdir(parents=True)
    monkeypatch.setattr(save_manager, "DRAFT_DIR", current)

    save_keep = isolated_project_root / "saves" / "save_keep"
    save_keep.mkdir(parents=True)
    linked = make_draft(
        isolated_project_root,
        "20260101_000001_linked",
        {"linked_save_id": "save_keep"},
    )
    linked_snapshot = linked / "snapshots" / "000001_linked"
    linked_snapshot.mkdir(parents=True)

    orphan = make_draft(
        isolated_project_root,
        "20260101_000002_orphan",
        {"linked_save_id": "save_gone"},
    )
    (orphan / "snapshots" / "000001_orphan").mkdir(parents=True)
    (orphan / "snapshots" / "000002_orphan").mkdir(parents=True)

    unlinked = make_draft(isolated_project_root, "20260101_000003_unlinked")
    (unlinked / "snapshots" / "000001_unlinked").mkdir(parents=True)

    pruned = save_manager.prune_draft_snapshots(
        isolated_project_root, keep_per_draft=0
    )

    assert pruned == ["20260101_000002_orphan", "20260101_000003_unlinked"]
    assert current_snapshot.exists()
    assert linked_snapshot.exists()
    assert not (orphan / "snapshots").exists()
    assert not (unlinked / "snapshots").exists()


def test_prune_draft_snapshots_keeps_latest_snapshots(
    isolated_project_root,
    monkeypatch,
) -> None:
    current = make_draft(isolated_project_root, "20260101_000000_current")
    monkeypatch.setattr(save_manager, "DRAFT_DIR", current)
    draft = make_draft(
        isolated_project_root,
        "20260101_000001_orphan",
        {"linked_save_id": "save_gone"},
    )
    old_snapshot = draft / "snapshots" / "000001_old"
    new_snapshot = draft / "snapshots" / "000002_new"
    old_snapshot.mkdir(parents=True)
    new_snapshot.mkdir(parents=True)

    pruned = save_manager.prune_draft_snapshots(
        isolated_project_root, keep_per_draft=1
    )

    assert pruned == ["20260101_000001_orphan"]
    assert not old_snapshot.exists()
    assert new_snapshot.exists()


def test_delete_save_removes_linked_drafts_but_keeps_current_and_unrelated(
    isolated_project_root,
    monkeypatch,
) -> None:
    manifest = save_manager.create_save(
        isolated_project_root, "Demo", event="unit_test"
    )
    save_id = manifest["save_id"]
    current = make_draft(
        isolated_project_root,
        "20260101_000000_current",
        {"linked_save_id": save_id},
    )
    monkeypatch.setattr(save_manager, "DRAFT_DIR", current)
    linked_direct = make_draft(
        isolated_project_root,
        "20260101_000001_linked",
        {"linked_save_id": save_id},
    )
    linked_legacy = make_draft(
        isolated_project_root,
        "20260101_000002_legacy",
        {"linked_archive_path": str(isolated_project_root / "saves" / save_id)},
    )
    unrelated = make_draft(
        isolated_project_root,
        "20260101_000003_unrelated",
        {"linked_save_id": "save_other"},
    )

    save_manager.delete_save(isolated_project_root, save_id)

    assert not save_manager.save_dir(isolated_project_root, save_id).exists()
    assert not linked_direct.exists()
    assert not linked_legacy.exists()
    assert current.exists()
    assert unrelated.exists()


def test_reset_current_draft_outputs_clears_artifacts_only(
    isolated_project_root,
) -> None:
    stage = isolated_project_root / "outputs" / "artifacts" / "stage_00"
    stage.mkdir(parents=True)
    (stage / "artifact.json").write_text("{}", encoding="utf-8")
    checkpoint = isolated_project_root / "outputs" / "checkpoints" / "keep.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("{}", encoding="utf-8")
    source = isolated_project_root / "source_artifacts" / "idea.txt"
    source.parent.mkdir(parents=True)
    source.write_text("demo", encoding="utf-8")

    save_manager.reset_current_draft_outputs(isolated_project_root, stage_from=0)

    assert (isolated_project_root / "outputs" / "artifacts").is_dir()
    assert not stage.exists()
    assert checkpoint.exists()
    assert source.exists()


def test_prune_sibling_draft_outputs_clears_same_save_artifacts_only(
    isolated_project_root,
    monkeypatch,
) -> None:
    manifest = save_manager.create_save(
        isolated_project_root, "Demo", event="unit_test"
    )
    save_id = manifest["save_id"]
    current = make_draft(
        isolated_project_root,
        "20260101_000000_current",
        {"linked_save_id": save_id},
    )
    current_stage = current / "outputs" / "artifacts" / "stage_00"
    current_stage.mkdir(parents=True)
    (current_stage / "keep.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(save_manager, "DRAFT_DIR", current)

    linked = make_draft(
        isolated_project_root,
        "20260101_000001_linked",
        {"linked_save_id": save_id},
    )
    linked_stage = linked / "outputs" / "artifacts" / "stage_00"
    linked_stage.mkdir(parents=True)
    (linked_stage / "old.json").write_text("{}", encoding="utf-8")
    linked_source = linked / "source_artifacts" / "idea.txt"
    linked_source.parent.mkdir(parents=True)
    linked_source.write_text("demo", encoding="utf-8")

    unrelated = make_draft(
        isolated_project_root,
        "20260101_000002_unrelated",
        {"linked_save_id": "save_other"},
    )
    unrelated_stage = unrelated / "outputs" / "artifacts" / "stage_00"
    unrelated_stage.mkdir(parents=True)
    (unrelated_stage / "keep.json").write_text("{}", encoding="utf-8")

    pruned = save_manager.prune_sibling_draft_outputs(
        isolated_project_root, stage_from=0
    )

    assert pruned == ["20260101_000001_linked"]
    assert current_stage.exists()
    assert linked.exists()
    assert not (linked / "outputs" / "artifacts").exists()
    assert linked_source.exists()
    assert (linked / "draft_meta.json").exists()
    assert unrelated_stage.exists()


def test_migrate_workspace_project_id_reports_manifest_changes_once(
    isolated_project_root,
) -> None:
    package = isolated_project_root / "source_artifacts" / "devflow_Concept_v1"
    package.mkdir(parents=True)
    (package / "selected_play_prototype.json").write_text("{}", encoding="utf-8")

    assert save_manager.migrate_workspace_project_id(isolated_project_root) is True
    manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
    assert manifest["project_id"] == save_manager.PROJECT_ID
    assert manifest["package_type"] == "Concept"

    assert save_manager.migrate_workspace_project_id(isolated_project_root) is False


def test_build_file_map_reuses_cached_sha256(
    isolated_project_root,
    monkeypatch,
) -> None:
    workspace_file = isolated_project_root / "workspace" / "notes.txt"
    workspace_file.parent.mkdir(parents=True)
    workspace_file.write_text("unchanged", encoding="utf-8")
    first = save_manager.build_file_map(isolated_project_root, transaction_seq=1)
    save_manager.write_json(isolated_project_root / "draft_file_map.json", first)

    def fail_sha256(path: Path) -> str:
        raise AssertionError(f"unexpected sha256 recompute: {path}")

    monkeypatch.setattr(save_manager, "_sha256", fail_sha256)

    second = save_manager.build_file_map(isolated_project_root, transaction_seq=2)

    entry = next(item for item in second["files"] if item["workspace_path"] == "workspace/notes.txt")
    assert entry["sha256"] == first["files"][0]["sha256"]
    assert entry["latest_transaction_seq"] == 2


def test_sync_current_save_trims_current_draft_snapshots(
    isolated_project_root,
) -> None:
    workspace_file = isolated_project_root / "workspace" / "notes.txt"
    workspace_file.parent.mkdir(parents=True)
    workspace_file.write_text("0", encoding="utf-8")
    manifest = save_manager.create_save(isolated_project_root, "Demo", event="unit_test")

    for index in range(7):
        workspace_file.write_text(str(index + 1), encoding="utf-8")
        save_manager.sync_current_save(isolated_project_root, event=f"unit_test_{index}")

    snap_dir = isolated_project_root / "snapshots"
    snapshots = sorted(path.name for path in snap_dir.iterdir() if path.is_dir())
    assert len(snapshots) == 5
    assert snapshots[-1].endswith("unit_test_6")
    assert save_manager.current_save_id(isolated_project_root) == manifest["save_id"]


def test_sync_current_save_snapshot_skips_binary_but_archive_keeps_it(
    isolated_project_root,
) -> None:
    image = (
        isolated_project_root
        / "outputs"
        / "artifacts"
        / "stage_07"
        / "generated_images"
        / "STYLE-01.png"
    )
    image.parent.mkdir(parents=True)
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    text = isolated_project_root / "workspace" / "notes.txt"
    text.parent.mkdir(parents=True)
    text.write_text("keep", encoding="utf-8")

    manifest = save_manager.create_save(
        isolated_project_root, "Demo", event="unit_test"
    )
    save_id = manifest["save_id"]
    archive_image = (
        save_manager.workspace_dir(isolated_project_root, save_id)
        / "outputs"
        / "artifacts"
        / "stage_07"
        / "generated_images"
        / "STYLE-01.png"
    )
    snapshot_full = next((isolated_project_root / "snapshots").glob("*/full"))

    assert archive_image.exists()
    assert not (
        snapshot_full
        / "outputs"
        / "artifacts"
        / "stage_07"
        / "generated_images"
        / "STYLE-01.png"
    ).exists()
    assert (snapshot_full / "workspace" / "notes.txt").read_text(
        encoding="utf-8"
    ) == "keep"


def test_load_save_fast_path_skips_snapshot_creation(
    isolated_project_root,
) -> None:
    source_file = isolated_project_root / "source_artifacts" / "idea.txt"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("demo", encoding="utf-8")
    manifest = save_manager.create_save(isolated_project_root, "Demo", event="unit_test")
    save_id = manifest["save_id"]

    loaded = save_manager.load_save(isolated_project_root, save_id)

    assert loaded["save_id"] == save_id
    assert not (isolated_project_root / "snapshots").exists()
    timeline = (isolated_project_root / "timeline.jsonl").read_text(encoding="utf-8")
    assert "fast path: no migration changes" in timeline
    assert (save_manager.workspace_dir(isolated_project_root, save_id) / "source_artifacts" / "idea.txt").read_text(
        encoding="utf-8"
    ) == "demo"


def test_create_save_transfers_active_execution_object_store_ownership(
    isolated_project_root,
) -> None:
    manifest_a = save_manager.create_save(isolated_project_root, "A", event="unit_test_a")
    save_a = manifest_a["save_id"]
    active_store = write_execution_object_store(isolated_project_root, save_a)
    archive_a_store = write_execution_object_store(
        save_manager.workspace_dir(isolated_project_root, save_a),
        save_a,
    )

    manifest_b = save_manager.create_save(
        isolated_project_root,
        "B",
        event="manual_save_new",
    )
    save_b = manifest_b["save_id"]
    archive_b_store = (
        save_manager.workspace_dir(isolated_project_root, save_b)
        / save_manager._execution_object_store_relpath()
    )

    active_data = read_execution_object_store(active_store)
    archive_b_data = read_execution_object_store(archive_b_store)
    archive_a_data = read_execution_object_store(archive_a_store)

    assert active_data["save_id"] == save_b
    assert archive_b_data["save_id"] == save_b
    assert archive_a_data["save_id"] == save_a
    assert active_data["ownership_migrations"][-1]["from_save_id"] == save_a
    assert active_data["ownership_migrations"][-1]["to_save_id"] == save_b
    assert archive_b_data["ownership_migrations"][-1]["to_save_id"] == save_b
    timeline = (isolated_project_root / "timeline.jsonl").read_text(encoding="utf-8")
    assert "execution_object_store_ownership_transferred" in timeline


def test_load_save_does_not_repair_execution_object_store_save_id_mismatch(
    isolated_project_root,
) -> None:
    from core.engines.execution_objects.workflow import ExecutionObjectError, ExecutionObjectStore

    manifest_a = save_manager.create_save(isolated_project_root, "A", event="unit_test_a")
    save_a = manifest_a["save_id"]
    manifest_b = save_manager.create_save(isolated_project_root, "B", event="unit_test_b")
    save_b = manifest_b["save_id"]
    archive_b_store = write_execution_object_store(
        save_manager.workspace_dir(isolated_project_root, save_b),
        save_a,
    )

    save_manager.load_save(isolated_project_root, save_b)

    assert read_execution_object_store(archive_b_store)["save_id"] == save_a
    with pytest.raises(ExecutionObjectError, match="does not match expected save_id"):
        ExecutionObjectStore(archive_b_store, expected_save_id=save_b).save()


def test_delete_all_saves_clears_index_and_linked_drafts(
    isolated_project_root,
    monkeypatch,
) -> None:
    manifest_one = save_manager.create_save(
        isolated_project_root, "One", event="unit_test_one"
    )
    manifest_two = save_manager.create_save(
        isolated_project_root, "Two", event="unit_test_two"
    )
    save_one = manifest_one["save_id"]
    save_two = manifest_two["save_id"]
    current = make_draft(
        isolated_project_root,
        "20260101_000000_current",
        {"linked_save_id": save_two},
    )
    monkeypatch.setattr(save_manager, "DRAFT_DIR", current)
    linked_one = make_draft(
        isolated_project_root,
        "20260101_000001_linked_one",
        {"linked_save_id": save_one},
    )
    linked_two = make_draft(
        isolated_project_root,
        "20260101_000002_linked_two",
        {"linked_save_id": save_two},
    )
    unrelated = make_draft(
        isolated_project_root,
        "20260101_000003_unrelated",
        {"linked_save_id": "save_other"},
    )

    deleted = save_manager.delete_all_saves(isolated_project_root)
    index = save_manager.load_index(isolated_project_root)

    assert set(deleted) == {save_one, save_two}
    assert len(deleted) == 2
    assert index["saves"] == []
    assert index["current_save_id"] is None
    assert not save_manager.save_dir(isolated_project_root, save_one).exists()
    assert not save_manager.save_dir(isolated_project_root, save_two).exists()
    assert current.exists()
    assert not linked_one.exists()
    assert not linked_two.exists()
    assert unrelated.exists()
    meta = json.loads(
        (isolated_project_root / "draft_meta.json").read_text(encoding="utf-8")
    )
    assert meta["linked_save_id"] is None
