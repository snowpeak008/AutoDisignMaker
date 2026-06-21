from __future__ import annotations

import json

from core.paths import DRAFT_DIR, DRAFTS_DIR, PROJECT_ROOT, SANDBOX_DIR, SOURCE_ARTIFACTS_DIR
from core.save import manager as save_manager


def test_runtime_paths_use_current_session_draft() -> None:
    assert DRAFT_DIR.parent == DRAFTS_DIR
    assert SANDBOX_DIR == DRAFT_DIR
    assert SANDBOX_DIR != PROJECT_ROOT / "sandbox"
    assert SOURCE_ARTIFACTS_DIR == DRAFT_DIR / "source_artifacts"


def test_formal_archive_excludes_snapshot_history(tmp_path) -> None:
    active_source = tmp_path / "source_artifacts"
    active_source.mkdir(parents=True)
    (active_source / "idea.txt").write_text("demo", encoding="utf-8")

    manifest = save_manager.create_save(tmp_path, "Demo", event="unit_test")
    save_path = save_manager.save_dir(tmp_path, manifest["save_id"])

    assert (save_path / "manifest.json").is_file()
    assert (save_path / "workspace" / "source_artifacts" / "idea.txt").read_text(encoding="utf-8") == "demo"
    assert not (save_path / "snapshots").exists()
    assert not (save_path / "save_file_map.json").exists()
    assert not (save_path / "timeline.jsonl").exists()
    assert not (save_path / "save_manifest.json").exists()
    assert (tmp_path / "snapshots").is_dir()
    assert (tmp_path / "timeline.jsonl").is_file()


def test_legacy_save_manifest_is_still_readable(tmp_path) -> None:
    save_id = "save_legacy"
    legacy_dir = tmp_path / "saves" / save_id
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

    assert save_manager.get_save(tmp_path, save_id) == legacy_manifest


def test_clear_active_workspace_removes_draft_runtime_history(tmp_path) -> None:
    (tmp_path / "snapshots" / "000001_test").mkdir(parents=True)
    (tmp_path / "draft_file_map.json").write_text("{}", encoding="utf-8")
    (tmp_path / "timeline.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "source_artifacts").mkdir()

    save_manager.clear_active_workspace(tmp_path)

    assert not (tmp_path / "snapshots").exists()
    assert not (tmp_path / "draft_file_map.json").exists()
    assert not (tmp_path / "timeline.jsonl").exists()
    assert (tmp_path / "source_artifacts").is_dir()
