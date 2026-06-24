from __future__ import annotations

import json
from pathlib import Path

from core.engines import generation
from pipeline.step_02_design_review_freeze.helpers import (
    _prioritize_unmapped_nodes,
    supplement_trigger_reason,
)
from pipeline.step_02_design_review_freeze.supplement import EntitySupplementAdapter
from pipeline.step_03_program_requirements.binding import RequirementBindingEngine


def _selection(
    index: int,
    item_type: str,
    option: str,
    purpose: str = "",
    dependencies: list[str] | None = None,
    *,
    layer_title: str = "系统图",
) -> generation.Selection:
    return generation.Selection(
        index=index,
        layer_number=1,
        layer_title=layer_title,
        layer_status="已提交",
        item_type=item_type,
        option=option,
        purpose=purpose,
        dependencies=dependencies or [],
        source_ref=f"design.md:{index}",
        source_line=index,
    )


def test_stage2_design_freeze_contract_contains_entities_and_systems(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(generation, "_stage2_supplement_adapter", lambda _out_dir: None)
    parsed = {
        "source": "design.md",
        "raw_text": "Hades combat loop",
        "source_sha256": "same",
        "design_summary": {"node_count": 3},
        "selections": [
            _selection(1, "系统", "Combat System", "核心战斗系统。"),
            _selection(
                2,
                "L5实体",
                "Combat Runtime",
                "kind=system；schema=system.v1",
                ["SEL-001"],
            ),
            _selection(
                3,
                "L5实体",
                "Stygian Blade",
                "kind=weapon；schema=weapon.v1",
                ["SEL-001"],
            ),
        ],
    }

    generation._stage2_outputs(parsed, tmp_path)
    contract = json.loads(
        (tmp_path / "design_freeze_contract.json").read_text(encoding="utf-8")
    )

    assert len(contract["entities"]) == 2
    assert contract["entity_stats"]["total_count"] == 2
    assert contract["systems"]
    assert contract["systems"][0]["related_entities"] == ["ENT-002"]


def test_requirement_binding_engine_uses_semantic_and_default_fallback() -> None:
    engine = RequirementBindingEngine(
        {
            "systems": [
                {
                    "system_id": "combat_system",
                    "system_name": "Combat System",
                    "node_id": "combat_node",
                    "dependencies": [],
                    "related_entities": [],
                },
                {
                    "system_id": "ui_system",
                    "system_name": "UI System",
                    "node_id": "ui_node",
                    "dependencies": [],
                    "related_entities": [],
                },
            ]
        }
    )

    semantic = engine.bind_requirement(
        {"requirement": "Calculate weapon damage and attack hit results."}
    )
    default = engine.bind_requirement({"requirement": "Unknown behavior contract."})

    assert semantic["system_ids"] == ["combat_system"]
    assert default["system_ids"]


def test_stage3_outputs_auto_bind_unbound_requirements(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_stage_dir(stage: int) -> Path:
        path = tmp_path / f"stage_{stage:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(generation, "stage_dir", fake_stage_dir)
    monkeypatch.setattr(
        generation,
        "run_actual_development_preflight",
        lambda *_args, **_kwargs: {"status": "passed", "settings": {}},
    )
    generation.write_json(
        fake_stage_dir(2) / "design_freeze_contract.json",
        {
            "entities": [],
            "systems": [
                {
                    "system_id": "combat_system",
                    "system_name": "Combat System",
                    "node_id": "combat_node",
                    "dependencies": [],
                    "related_entities": [],
                }
            ],
        },
    )
    parsed = {
        "source": "design.md",
        "raw_text": "Hades combat loop",
        "source_sha256": "same",
        "selections": [
            _selection(1, "玩法系统", "Weapon damage", "Attack and hit validation.")
        ],
    }

    generation._stage3_outputs(parsed, tmp_path)
    contract = json.loads(
        (tmp_path / "program_requirements_contract.json").read_text(encoding="utf-8")
    )

    assert contract["binding_stats"]["binding_rate"] == 1.0
    assert all(req["system_ids"] for req in contract["requirements"])


def test_supplement_trigger_and_unmapped_priority() -> None:
    should_run, reason = supplement_trigger_reason(
        [{"kind": "weapon", "status": "precise"}],
        0.38,
        "codex",
    )
    adapter_should_run, adapter_reason = EntitySupplementAdapter(
        adapter_name="codex"
    ).should_supplement(
        {
            "entity_coverage_rate": 0.9,
            "missing_entities": [{"node_id": f"UNMAPPED-NODE-{i}"} for i in range(31)],
            "entities": [{"kind": "system"}],
        }
    )
    prioritized = _prioritize_unmapped_nodes(
        [
            {"node_id": "content_node"},
            {"node_id": "combat_system"},
            {"node_id": "ability_node"},
        ]
    )

    assert should_run is True
    assert "coverage_rate" in reason
    assert adapter_should_run is True
    assert "unmapped_nodes" in adapter_reason
    assert [item["node_id"] for item in prioritized] == [
        "combat_system",
        "ability_node",
        "content_node",
    ]
