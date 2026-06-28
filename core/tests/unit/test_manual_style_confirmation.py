from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

from core.engines import generation
from core.io import write_json
from core.context import StageContext
from core.ui.style_confirmation_dialog import write_style_confirmation
from core.ui.pipeline_panel import _cleanup_unselected_style_images
from core.ui.style_prompt_editor import (
    StylePromptEditorDialog,
    parse_style_prompt_response,
    write_style_prompt_override,
)
from pipeline.step_07_art_style_generation import plugin as style_plugin


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
    stale_image = out_dir / "generated_images" / "STYLE-99-stale.png"
    stale_image.parent.mkdir(parents=True)
    stale_image.write_bytes(b"stale")
    result = generation._stage7_art_style_generation_outputs(
        {"project_name": "Style Test"}, out_dir
    )

    style_options = json.loads((out_dir / "style_options.json").read_text("utf-8"))
    first_image = out_dir / "generated_images" / "STYLE-01-readable_production.png"

    assert result["style_option_count"] == 3
    assert style_options["option_count"] == 3
    assert style_options["options"][0]["title"] == "清晰量产风"
    assert first_image.read_bytes().startswith(b"\x89PNG")
    assert not stale_image.exists()


def test_style_prompt_editor_parses_refined_prompt_block() -> None:
    response = """已改成更暗黑的低饱和风格。

PROMPT_START
STYLE-01-readable_production: dark gothic game art style board, readable silhouettes
- STYLE-02-painterly_concept: painterly horror key art, dramatic rim light
STYLE-99-extra: should be ignored
PROMPT_END
"""

    explanation, prompts = parse_style_prompt_response(
        response, {"STYLE-01-readable_production", "STYLE-02-painterly_concept"}
    )

    assert explanation == "已改成更暗黑的低饱和风格。"
    assert prompts == {
        "STYLE-01-readable_production": "dark gothic game art style board, readable silhouettes",
        "STYLE-02-painterly_concept": "painterly horror key art, dramatic rim light",
    }


def test_style_prompt_editor_writes_prompt_override(tmp_path) -> None:
    options = [
        {"style_id": "STYLE-01", "prompt": "original 1", "palette": ["#111111"] * 3},
        {"style_id": "STYLE-02", "prompt": "original 2", "palette": ["#222222"] * 3},
    ]

    path = write_style_prompt_override(
        tmp_path,
        options,
        {"STYLE-02": "refined 2"},
        2,
    )
    payload = json.loads(path.read_text("utf-8"))

    assert payload["source"] == "style_prompt_editor"
    assert payload["count"] == 2
    assert payload["options"][0]["prompt"] == "original 1"
    assert payload["options"][0]["prompt_refined"] is False
    assert payload["options"][1]["prompt"] == "refined 2"
    assert payload["options"][1]["prompt_refined"] is True


def test_style_prompt_editor_initial_greeting_enters_history() -> None:
    dialog = object.__new__(StylePromptEditorDialog)
    dialog.options = [{"style_id": "STYLE-01", "title": "Readable", "prompt": "prompt"}]
    dialog._history = []
    appended: list[tuple[str, str]] = []
    dialog._append_message = lambda role, content: appended.append((role, content))

    StylePromptEditorDialog._send_initial_greeting(dialog)

    assert appended[0][0] == "assistant"
    assert dialog._history == [
        {"role": "assistant", "content": appended[0][1]},
    ]


def test_style_prompt_editor_ignores_ai_callbacks_after_cancel() -> None:
    dialog = object.__new__(StylePromptEditorDialog)
    dialog._cancelled = True

    StylePromptEditorDialog._handle_ai_response(
        dialog,
        "explanation\nPROMPT_START\nSTYLE-01: prompt\nPROMPT_END",
    )
    StylePromptEditorDialog._handle_ai_error(dialog, RuntimeError("boom"))
    StylePromptEditorDialog._schedule_ui(
        dialog,
        lambda: (_ for _ in ()).throw(AssertionError("should not run")),
    )


def test_step07_consumes_prompt_override(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    monkeypatch.delenv("AUTODESIGNMAKER_ENABLE_IMAGE_GENERATION", raising=False)
    monkeypatch.setenv("AUTODESIGNMAKER_SKIP_ALL_GATES", "1")
    out_dir = tmp_path / "stage_07"
    options = [
        {
            "style_id": "STYLE-01-readable_production",
            "title": "清晰量产风",
            "description": "Readable",
            "prompt": "original prompt 1",
            "palette": ["#111111", "#222222", "#333333"],
        },
        {
            "style_id": "STYLE-02-painterly_concept",
            "title": "概念绘画风",
            "description": "Painterly",
            "prompt": "original prompt 2",
            "palette": ["#444444", "#555555", "#666666"],
        },
    ]
    write_style_prompt_override(
        out_dir,
        options,
        {"STYLE-01-readable_production": "refined dark prompt"},
        1,
    )

    result = generation._stage7_art_style_generation_outputs(
        {"project_name": "Override Test"}, out_dir
    )
    style_options = json.loads((out_dir / "style_options.json").read_text("utf-8"))
    generation_log = json.loads((out_dir / "generation_log.json").read_text("utf-8"))

    assert result["prompt_override_used"] is True
    assert style_options["prompt_override_used"] is True
    assert style_options["option_count"] == 1
    assert style_options["options"][0]["prompt"] == "refined dark prompt"
    assert generation_log["generated_count"] == 1
    assert not (out_dir / "prompt_override.json").exists()


def test_step07_confirm_cleanup_keeps_only_selected_image(tmp_path) -> None:
    img_dir = tmp_path / "generated_images"
    img_dir.mkdir(parents=True)
    selected = img_dir / "STYLE-02.png"
    stale_a = img_dir / "STYLE-01.png"
    stale_b = img_dir / "STYLE-03.png"
    selected.write_bytes(b"selected")
    stale_a.write_bytes(b"stale")
    stale_b.write_bytes(b"stale")

    removed = _cleanup_unselected_style_images(tmp_path, "STYLE-02", str(selected))

    assert removed == 2
    assert selected.exists()
    assert not stale_a.exists()
    assert not stale_b.exists()


def test_step07_confirm_cleanup_preserves_selected_unique_fallback(
    tmp_path, monkeypatch
) -> None:
    from core.ui import pipeline_panel

    monkeypatch.setattr(pipeline_panel, "PROJECT_ROOT", tmp_path)
    img_dir = tmp_path / "generated_images"
    img_dir.mkdir(parents=True)
    selected_unique = img_dir / "STYLE-02_123.png"
    stale = img_dir / "STYLE-01.png"
    selected_unique.write_bytes(b"selected")
    stale.write_bytes(b"stale")

    removed = pipeline_panel._cleanup_unselected_style_images(
        tmp_path,
        "STYLE-02",
        "generated_images/STYLE-02_123.png",
    )

    assert removed == 1
    assert selected_unique.exists()
    assert not stale.exists()


def test_step07_image_generation_workers_allows_parallel(monkeypatch) -> None:
    monkeypatch.setattr(generation, "get_config", lambda key, default=None: 5)

    assert generation._style_image_generation_workers(5) == 5
    assert generation._style_image_generation_workers(7) == 5
    assert generation._style_image_generation_workers(0) == 1


def test_step07_generates_style_images_in_parallel(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(generation, "_style_image_generation_enabled", lambda: True)
    monkeypatch.setattr(generation, "_create_image_generator", lambda: object())
    barrier = threading.Barrier(3, timeout=2)
    lock = threading.Lock()
    active = {"count": 0, "max": 0}

    def fake_run(generator, prompt, generated_dir, image_path):
        _ = generator, prompt, generated_dir
        with lock:
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
        try:
            barrier.wait()
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            return {"status": "success", "result": "ok", "image_path": str(image_path)}
        finally:
            with lock:
                active["count"] -= 1

    monkeypatch.setattr(generation, "_run_style_image_generation", fake_run)
    options = [
        {
            "style_id": f"STYLE-{index:02d}",
            "prompt": f"prompt {index}",
            "palette": ("#111111", "#222222", "#333333"),
        }
        for index in range(1, 4)
    ]

    manifest = generation._generate_style_option_images(
        tmp_path,
        {"project_name": "Parallel Test"},
        options,
    )

    assert active["max"] > 1
    assert manifest["enabled"] is True
    assert [record["status"] for record in manifest["records"]] == ["success"] * 3


def test_step07_places_image_with_copy_fallback(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "target.png"
    source.write_bytes(b"new")
    target.write_bytes(b"old")

    def fake_replace(self, target_path):
        _ = self, target_path
        raise OSError("locked")

    monkeypatch.setattr(Path, "replace", fake_replace)

    final_path = generation._place_style_image(source, target)

    assert final_path == target
    assert target.read_bytes() == b"new"
    assert not source.exists()


def test_step07_places_image_with_unique_fallback_when_target_locked(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "target.png"
    source.write_bytes(b"new")
    target.write_bytes(b"old")
    real_copy2 = generation.shutil.copy2

    def fake_replace(self, target_path):
        _ = self, target_path
        raise OSError("locked")

    def fake_copy2(source_path, target_path, *args, **kwargs):
        if Path(target_path) == target:
            raise OSError("target locked")
        return real_copy2(source_path, target_path, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fake_replace)
    monkeypatch.setattr(generation.shutil, "copy2", fake_copy2)
    monkeypatch.setattr(generation.time, "time_ns", lambda: 123456)

    final_path = generation._place_style_image(source, target)

    assert final_path == tmp_path / "target_123456.png"
    assert final_path.read_bytes() == b"new"
    assert target.read_bytes() == b"old"
    assert not source.exists()


def test_step07_place_image_logs_cleanup_failure(
    tmp_path, monkeypatch, caplog
) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "target.png"
    source.write_bytes(b"new")
    original_unlink = Path.unlink

    def fake_replace(self, target_path):
        _ = self, target_path
        raise OSError("locked")

    def fake_unlink(self, *args, **kwargs):
        if self == source:
            raise PermissionError("source locked")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fake_replace)
    monkeypatch.setattr(Path, "unlink", fake_unlink)
    caplog.set_level("WARNING", logger="core.engines.generation")

    final_path = generation._place_style_image(source, target)

    assert final_path == target
    assert target.read_bytes() == b"new"
    assert source.exists()
    assert "Failed to remove temporary style image" in caplog.text


def test_step07_saved_path_result_preserves_inner_backticks(tmp_path) -> None:
    image_path = tmp_path / "with`tick.png"
    image_path.write_bytes(b"png")

    result = generation._saved_image_path_from_result(f"saved: `{image_path}`")

    assert result == image_path


def test_step07_new_png_filter_ignores_stale_concurrent_file(
    tmp_path, monkeypatch
) -> None:
    fresh = tmp_path / "fresh.png"
    stale = tmp_path / "stale.png"
    fresh.write_bytes(b"fresh")
    stale.write_bytes(b"stale")
    old_time = 1_000_000_000
    new_time = 10_000_000_000
    monkeypatch.setattr(generation.time, "time_ns", lambda: new_time)
    import os

    os.utime(stale, ns=(old_time, old_time))
    os.utime(fresh, ns=(new_time, new_time))

    paths = generation._new_style_pngs(tmp_path, {}, generation.time.time_ns())

    assert paths == [fresh]


def test_step07_new_png_filter_skips_deleted_file(tmp_path, monkeypatch) -> None:
    keep = tmp_path / "keep.png"
    deleted = tmp_path / "deleted.png"
    keep.write_bytes(b"keep")
    deleted.write_bytes(b"deleted")
    original_is_file = Path.is_file
    original_stat = Path.stat

    def fake_is_file(self):
        if self == deleted:
            return True
        return original_is_file(self)

    def fake_stat(self, *args, **kwargs):
        if self == deleted:
            raise FileNotFoundError(str(self))
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "is_file", fake_is_file)
    monkeypatch.setattr(Path, "stat", fake_stat)

    paths = generation._new_style_pngs(tmp_path, {}, 0)

    assert paths == [keep]


def test_step07_saved_path_handles_backtick_before_extension(tmp_path) -> None:
    image_path = tmp_path / "image`.png"
    image_path.write_bytes(b"png")

    result = generation._saved_image_path_from_result(f"saved: `{image_path}`")

    assert result == image_path


def test_step07_prompt_uses_short_asset_labels_and_source_title(
    tmp_path, monkeypatch
) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    long_asset_name = (
        "product_vision_decision：Axiom Verge 2D L5 reference positions "
        "项目愿景决策 around glitch tools, ability-gated exploration, boss precision, "
        "alien world mystery, and high-density system discovery."
    )
    write_json(
        tmp_path / "stage_04" / "asset_registry.json",
        {
            "assets": [
                {
                    "asset_id": "ASSET-001",
                    "asset_type": "ui",
                    "name": long_asset_name,
                    "source": "design.md:1",
                },
                {
                    "asset_id": "ASSET-002",
                    "asset_type": "ui",
                    "name": long_asset_name,
                    "source": "design.md:2",
                },
            ]
        },
    )
    monkeypatch.setattr(generation, "get_config", lambda key, default=None: 3)
    monkeypatch.delenv("AUTODESIGNMAKER_ENABLE_IMAGE_GENERATION", raising=False)

    out_dir = tmp_path / "stage_07"
    generation._stage7_art_style_generation_outputs(
        {"raw_text": "# ???Axiom Verge — Full Design Specification\n\nbody"},
        out_dir,
    )

    style_options = json.loads((out_dir / "style_options.json").read_text("utf-8"))
    generation_log = json.loads((out_dir / "generation_log.json").read_text("utf-8"))
    prompt = style_options["options"][0]["prompt"]
    representative = prompt.split("Representative assets: ", 1)[1].splitlines()[0]

    assert style_options["project"] == "Axiom Verge"
    assert generation_log["project"] == "Axiom Verge"
    assert "Project: Axiom Verge" in prompt
    assert len(representative) <= 80
    assert representative == "ui"
    assert "glitch tools" not in representative


def test_step07_waits_without_confirmation(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    write_json(
        tmp_path / "stage_07" / "style_options.json",
        {
            "options": [
                {
                    "style_id": "STYLE-01",
                    "title": "Readable",
                    "image_path": "drafts/example.png",
                    "score": 80,
                },
                {
                    "style_id": "STYLE-02",
                    "title": "Painterly",
                    "image_path": "drafts/example-2.png",
                    "score": 95,
                    "recommended": True,
                }
            ]
        },
    )
    monkeypatch.setattr(generation, "get_config", lambda key, default=None: True)
    monkeypatch.delenv("AUTODESIGNMAKER_SKIP_ALL_GATES", raising=False)
    monkeypatch.delenv("AUTODESIGNMAKER_SKIP_GATES", raising=False)

    result = generation._style_confirmation_outputs({}, tmp_path / "stage_07")

    assert result["status"] == "waiting_confirmation"
    assert result["confirmation_ui"] == "style_confirmation_dialog"
    assert (tmp_path / "stage_07" / "style_confirmation_pending.json").exists()


def test_step07_auto_pass_when_gate_disabled(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    write_json(
        tmp_path / "stage_07" / "style_options.json",
        {
            "options": [
                {
                    "style_id": "STYLE-01",
                    "title": "Readable",
                    "image_path": "drafts/example.png",
                    "score": 80,
                },
                {
                    "style_id": "STYLE-02",
                    "title": "Painterly",
                    "image_path": "drafts/example-2.png",
                    "score": 95,
                    "recommended": True,
                }
            ]
        },
    )
    monkeypatch.setenv("AUTODESIGNMAKER_SKIP_ALL_GATES", "1")

    result = generation._style_confirmation_outputs({}, tmp_path / "stage_07")
    confirmation = json.loads(
        (tmp_path / "stage_07" / "style_confirmation.json").read_text("utf-8")
    )

    assert result["confirmation_status"] == "approved"
    assert confirmation["mode"] == "auto"
    assert confirmation["selected_style_id"] == "STYLE-02"


def test_step07_legacy_skip_gate_08_auto_passes(tmp_path, monkeypatch) -> None:
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
    monkeypatch.setenv("AUTODESIGNMAKER_SKIP_GATES", "08")

    result = generation._style_confirmation_outputs({}, tmp_path / "stage_07")

    assert result["confirmation_status"] == "approved"
    assert result["selected_style_id"] == "STYLE-01"


def test_step07_uses_existing_confirmation(tmp_path, monkeypatch) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    option = {"style_id": "STYLE-02", "title": "Painterly", "image_path": "x.png"}
    write_json(tmp_path / "stage_07" / "style_options.json", {"options": [option]})
    write_style_confirmation(tmp_path / "stage_07", option, "Use warmer lighting.")
    monkeypatch.setattr(generation, "get_config", lambda key, default=None: True)

    result = generation._style_confirmation_outputs({}, tmp_path / "stage_07")

    assert result["confirmation_status"] == "approved"
    assert result["selected_style_id"] == "STYLE-02"


def test_style_confirmation_writer_records_selection(tmp_path) -> None:
    option = {"style_id": "STYLE-03", "title": "Arcade", "image_path": "img.png"}

    path = write_style_confirmation(tmp_path, option, "Keep high contrast.")
    payload = json.loads(path.read_text("utf-8"))

    assert payload["status"] == "approved"
    assert payload["selected_style_id"] == "STYLE-03"
    assert payload["notes"] == "Keep high contrast."


def test_pipeline_panel_locates_style_options(tmp_path, monkeypatch) -> None:
    from core.ui import pipeline_panel

    write_json(
        tmp_path / "stage_07" / "style_options.json",
        {"options": [{"style_id": "STYLE-05", "title": "Readable"}]},
    )
    monkeypatch.setattr(pipeline_panel, "ARTIFACTS_DIR", tmp_path)

    found = pipeline_panel.PipelinePanel._locate_style_options_json(object(), 7)

    assert found is not None
    assert found["options"][0]["style_id"] == "STYLE-05"


def test_pipeline_panel_loads_approved_style_confirmation(tmp_path, monkeypatch) -> None:
    from core.ui import pipeline_panel

    stage07 = tmp_path / "stage_07"
    option = {"style_id": "STYLE-01", "title": "清晰量产风", "image_path": "style.png"}
    write_style_confirmation(stage07, option, "Approved.")
    monkeypatch.setattr(pipeline_panel, "ARTIFACTS_DIR", tmp_path)

    confirmation = pipeline_panel.PipelinePanel._load_approved_style_confirmation(object())

    assert confirmation is not None
    assert confirmation["selected_style_id"] == "STYLE-01"
    assert confirmation["selected_title"] == "清晰量产风"


def test_step07_plugin_preserves_manual_confirmation_across_import_reset(
    tmp_path, monkeypatch
) -> None:
    stage07 = tmp_path / "stage_07"
    option = {"style_id": "STYLE-04", "title": "Ink", "image_path": "ink.png"}
    write_style_confirmation(stage07, option, "Approved by operator.")

    def fake_stage_dir(stage: int) -> Path:
        path = tmp_path / f"stage_{stage:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def fake_run_import_step(step_number, groups, *, context=None):
        _ = step_number, groups, context
        shutil.rmtree(stage07)
        stage07.mkdir(parents=True, exist_ok=True)
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

    monkeypatch.setattr(style_plugin, "stage_dir", fake_stage_dir)
    monkeypatch.setattr(style_plugin, "run_import_step", fake_run_import_step)
    monkeypatch.setattr(style_plugin, "apply_development_plan_outputs", fake_apply_outputs)

    result = style_plugin.Plugin().execute(StageContext(stage_id="07"))

    assert result.status == "success"
    assert result.outputs["selected_style_id"] == "STYLE-04"


def test_step08_to_step11_dispatch_uses_matching_output_functions(
    tmp_path, monkeypatch
) -> None:
    _patch_stage_dir(monkeypatch, tmp_path)
    called: list[tuple[int, str]] = []

    def fake_load_design(step_number: int) -> dict:
        return {"step_number": step_number}

    def fake_update_stage_report(step_number: int, out_dir: Path, result: dict) -> dict:
        _ = step_number, out_dir, result
        return {"valid": True}

    def fake_refresh_indexes(step_number: int, out_dir: Path) -> None:
        _ = step_number, out_dir

    def make_output(expected_step: int):
        def fake_output(parsed: dict, out_dir: Path) -> dict:
            called.append((expected_step, out_dir.name))
            return {
                "content_exists": True,
                "blocking_issues": 0,
                "ai_review_status": "passed",
                "traceability_valid": True,
            }

        return fake_output

    monkeypatch.setattr(generation, "_load_design_for_stage", fake_load_design)
    monkeypatch.setattr(generation, "_update_stage_report", fake_update_stage_report)
    monkeypatch.setattr(generation, "_refresh_indexes", fake_refresh_indexes)
    for step_number in range(8, 12):
        monkeypatch.setattr(
            generation,
            f"_stage{step_number}_outputs",
            make_output(step_number),
        )

    for step_number in range(8, 12):
        generation.apply_development_plan_outputs(step_number, {})

    assert called == [
        (8, "stage_08"),
        (9, "stage_09"),
        (10, "stage_10"),
        (11, "stage_11"),
    ]
