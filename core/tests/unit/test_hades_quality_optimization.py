from __future__ import annotations

import json
from pathlib import Path

from core.engines import generation
from core.io import write_json


TEMPLATE_PATH = Path(
    "knowledge/design_data/project_templates/builtin_indie_hades_l5_partial.json"
)
TOTAL_HADES_TEMPLATE_NODES = 103


def test_hades_partial_template_exceeds_phase2_entity_coverage_target() -> None:
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    covered = {
        node_id: node["designEntities"]
        for node_id, node in template["projectState"]["nodes"].items()
        if node.get("designEntities")
    }

    assert len(covered) == TOTAL_HADES_TEMPLATE_NODES
    for entities in covered.values():
        for entity in entities:
            assert entity.get("supplement_basis"), entity["id"]


def test_clean_task_title_removes_repeated_hades_template_note() -> None:
    raw = (
        "资源：Hades 范本反推：基于公开信息与设计分析反推，非官方配置；"
        "部分 L4 为基于同品类结构的合理推断。"
    )

    assert generation._clean_task_title(raw, fallback="fallback") == "fallback"
    assert (
        generation._clean_task_title("Hades 范本反推：", fallback="fallback")
        == "fallback"
    )


def test_stage7_tasks_include_clean_titles_category_and_priority(
    tmp_path, monkeypatch
) -> None:
    def fake_stage_dir(stage: int) -> Path:
        return tmp_path / f"stage_{stage:02d}"

    monkeypatch.setattr(generation, "stage_dir", fake_stage_dir)
    stage3 = fake_stage_dir(3)
    write_json(
        stage3 / "program_requirements_contract.json",
        {
            "requirements": [
                {
                    "id": "REQ-001",
                    "requirement": (
                        "实现并验证 Hades 范本反推：基于公开信息与设计分析反推，"
                        "非官方配置；部分 L4 为基于同品类结构的合理推断。战斗输入"
                    ),
                    "phase": "core_playable",
                    "source_refs": ["design.md:1"],
                    "acceptance": "验证 combat 输入响应。",
                }
            ]
        },
    )
    write_json(
        stage3 / "program_structure_spec.json",
        {
            "allowed_roots": ["Assets/Scripts/", "Assets/Tests/"],
            "system_path_map": [
                {
                    "requirement_id": "REQ-001",
                    "target_path": "Assets/Scripts/Core/",
                    "test_path": "Assets/Tests/EditMode/Core/",
                }
            ],
        },
    )

    out_dir = tmp_path / "stage_07"
    generation._stage7_outputs({}, out_dir)
    plan = json.loads(
        (out_dir / "program_task_breakdown.json").read_text(encoding="utf-8")
    )
    task = plan["tasks"][0]
    config_schema = json.loads(
        (out_dir / "config_schema.json").read_text(encoding="utf-8")
    )

    assert "范本反推" not in task["title"]
    assert "基于公开信息" not in task["title"]
    assert task["category"] == "combat"
    assert task["priority"] == "P0"
    assert (out_dir / "TEMPLATE_NOTE.md").exists()
    assert "category" in config_schema["required_task_fields"]
    assert "priority" in config_schema["required_task_fields"]


def test_stage7_skips_documentation_requirements_and_ignores_schema_metadata(
    tmp_path, monkeypatch
) -> None:
    def fake_stage_dir(stage: int) -> Path:
        return tmp_path / f"stage_{stage:02d}"

    monkeypatch.setattr(generation, "stage_dir", fake_stage_dir)
    stage3 = fake_stage_dir(3)
    write_json(
        stage3 / "program_requirements_contract.json",
        {
            "requirements": [
                {
                    "id": "REQ-DOC",
                    "requirement": "实现 documentation_runtime_decision 的文档治理输出。",
                    "phase": "core_playable",
                    "source_refs": ["design.md:1"],
                    "acceptance": "文档节点仅记录治理决策。",
                    "dependencies": [],
                },
                {
                    "id": "REQ-SKILL",
                    "requirement": "实现 L5实体 Varatha 的武器攻击行为。",
                    "phase": "core_playable",
                    "source_refs": ["design.md:2"],
                    "acceptance": "kind=skill；schema=skill_card_v1；effect=attack_dash",
                    "dependencies": ["combat_weapon_decision"],
                },
            ]
        },
    )
    write_json(stage3 / "program_structure_spec.json", {"system_path_map": []})

    out_dir = tmp_path / "stage_07"
    generation._stage7_outputs({}, out_dir)
    plan = json.loads(
        (out_dir / "program_task_breakdown.json").read_text(encoding="utf-8")
    )

    assert len(plan["tasks"]) == 1
    assert plan["tasks"][0]["requirement_id"] == "REQ-SKILL"
    assert plan["tasks"][0]["category"] == "combat"


def test_stage8_tasks_carry_asset_classification_and_clean_titles(
    tmp_path, monkeypatch
) -> None:
    def fake_stage_dir(stage: int) -> Path:
        return tmp_path / f"stage_{stage:02d}"

    monkeypatch.setattr(generation, "stage_dir", fake_stage_dir)
    write_json(
        fake_stage_dir(4) / "asset_registry.json",
        {
            "assets": [
                {
                    "asset_id": "ASSET-001",
                    "name": (
                        "资源：Hades 范本反推：基于公开信息与设计分析反推，"
                        "非官方配置；部分 L4 为基于同品类结构的合理推断。"
                    ),
                    "asset_type": "effect",
                    "priority": "P1",
                    "complexity": "m",
                    "required_for_phase": "core_playable",
                    "source": "design.md:2",
                }
            ]
        },
    )

    out_dir = tmp_path / "stage_08"
    generation._stage8_outputs({}, out_dir)
    plan = json.loads((out_dir / "art_task_breakdown.json").read_text(encoding="utf-8"))
    task = plan["tasks"][0]

    assert task["title"] == "effect asset ASSET-001"
    assert task["asset_type"] == "effect"
    assert task["category"] == "vfx"
    assert task["priority"] == "P1"
    assert task["complexity"] == "m"
    assert (out_dir / "TEMPLATE_NOTE.md").exists()


def test_stage4_asset_items_detect_english_environment_entities() -> None:
    parsed = {
        "selections": [
            generation.Selection(
                index=1,
                layer_number=1,
                layer_title="内容对象",
                layer_status="已提交",
                item_type="内容",
                option="underworld_room",
                purpose="Room layout, dungeon floor, chamber variant and tileset rules.",
                source_ref="design.md:1",
                source_line=1,
            ),
            generation.Selection(
                index=2,
                layer_number=1,
                layer_title="内容对象",
                layer_status="已提交",
                item_type="内容",
                option="boon_choice_ui",
                purpose="HUD choice panel for rewards.",
                source_ref="design.md:2",
                source_line=2,
            ),
        ]
    }

    assets = generation._asset_items(parsed)

    assert [asset["asset_type"] for asset in assets] == ["environment", "ui"]
    assert assets[0]["name"] == "内容：underworld_room"


def test_stage4_uses_stage2_supplemented_entities_for_assets(
    tmp_path, monkeypatch
) -> None:
    def fake_stage_dir(stage: int) -> Path:
        path = tmp_path / f"stage_{stage:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(generation, "stage_dir", fake_stage_dir)
    write_json(
        fake_stage_dir(2) / "entity_coverage_report.json",
        {
            "entities": [
                {
                    "entity_id": "ENT-001",
                    "label": "Asphodel Chamber",
                    "kind": "room",
                    "schema": "room.v1",
                    "node_id": "level_space_decision",
                    "source": "ai_supplement_missing_node_fallback",
                }
            ]
        },
    )

    out_dir = tmp_path / "stage_04"
    generation._stage4_outputs(
        {"source": "design.md", "raw_text": "Hades roguelike", "selections": []},
        out_dir,
    )
    registry = json.loads((out_dir / "asset_registry.json").read_text(encoding="utf-8"))
    environments = [
        asset for asset in registry["assets"] if asset["asset_type"] == "environment"
    ]

    assert len(environments) == 2
    assert {asset["source_node_id"] for asset in environments} == {
        "level_space_decision"
    }


def test_image_generation_manifest_is_skipped_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AUTODESIGNMAKER_ENABLE_IMAGE_GENERATION", raising=False)

    manifest = generation._write_generated_images_manifest(
        tmp_path,
        [
            {
                "task_id": "ART-001",
                "asset_id": "ASSET-001",
                "title": "Styx sword slash VFX",
                "asset_type": "effect",
            }
        ],
        stage=11,
    )
    saved = json.loads(
        (tmp_path / "generated_images_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["enabled"] is False
    assert manifest["status"] == "skipped"
    assert saved["task_count"] == 1
    assert saved["generated_count"] == 0
