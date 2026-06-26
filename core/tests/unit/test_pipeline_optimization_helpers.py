from __future__ import annotations

import json
import os
from types import SimpleNamespace

from core.design.export_adapter import (
    _design_markdown_from_project_state,
    _framework_markdown_from_project_state,
)
from core.source import finder
from pipeline.step_00_idea_intake.helpers import ConceptProcessor, QuestionEngine
from pipeline.step_01_gameplay_framework import helpers as step01_helpers
from pipeline.step_01_gameplay_framework.helpers import LoopExtractor, SystemDeducer
from pipeline.step_02_design_review_freeze.helpers import (
    EntityValidator,
    GraphGenerator,
    PhaseClassifier,
)
from pipeline.step_03_program_requirements.helpers import (
    EntityToRequirementConverter,
    SystemBinder,
    build_requirement_quality_report,
)
from pipeline.step_04_art_requirements import helpers as step04_helpers
from pipeline.step_04_art_requirements.helpers import (
    EntityToAssetConverter,
    MarketResearchSkill,
)
from pipeline.step_05_program_review.helpers import IntelligentReviewer
from tools.validators.pipeline_quality import check_plan_002, collect_quality_metrics


def _selection(
    index: int,
    item_type: str,
    option: str,
    purpose: str = "",
    dependencies: list[str] | None = None,
    layer_title: str = "测试层",
):
    return SimpleNamespace(
        index=index,
        id=f"SEL-{index:03d}",
        item_type=item_type,
        option=option,
        label=f"{item_type}：{option}",
        purpose=purpose,
        dependencies=dependencies or [],
        unlocks=[],
        layer_title=layer_title,
        source_ref=f"test.md:{index}",
    )


def test_design_markdown_exports_l5_entities_as_parseable_items():
    markdown = _design_markdown_from_project_state(
        {
            "projectName": "Test Project",
            "gameplaySystems": {},
            "nodes": {
                "combat_node": {
                    "decisionState": "completed",
                    "designNote": "Combat node",
                    "designEntities": [
                        {
                            "kind": "weapon",
                            "schema": "weapon.v1",
                            "id": "sword",
                            "label": "Stygian Blade",
                            "mapping": {"attack": "slash"},
                        }
                    ],
                }
            },
        }
    )

    assert "## Layer 5 L5实体" in markdown
    assert "- L5实体: Stygian Blade (sword)" in markdown
    assert "依赖：combat_node" in markdown


def test_framework_export_tolerates_missing_core_loops():
    markdown = _framework_markdown_from_project_state(
        {
            "projectName": "No Loop Project",
            "gameplaySystems": {
                "selected": ["combat"],
                "weights": {"combat": {"weight": 80}},
            },
        }
    )

    assert "No Loop Project" in markdown
    assert "system_layer" in markdown


def test_step00_question_engine_reports_coverage():
    parsed = {
        "source": "test.md",
        "raw_text": "Roguelike action game for PC with combat loop and rewards.",
        "selections": [
            _selection(1, "项目定位", "Roguelike action"),
            _selection(2, "平台", "PC"),
            _selection(3, "核心循环", "进入房间 -> 战斗 -> 奖励 -> 成长"),
        ],
    }

    profile = ConceptProcessor().build_profile(parsed)
    report = QuestionEngine().evaluate(parsed)

    assert profile["core_loop"]["confidence"] == "explicit"
    assert "key_systems" in profile
    assert report["answered_questions"] >= 3
    assert report["coverage_rate"] > 0


def test_step00_uses_genre_inference_for_sparse_hades_concept():
    parsed = {
        "source": "concept.md",
        "raw_text": "Hades Design Concept",
        "selections": [_selection(1, "游戏类型", "Hades")],
    }

    report = QuestionEngine().evaluate(parsed)
    questions = {item["id"]: item for item in report["questions"]}

    assert report["coverage_rate"] >= 0.55
    assert questions["CQ-005"]["evidence"][0]["match"] == "genre_inference"


def test_step00_uses_genre_inference_for_new_step01_genres():
    cases = [
        ("strategy tactics game", "CQ-008", "strategy"),
        ("classic rpg adventure", "CQ-008", "rpg"),
        ("moba lane push game", "CQ-008", "moba"),
    ]

    for raw_text, question_id, expected_genre in cases:
        parsed = {
            "source": "concept.md",
            "raw_text": raw_text,
            "selections": [_selection(1, "游戏类型", raw_text)],
        }
        report = QuestionEngine().evaluate(parsed)
        questions = {item["id"]: item for item in report["questions"]}

        assert report["coverage_rate"] >= 0.55
        assert (
            questions[question_id]["evidence"][0]["source"]
            == f"genre_template:{expected_genre}"
        )


def test_step00_uses_genre_inference_for_broad_market_genres():
    cases = [
        ("Stardew Valley farming life sim", "farming_sim"),
        ("Slay the Spire deck card battler", "card_game"),
        ("Vampire Survivors bullet heaven", "bullet_heaven"),
        ("Subway Surfers hypercasual runner", "hypercasual"),
        ("Coin Master idle incremental", "idle"),
        ("Royal Match match-3", "match3"),
        ("Elden Ring souls-like", "souls_like"),
        ("God of War action adventure", "action_adventure"),
        ("Resident Evil survival horror", "survival_horror"),
        ("Borderlands looter shooter", "looter_shooter"),
        ("Apex Legends battle royale", "battle_royale"),
        ("Valorant hero shooter", "hero_shooter"),
        ("World of Warcraft MMORPG", "mmorpg"),
        ("Factorio factory automation", "factory_sim"),
        ("A Short Hike exploration sandbox", "exploration"),
        ("Dead Cells metroidvania", "metroidvania"),
        ("Brawl Stars brawler arena", "brawler"),
    ]

    for raw_text, expected_genre in cases:
        parsed = {
            "source": "concept.md",
            "raw_text": raw_text,
            "selections": [_selection(1, "游戏类型", raw_text)],
        }
        report = QuestionEngine().evaluate(parsed)
        questions = {item["id"]: item for item in report["questions"]}

        assert report["coverage_rate"] >= 0.55
        assert (
            questions["CQ-011"]["evidence"][0]["source"]
            == f"genre_template:{expected_genre}"
        )
        assert questions["CQ-011"]["evidence"][0]["match"] == "genre_inference"


def test_step00_roguelike_action_supplies_runtime_flow_evidence():
    parsed = {
        "source": "concept.md",
        "raw_text": "Hades roguelike action combat draft.",
        "selections": [],
    }

    report = QuestionEngine().evaluate(parsed)
    questions = {item["id"]: item for item in report["questions"]}

    assert questions["CQ-011"]["answered"] is True
    assert (
        questions["CQ-011"]["evidence"][0]["source"]
        == "genre_template:roguelike_action"
    )
    assert questions["CQ-011"]["evidence"][0]["match"] == "genre_inference"


def test_step00_cq013_cq014_match_common_project_fields():
    parsed = {
        "source": "concept.md",
        "raw_text": "",
        "selections": [
            _selection(1, "项目规模", "indie"),
            _selection(2, "平台范围", "multi_platform"),
            _selection(3, "社交模式", "community_driven"),
        ],
    }

    report = QuestionEngine().evaluate(parsed)
    questions = {item["id"]: item for item in report["questions"]}

    assert questions["CQ-013"]["answered"] is True
    assert questions["CQ-014"]["answered"] is True


def test_step01_extracts_fallback_loop_and_at_least_five_systems():
    parsed = {
        "source": "test.md",
        "raw_text": "Hades inspired roguelike combat",
        "selections": [],
    }
    loop = LoopExtractor().extract(parsed)
    systems = SystemDeducer().deduce(parsed, {"nodes": [], "edges": []})

    assert loop["loop"]
    assert loop["output_rate"] == 1.0
    assert systems["system_count"] >= 5
    assert systems["definition_rate"] >= 1.0


def test_step01_caps_deduced_system_count_at_eight():
    parsed = {"source": "test.md", "raw_text": "", "selections": []}
    graph = {
        "nodes": [
            {"id": f"SYS-{index:03d}", "name": f"System {index}", "source": "test"}
            for index in range(1, 13)
        ],
        "edges": [],
    }

    systems = SystemDeducer().deduce(parsed, graph)

    assert systems["system_count"] == 8


def test_step01_cleans_system_prefix_and_supports_strategy_template():
    parsed = {
        "source": "test.md",
        "raw_text": "strategy tactics game",
        "selections": [],
    }
    graph = {
        "nodes": [{"id": "strategy_node", "name": "system_layer：战术部署系统"}],
        "edges": [],
    }

    loop = LoopExtractor().extract(parsed)
    systems = SystemDeducer().deduce(parsed, graph)

    assert loop["template_key"] == "strategy"
    assert systems["systems"][0]["name"] == "战术部署系统"


def test_step01_blank_fps_and_puzzle_templates_have_playable_systems():
    cases = [
        ("competitive fps shooter", "fps", 4),
        ("minimal puzzle game", "puzzle", 3),
    ]

    for raw_text, template_key, minimum_system_count in cases:
        parsed = {"source": "test.md", "raw_text": raw_text, "selections": []}
        loop = LoopExtractor().extract(parsed)
        systems = SystemDeducer().deduce(parsed, {"nodes": [], "edges": []})

        assert loop["template_key"] == template_key
        assert loop["loop"]
        assert systems["system_count"] >= minimum_system_count


def test_step01_template_cache_refreshes_when_template_file_appears(
    tmp_path, monkeypatch
):
    template_path = tmp_path / "genre_templates.json"
    monkeypatch.setattr(step01_helpers, "GENRE_TEMPLATES_PATH", template_path)

    assert step01_helpers._load_templates() == {}

    template_path.write_text(
        json.dumps(
            {"generic": {"core_loop": ["缓存刷新"], "systems": []}}, ensure_ascii=False
        ),
        encoding="utf-8",
    )

    assert step01_helpers._load_templates()["generic"]["core_loop"] == ["缓存刷新"]


def test_step02_entity_validation_graph_and_phase_classification():
    parsed = {
        "source": "test.md",
        "design_summary": {"node_count": 1},
        "selections": [
            _selection(
                1,
                "L5实体",
                "Stygian Blade",
                "kind=weapon；schema=weapon.v1",
                ["combat_node"],
            ),
        ],
    }
    report = EntityValidator().validate(parsed)
    graph = GraphGenerator().generate({"nodes": [], "edges": []}, report)
    phases = PhaseClassifier().classify(report)

    assert report["entity_count"] == 1
    assert report["entity_coverage_rate"] == 1.0
    assert graph["cycle_free"]
    assert phases["phases"]["core_playable"]


def test_step02_build_system_decision_is_not_launch_ops():
    phases = PhaseClassifier().classify(
        {
            "entities": [
                {
                    "entity_id": "ENT-001",
                    "label": "build_system_decision",
                    "kind": "system",
                    "schema": "system.v1",
                    "node_id": "build_system_decision",
                }
            ]
        }
    )

    assert phases["phases"]["core_playable"]
    assert phases["phases"]["launch_ops"] == []


def test_step02_l5_entity_ids_are_continuous():
    parsed = {
        "source": "test.md",
        "design_summary": {"node_count": 2},
        "selections": [
            _selection(1, "项目定位", "Action roguelike"),
            _selection(
                2,
                "L5实体",
                "Stygian Blade",
                "kind=weapon；schema=weapon.v1",
                ["combat_node"],
            ),
            _selection(3, "玩法系统", "战斗系统"),
            _selection(
                4,
                "L5实体",
                "Dash Strike",
                "kind=ability；schema=ability.v1",
                ["ability_node"],
            ),
        ],
    }

    report = EntityValidator().validate(parsed)

    assert [entity["entity_id"] for entity in report["entities"]] == [
        "ENT-001",
        "ENT-002",
    ]


def test_step02_entity_coverage_uses_expected_design_node_count():
    parsed = {
        "source": "test.md",
        "design_summary": {"node_count": 4},
        "selections": [
            _selection(
                1,
                "L5实体",
                "Stygian Blade",
                "kind=weapon；schema=weapon.v1",
                ["combat_node"],
            ),
        ],
    }

    report = EntityValidator().validate(parsed)

    assert report["concrete_node_count"] == 4
    assert report["covered_concrete_nodes"] == 1
    assert report["entity_coverage_rate"] == 0.25
    assert len(report["missing_entities"]) == 3


def test_step02_missing_entities_use_real_expected_node_ids():
    parsed = {
        "source": "test.md",
        "design_summary": {"node_count": 3},
        "selections": [
            _selection(1, "combat_system_decision", "Combat", layer_title="设计决策"),
            _selection(2, "ability_choice_decision", "Ability", layer_title="设计决策"),
            _selection(3, "level_space_decision", "Level", layer_title="设计决策"),
            _selection(
                4,
                "L5实体",
                "Combat Runtime",
                "kind=system；schema=system.v1",
                ["combat_system_decision"],
                layer_title="L5实体",
            ),
        ],
    }

    report = EntityValidator().validate(parsed)

    missing_node_ids = {item["node_id"] for item in report["missing_entities"]}
    assert report["covered_concrete_nodes"] == 1
    assert report["entity_coverage_rate"] == round(1 / 3, 4)
    assert missing_node_ids == {"ability_choice_decision", "level_space_decision"}
    assert not any(node_id.startswith("UNMAPPED-NODE") for node_id in missing_node_ids)


def test_step02_entity_coverage_excludes_governance_nodes_from_denominator():
    parsed = {
        "source": "test.md",
        "design_summary": {"node_count": 4},
        "selections": [
            _selection(1, "商业模式", "buyout", layer_title="项目愿景"),
            _selection(2, "运营模式", "offline_single_release", layer_title="项目愿景"),
            _selection(3, "combat_system_decision", "Combat", layer_title="设计决策"),
            _selection(
                4, "documentation_core_doc_decision", "Docs", layer_title="设计决策"
            ),
            _selection(
                5, "launch_store_page_decision", "Launch", layer_title="设计决策"
            ),
            _selection(
                6,
                "compliance_age_rating_decision",
                "Compliance",
                layer_title="设计决策",
            ),
            _selection(
                7,
                "L5实体",
                "Combat Runtime",
                "kind=system；schema=system.v1",
                ["combat_system_decision"],
                layer_title="L5实体",
            ),
        ],
    }

    report = EntityValidator().validate(parsed)

    assert report["concrete_node_count"] == 1
    assert report["covered_concrete_nodes"] == 1
    assert report["entity_coverage_rate"] == 1.0
    assert report["missing_entities"] == []


def test_step02_liveops_projects_keep_liveops_only_nodes_in_denominator():
    parsed = {
        "source": "test.md",
        "design_summary": {"node_count": 6},
        "selections": [
            _selection(1, "商业模式", "free_to_play", layer_title="项目愿景"),
            _selection(2, "运营模式", "live_service", layer_title="项目愿景"),
            _selection(3, "combat_system_decision", "Combat", layer_title="设计决策"),
            _selection(4, "data_metric_decision", "Data", layer_title="设计决策"),
            _selection(
                5, "retention_daily_loop_decision", "Retention", layer_title="设计决策"
            ),
            _selection(
                6, "launch_store_page_decision", "Launch", layer_title="设计决策"
            ),
            _selection(
                7, "documentation_core_doc_decision", "Docs", layer_title="设计决策"
            ),
            _selection(
                8,
                "L5实体",
                "Combat Runtime",
                "kind=system；schema=system.v1",
                ["combat_system_decision"],
                layer_title="L5实体",
            ),
        ],
    }

    report = EntityValidator().validate(parsed)
    missing_node_ids = {item["node_id"] for item in report["missing_entities"]}

    assert report["concrete_node_count"] == 4
    assert report["covered_concrete_nodes"] == 1
    assert report["entity_coverage_rate"] == 0.25
    assert missing_node_ids == {
        "data_metric_decision",
        "retention_daily_loop_decision",
        "launch_store_page_decision",
    }


def test_step02_real_l5_without_expected_total_does_not_report_fake_full_coverage():
    parsed = {
        "source": "test.md",
        "selections": [
            _selection(
                1,
                "L5实体",
                "Stygian Blade",
                "kind=weapon；schema=weapon.v1",
                ["combat_node"],
            ),
        ],
    }

    report = EntityValidator().validate(parsed)

    assert report["concrete_node_count"] == 0
    assert report["covered_concrete_nodes"] == 1
    assert report["entity_coverage_rate"] == 0.0


def test_step02_synthesizes_entities_when_l5_entities_missing():
    parsed = {
        "source": "test.md",
        "selections": [
            _selection(index, "玩法系统", f"系统 {index}", "用于验证本地实体补全。")
            for index in range(1, 60)
        ],
    }

    report = EntityValidator().validate(parsed)

    assert report["entity_count"] == 47
    assert report["concrete_node_count"] == 59
    assert report["entity_coverage_rate"] == round(47 / 59, 4)
    assert report["entities"][0]["inference"]["mode"] == "local_selection_fallback"


def test_step02_cycle_report_does_not_duplicate_closing_node():
    graph = GraphGenerator().generate(
        {
            "nodes": [
                {"id": "A", "name": "A", "source": "test"},
                {"id": "B", "name": "B", "source": "test"},
            ],
            "edges": [
                {"from": "A", "to": "B"},
                {"from": "B", "to": "A"},
            ],
        },
        {"entities": []},
    )

    assert graph["cycles"] == [["A", "B", "A"]]


def test_step03_converts_entities_to_bound_requirements():
    parsed = {
        "source": "test.md",
        "selections": [
            _selection(
                1,
                "L5实体",
                "Stygian Blade",
                "kind=weapon；schema=weapon.v1",
                ["combat_node"],
            ),
        ],
    }
    requirements = EntityToRequirementConverter().convert(parsed)
    SystemBinder().bind(
        requirements, {"nodes": [{"id": "combat_node", "name": "Combat"}]}
    )
    quality = build_requirement_quality_report(requirements)

    assert len(requirements) >= 3
    assert requirements[0]["trace_kind"] == "design_entity"
    assert requirements[0]["system_ids"] == ["combat_node"]
    assert quality["system_binding_rate"] == 1.0
    assert quality["placeholder_rate"] == 0.0
    assert quality["average_requirements_per_bound_system"] >= 3


def test_step03_unrelated_text_does_not_get_fuzzy_bound():
    requirements = [
        {
            "id": "REQ-UNRELATED",
            "requirement": "实现完全无关的烹饪装饰流程。",
            "entity_label": "烹饪装饰",
            "dependencies": [],
            "phase": "core_playable",
        }
    ]

    SystemBinder().bind(
        requirements, {"nodes": [{"id": "SYS-COMBAT", "name": "Combat"}]}
    )

    assert requirements[0]["system_ids"] == []
    assert requirements[0]["system_binding"]["method"] == "unmatched"


def test_step04_converts_entities_to_assets_with_market_fallback():
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "selections": [
            _selection(
                1,
                "L5实体",
                "Stygian Blade",
                "kind=weapon；schema=weapon.v1",
                ["combat_node"],
            ),
        ],
    }
    assets = EntityToAssetConverter().convert(parsed)
    market = MarketResearchSkill().local_fallback(parsed)

    assert len(assets) >= 3
    assert assets[0]["source_entity_id"] == "ENT-001"
    assert assets[0]["priority"] in {"P0", "P1"}
    assert assets[0]["complexity"] in {"xs", "s", "m", "l", "xl"}
    assert any(asset["asset_type"] == "effect" for asset in assets)
    assert any(asset.get("resolution") for asset in assets if asset["priority"] == "P0")
    assert market["network_used"] is False


def test_step04_reads_market_library_for_fps_and_puzzle(tmp_path, monkeypatch):
    monkeypatch.setattr(step04_helpers, "MARKET_DATA_DIR", tmp_path)
    for key in ("fps", "puzzle"):
        (tmp_path / f"{key}.json").write_text(
            json.dumps(
                {
                    "genre": key,
                    "style_direction": f"{key} style",
                    "reference_principles": [f"{key} principle"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    fps = MarketResearchSkill().local_fallback({"raw_text": "competitive fps shooter"})
    puzzle = MarketResearchSkill().local_fallback({"raw_text": "minimal puzzle game"})

    assert fps["mode"] == "reference_library"
    assert fps["genre"] == "fps"
    assert puzzle["mode"] == "reference_library"
    assert puzzle["genre"] == "puzzle"


def test_step04_reads_roguelike_action_market_library_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(step04_helpers, "MARKET_DATA_DIR", tmp_path)
    (tmp_path / "roguelike_action.json").write_text(
        json.dumps(
            {
                "genre": "roguelike_action",
                "style_direction": "roguelike action style",
                "reference_principles": ["readability"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    market = MarketResearchSkill().local_fallback(
        {"raw_text": "Hades roguelike action"}
    )

    assert market["mode"] == "reference_library"
    assert market["genre"] == "roguelike_action"


def test_step04_asset_phase_matches_six_phase_classifier():
    parsed = {
        "source": "test.md",
        "selections": [
            _selection(
                1,
                "L5实体",
                "永久解锁",
                "kind=ability；schema=ability.v1",
                ["progression_node"],
            ),
            _selection(
                2,
                "L5实体",
                "公会大厅",
                "kind=system；schema=system.v1",
                ["social_node"],
            ),
            _selection(
                3,
                "L5实体",
                "release_build telemetry",
                "kind=config；schema=config.v1",
                ["release_node"],
            ),
        ],
    }

    phases = {
        asset["required_for_phase"]
        for asset in EntityToAssetConverter().convert(parsed)
    }

    assert {"progression", "social", "launch_ops"}.issubset(phases)


def test_intelligent_reviewer_classifies_actionable_issues():
    reviewer = IntelligentReviewer()
    report = reviewer.review_program(
        [
            {
                "id": "REQ-001",
                "requirement": "实现战斗系统的输入响应、命中判定、状态更新和验收路径。",
                "source_refs": ["test.md:1"],
                "system_ids": ["combat_node"],
                "inputs": ["design_selection"],
                "outputs": ["Assets/Scripts/Combat.cs"],
                "dependencies": ["combat_node"],
                "acceptance": "运行战斗流程。",
            }
        ]
    )

    assert report["blocking_issue_count"] == 0
    assert report["warning_count"] == 0
    assert report["verdict"] == "PASS"


def test_intelligent_reviewer_warns_when_warning_issues_exist():
    reviewer = IntelligentReviewer()
    report = reviewer.review_program(
        [
            {
                "id": "REQ-WARN",
                "requirement": "实现战斗系统的输入响应、命中判定、状态更新和验收路径。",
                "source_refs": ["test.md:1"],
                "system_ids": [],
                "inputs": ["design_selection"],
                "outputs": ["Assets/Scripts/Combat.cs"],
                "dependencies": [],
                "acceptance": "运行战斗流程。",
            }
        ]
    )

    assert report["warning_count"] == 1
    assert report["verdict"] == "WARN"


def test_intelligent_reviewer_keeps_critical_separate_from_blockers():
    reviewer = IntelligentReviewer()
    report = reviewer.review_program(
        [
            {
                "id": "REQ-CRITICAL",
                "requirement": "实现战斗系统的输入响应、命中判定、状态更新和验收路径。",
                "source_refs": ["test.md:1"],
                "system_ids": ["combat_node"],
                "inputs": ["design_selection"],
                "outputs": ["Assets/Scripts/Combat.cs"],
                "dependencies": ["combat_node"],
            }
        ]
    )

    assert report["blocker_count"] == 0
    assert report["critical_count"] == 1
    assert report["requires_action_count"] == 1
    assert report["blocking_issue_count"] == 0
    assert report["verdict"] == "FAIL"


def test_intelligent_reviewer_requires_action_counts_blockers():
    reviewer = IntelligentReviewer()
    report = reviewer.review_program([])

    assert report["blocker_count"] == 1
    assert report["critical_count"] == 0
    assert report["requires_action_count"] == 1
    assert report["blocking_issue_count"] == 1
    assert report["verdict"] == "BLOCKED"


def test_pipeline_quality_collects_from_explicit_artifacts_root(tmp_path):
    def write_json(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    write_json(
        tmp_path / "stage_00" / "core_question_coverage_report.json",
        {"coverage_rate": 0.5},
    )
    write_json(tmp_path / "stage_01" / "core_loop.json", {"loop": ["act"]})
    write_json(
        tmp_path / "stage_01" / "system_definitions.json", {"definition_rate": 1.0}
    )
    write_json(
        tmp_path / "stage_02" / "entity_coverage_report.json",
        {"entity_coverage_rate": 0.9, "entity_count": 3},
    )
    write_json(
        tmp_path / "stage_03" / "requirement_quality_report.json",
        {"system_binding_rate": 1.0, "placeholder_rate": 0.0},
    )
    write_json(
        tmp_path / "stage_04" / "asset_registry.json", {"assets": [{"asset_id": "A1"}]}
    )
    write_json(
        tmp_path / "stage_05" / "intelligent_review_report.json",
        {"warning_count": 2, "blocking_issue_count": 0},
    )

    metrics = collect_quality_metrics(tmp_path)["metrics"]

    assert metrics["question_coverage_rate"] == 0.5
    assert metrics["core_loop_output_rate"] == 1.0
    assert metrics["asset_count"] == 1
    assert metrics["stage05_warning_count"] == 2


def test_pipeline_quality_plan_002_check_uses_entity_coverage(tmp_path):
    stage = tmp_path / "stage_02"
    stage.mkdir(parents=True)
    (stage / "entity_coverage_report.json").write_text(
        json.dumps({"entity_coverage_rate": 0.38, "entity_count": 3}),
        encoding="utf-8",
    )

    payload = check_plan_002(tmp_path)

    assert payload["checks"]["plan-002"]["passed"] is True


def test_find_sources_falls_back_to_latest_draft_source_artifacts(
    tmp_path, monkeypatch
):
    drafts_dir = tmp_path / "drafts"
    current_root = drafts_dir / "current" / "source_artifacts"
    older_root = drafts_dir / "older" / "source_artifacts"
    newer_root = drafts_dir / "newer" / "source_artifacts"
    current_root.mkdir(parents=True)

    def write_package(root, project_name):
        package_dir = root / "devflow_Concept_v2"
        package_dir.mkdir(parents=True)
        manifest = {
            "schema_version": 1,
            "project": project_name,
            "package_type": "Concept",
            "source_ids": ["Concept"],
            "stage": 0,
            "version": 2,
        }
        (package_dir / "package_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        return package_dir

    older_package = write_package(older_root, "Older")
    newer_package = write_package(newer_root, "Newer")
    os.utime(older_root, (100, 100))
    os.utime(newer_root, (200, 200))

    monkeypatch.setattr(finder, "DRAFTS_DIR", drafts_dir)
    monkeypatch.setattr(finder, "SOURCE_ARTIFACTS_DIR", current_root)
    monkeypatch.setattr(finder, "PROJECT_ROOT", tmp_path)

    sources = finder.find_sources(
        ("devflow_Concept_*",), mode="latest", source_ids=("Concept",)
    )

    assert sources == [newer_package]
    assert older_package not in sources
