from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.engines import generation
from core.io import write_json
from core.context import StageContext
from core.ui.style_confirmation_dialog import write_style_confirmation
from pipeline.step_08_art_style_confirmation import plugin as confirmation_plugin


def _patch_stage_dir(monkeypatch, tmp_path: Path) -> None:
    def fake_stage_dir(stage: int) -> Path:
        path = tmp_path / f"stage_{stage:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(generation, "stage_dir", fake_stage_dir)


def test_step07_generates_style_options(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    write_json(
        tmp_path / "stage_04" / "asset_registry.json",
        {
            "assets": [
                {
                    "asset_id": "ASSET-001",
                    "name": "Hero character concept",
                    "asset_type": "character",
                    "source": "design.md:1",
                }
            ]
        },
    )
    monkeypatch.setattr(generation, "get_config", lambda key, default=None: 3)
    monkeypatch.delenv("AUTODESIGNMAKER_ENABLE_IMAGE_GENERATION", raising=False)

    out_dir = tmp_path / "stage_07"
    result = generation._stage7_art_style_generation_outputs(
        {"project_name": "Style Test"}, out_dir
    )

    style_options = json.loads((out_dir / "style_options.json").read_text("utf-8"))
    first_image = out_dir / "generated_images" / "STYLE-01-readable_production.png"

    assert result["style_option_count"] == 3
    assert style_options["option_count"] == 3
    assert first_image.read_bytes().startswith(b"\x89PNG")


def test_step08_blocks_without_confirmation(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    write_json(
        tmp_path / "stage_07" / "style_options.json",
        {
            "options": [
                {
                    "style_id": "STYLE-01",
                    "title": "Readable",
                    "image_path": "drafts/example.png",
                }
            ]
        },
    )
    monkeypatch.setattr(generation, "get_config", lambda key, default=None: True)
    monkeypatch.delenv("AUTODESIGNMAKER_SKIP_ALL_GATES", raising=False)
    monkeypatch.delenv("AUTODESIGNMAKER_SKIP_GATES", raising=False)

    result = generation._stage8_art_style_confirmation_outputs({}, tmp_path / "stage_08")

    assert result["status"] == "waiting_confirmation"
    assert result["confirmation_ui"] == "style_confirmation_dialog"
    assert (tmp_path / "stage_08" / "style_confirmation_pending.json").exists()


def test_step08_auto_pass_when_gate_disabled(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    write_json(
        tmp_path / "stage_07" / "style_options.json",
        {
            "options": [
                {
                    "style_id": "STYLE-01",
                    "title": "Readable",
                    "image_path": "drafts/example.png",
                }
            ]
        },
    )
    monkeypatch.setenv("AUTODESIGNMAKER_SKIP_ALL_GATES", "1")

    result = generation._stage8_art_style_confirmation_outputs({}, tmp_path / "stage_08")
    confirmation = json.loads(
        (tmp_path / "stage_08" / "style_confirmation.json").read_text("utf-8")
    )

    assert result["confirmation_status"] == "approved"
    assert confirmation["mode"] == "auto"
    assert confirmation["selected_style_id"] == "STYLE-01"


def test_step08_uses_existing_confirmation(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    option = {"style_id": "STYLE-02", "title": "Painterly", "image_path": "x.png"}
    write_json(tmp_path / "stage_07" / "style_options.json", {"options": [option]})
    write_style_confirmation(tmp_path / "stage_08", option, "Use warmer lighting.")
    monkeypatch.setattr(generation, "get_config", lambda key, default=None: True)

    result = generation._stage8_art_style_confirmation_outputs({}, tmp_path / "stage_08")

    assert result["confirmation_status"] == "approved"
    assert result["selected_style_id"] == "STYLE-02"


def test_style_confirmation_writer_records_selection(tmp_path) -> None:
    option = {"style_id": "STYLE-03", "title": "Arcade", "image_path": "img.png"}

    path = write_style_confirmation(tmp_path, option, "Keep high contrast.")
    payload = json.loads(path.read_text("utf-8"))

    assert payload["status"] == "approved"
    assert payload["selected_style_id"] == "STYLE-03"
    assert payload["notes"] == "Keep high contrast."


def test_step08_plugin_preserves_manual_confirmation_across_import_reset(
    tmp_path, monkeypatch
) -> None:
    stage08 = tmp_path / "stage_08"
    option = {"style_id": "STYLE-04", "title": "Ink", "image_path": "ink.png"}
    write_style_confirmation(stage08, option, "Approved by operator.")

    def fake_stage_dir(stage: int) -> Path:
        path = tmp_path / f"stage_{stage:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def fake_run_import_step(step_number, groups, *, context=None):
        _ = step_number, groups, context
        shutil.rmtree(stage08)
        stage08.mkdir(parents=True, exist_ok=True)
        return {"status": "success"}

    def fake_apply_outputs(step_number, report):
        _ = report
        confirmation = json.loads(
            (fake_stage_dir(step_number) / "style_confirmation.json").read_text(
                encoding="utf-8"
            )
        )
        return {
            "status": "success",
            "confirmation_status": confirmation["status"],
            "selected_style_id": confirmation["selected_style_id"],
        }

    monkeypatch.setattr(confirmation_plugin, "stage_dir", fake_stage_dir)
    monkeypatch.setattr(confirmation_plugin, "run_import_step", fake_run_import_step)
    monkeypatch.setattr(
        confirmation_plugin, "apply_development_plan_outputs", fake_apply_outputs
    )

    result = confirmation_plugin.Plugin().execute(StageContext(stage_id="08"))

    assert result.status == "success"
    assert result.outputs["selected_style_id"] == "STYLE-04"
