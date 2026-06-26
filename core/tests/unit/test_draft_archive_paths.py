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
    make_draft(
        isolated_project_root,
        "20260101_000001_linked",
        {"linked_archive_path": str(isolated_project_root / "saves" / "save_keep")},
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
