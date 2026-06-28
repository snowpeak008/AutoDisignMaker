from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


PROJECT_TEMPLATES = Path("knowledge/design_data/project_templates")

PHASE1_COMPLETE_TARGETS = [
    "builtin_indie_dead_cells.json",
    "builtin_indie_hades_l5_partial.json",
    "builtin_3a_axiom_verge.json",
    "builtin_3a_cuphead.json",
    "builtin_iaa_hypercasual_crossy_road.json",
    "builtin_large_service_path_of_exile.json",
    "builtin_midcore_clash_royale.json",
]

PHASE2_PARTIAL_TARGETS = [
    "builtin_indie_slay_the_spire.json",
    "builtin_indie_vampire_survivors.json",
    "builtin_indie_the_binding_of_isaac_rebirth.json",
    "builtin_indie_hollow_knight.json",
    "builtin_indie_enter_the_gungeon.json",
    "builtin_indie_stardew_valley.json",
    "builtin_indie_factorio.json",
    "builtin_indie_celeste.json",
]

PHASE3_PARTIAL_TARGETS = [
    "builtin_3a_blasphemous.json",
    "builtin_3a_celeste.json",
    "builtin_3a_ori_and_the_blind_forest.json",
    "builtin_3a_shovel_knight.json",
    "builtin_3a_spiritfarer.json",
    "builtin_3a_terraria.json",
    "builtin_3a_undertale.json",
]

PHASE4_PARTIAL_TARGETS = [
    "builtin_large_service_maplestory.json",
    "builtin_large_service_old_school_runescape.json",
    "builtin_large_service_ragnarok_online.json",
    "builtin_large_service_warframe.json",
    "builtin_midcore_brawl_stars.json",
    "builtin_midcore_marvel_snap.json",
    "builtin_iaa_hypercasual_2048.json",
    "builtin_iaa_hypercasual_cut_the_rope.json",
    "builtin_iaa_hypercasual_flappy_bird.json",
    "builtin_iaa_hypercasual_fruit_ninja.json",
    "builtin_iaa_hypercasual_jetpack_joyride.json",
    "builtin_iaa_hypercasual_royal_match.json",
    "builtin_iaa_hypercasual_stickman_hook.json",
    "builtin_iaa_hypercasual_coin_master.json",
]

P0_PARTIAL_TARGETS = (
    PHASE2_PARTIAL_TARGETS + PHASE3_PARTIAL_TARGETS + PHASE4_PARTIAL_TARGETS
)

P0_NODES = {
    "action_rule_decision",
    "input_control_decision",
    "objective_system_decision",
    "settlement_system_decision",
    "progression_system_decision",
    "build_system_decision",
    "character_unit_decision",
    "item_resource_content_decision",
    "level_space_decision",
    "meta_structure_decision",
    "content_type_decision",
    "randomness_system_decision",
    "balance_model_decision",
    "ux_information_architecture_decision",
    "hud_feedback_decision",
    "audio_experience_decision",
}

KIND_BY_SCHEMA = {
    "skill_card_v1": "skill",
    "operation_card_v1": "operation",
    "system_card_v1": "system",
    "numeric_curve_v1": "numeric_curve",
    "encounter_card_v1": "encounter",
    "content_card_v1": "content",
    "loop_card_v1": "loop",
}

OLD_3D_PUBLIC_NAMES = {
    "A Short Hike",
    "Apex Legends",
    "Borderlands 3",
    "Death Stranding",
    "Doom Eternal",
    "Elden Ring",
    "Final Fantasy XIV",
    "God of War",
    "Halo Infinite",
    "Helix Jump",
    "Last of Us",
    "Resident Evil",
    "Risk of Rain 2",
    "Sekiro",
    "Splatoon 3",
    "Stack",
    "Subway Surfers",
    "Valorant",
    "World of Warcraft",
}

REMOVED_TEMPLATE_FILES = {
    "builtin_iaa_hypercasual_helix_jump.json",
    "builtin_iaa_hypercasual_stack.json",
    "builtin_iaa_hypercasual_subway_surfers.json",
    "builtin_indie_a_short_hike.json",
    "builtin_indie_risk_of_rain_2.json",
    "builtin_3a_sekiro_shadows_die_twice.json",
    "builtin_3a_god_of_war_ragnarok.json",
    "builtin_3a_elden_ring.json",
    "builtin_3a_resident_evil_4_remake.json",
    "builtin_3a_the_last_of_us_part_ii.json",
    "builtin_3a_death_stranding.json",
    "builtin_3a_doom_eternal.json",
    "builtin_3a_halo_infinite.json",
    "builtin_3a_borderlands_3.json",
    "builtin_large_service_world_of_warcraft.json",
    "builtin_large_service_final_fantasy_xiv.json",
    "builtin_large_service_splatoon_3.json",
    "builtin_large_service_apex_legends.json",
    "builtin_large_service_valorant.json",
}

EXPECTED_PUBLIC_SCALE_COUNTS = Counter(
    {
        "iaa_hypercasual": 9,
        "indie": 10,
        "midcore": 3,
        "3a": 9,
        "large_service": 5,
    }
)

SCALE_LABEL_MAP = {
    "iaa_hypercasual": "IAA 超休闲小游戏",
    "indie": "独立游戏",
    "midcore": "中度商业游戏",
    "3a": "精品2D大作",
    "large_service": "2D长线服务游戏",
}

SOURCE_LABEL = "内置范本"


def _load_template(name: str) -> dict:
    return json.loads((PROJECT_TEMPLATES / name).read_text(encoding="utf-8"))


def _load_gameplay_system_options() -> list[dict]:
    payload = json.loads(
        Path("knowledge/design_data/gameplay_system_options.json").read_text(
            encoding="utf-8"
        )
    )
    return payload["options"]


def _load_public_template_entries() -> list[dict]:
    index = _load_template("template_index.json")
    return [entry for entry in index["templates"] if entry.get("visibility") == "public"]


def _concrete_node_ids() -> set[str]:
    template = _load_template("builtin_indie_hades_l5_complete.json")
    return set(_covered_nodes(template))


def _covered_nodes(template: dict) -> dict[str, list[dict]]:
    nodes = template["projectState"]["nodes"]
    return {
        node_id: node["designEntities"]
        for node_id, node in nodes.items()
        if isinstance(node, dict) and node.get("designEntities")
    }


def _validate_entity_shape(entity: dict) -> None:
    for field in ("kind", "schema", "id", "label"):
        assert entity.get(field), f"missing {field}: {entity}"
    assert entity["id"] == entity["id"].lower()
    assert " " not in entity["id"]
    assert KIND_BY_SCHEMA.get(entity["schema"]) == entity["kind"]
    if entity["schema"] == "numeric_curve_v1":
        curve = entity.get("sampleCurve", [])
        assert len(curve) >= 4
        assert [point["x"] for point in curve] == sorted(point["x"] for point in curve)
    if entity["schema"] == "loop_card_v1":
        assert len(entity.get("nodes", [])) >= 3
    if entity["schema"] == "encounter_card_v1":
        assert len(entity.get("phases", [])) >= 2
    if entity["schema"] == "system_card_v1":
        assert entity.get("inputs")
        assert entity.get("outputs")


def test_phase1_templates_reach_complete_l5_coverage() -> None:
    for name in PHASE1_COMPLETE_TARGETS:
        template = _load_template(name)
        covered = _covered_nodes(template)
        assert len(covered) >= 39, name
        assert P0_NODES <= set(covered), name
        entity_ids: set[str] = set()
        for node_entities in covered.values():
            for entity in node_entities:
                _validate_entity_shape(entity)
                assert entity.get("supplement_basis"), entity["id"]
                assert entity["id"] not in entity_ids
                entity_ids.add(entity["id"])


def test_phase2_to_phase4_templates_reach_p0_l5_coverage() -> None:
    for name in P0_PARTIAL_TARGETS:
        template = _load_template(name)
        covered = _covered_nodes(template)
        assert len(covered) >= 16, name
        assert P0_NODES <= set(covered), name
        entity_ids: set[str] = set()
        for node_id in P0_NODES:
            for entity in covered[node_id]:
                _validate_entity_shape(entity)
                assert entity["id"] not in entity_ids
                entity_ids.add(entity["id"])


def test_public_templates_are_2d_l5_and_index_synced() -> None:
    concrete_nodes = _concrete_node_ids()
    entries = _load_public_template_entries()
    assert Counter(entry["targetScale"] for entry in entries) == EXPECTED_PUBLIC_SCALE_COUNTS
    assert len(entries) == sum(EXPECTED_PUBLIC_SCALE_COUNTS.values())
    assert not any((PROJECT_TEMPLATES / name).exists() for name in REMOVED_TEMPLATE_FILES)

    for entry in entries:
        assert entry.get("dimension") == "2D", entry["fileName"]
        assert entry.get("qualityClaim") == "L5_partial", entry["fileName"]
        assert entry.get("qualityTier") == "B", entry["fileName"]
        assert entry["fileName"] == f"{entry['id']}.json", entry["fileName"]
        assert not any(name in entry["name"] for name in OLD_3D_PUBLIC_NAMES)

        template = _load_template(entry["fileName"])
        meta = template["template"]
        assert meta["id"] == entry["id"], entry["fileName"]
        assert meta["name"] == entry["name"], entry["fileName"]
        assert meta["qualityClaim"] != "L4_only_filled", entry["fileName"]
        assert meta["qualityClaim"] == entry["qualityClaim"], entry["fileName"]
        assert meta["qualityTier"] == entry["qualityTier"], entry["fileName"]
        assert template["projectState"]["profile"].get("dimension") == "2D"
        assert not any(name in meta["name"] for name in OLD_3D_PUBLIC_NAMES)

        nodes = template["projectState"]["nodes"]
        covered = _covered_nodes(template)
        assert concrete_nodes <= set(covered), entry["fileName"]
        assert len(covered) == len(concrete_nodes), entry["fileName"]

        entity_ids: set[str] = set()
        for node_id, node in nodes.items():
            if not isinstance(node, dict):
                continue
            assert "范本反推" not in node.get("designNote", ""), (
                entry["fileName"],
                node_id,
            )
            for entity in node.get("designEntities", []):
                _validate_entity_shape(entity)
                assert entity.get("supplement_basis"), entity["id"]
                assert entity["id"] not in entity_ids
                entity_ids.add(entity["id"])


def test_builtin_template_scale_labels_are_readable_and_synced() -> None:
    index = _load_template("template_index.json")
    for entry in index["templates"]:
        scale = entry.get("targetScale")
        if scale not in SCALE_LABEL_MAP:
            continue
        label = entry.get("scaleLabel", "")
        assert label == SCALE_LABEL_MAP[scale], entry["id"]
        assert "?" not in label
        assert "\ufffd" not in label

    for path in PROJECT_TEMPLATES.glob("builtin_*.json"):
        template = _load_template(path.name)
        meta = template["template"]
        scale = meta.get("targetScale")
        if scale not in SCALE_LABEL_MAP:
            continue
        label = meta.get("scaleLabel", "")
        assert label == SCALE_LABEL_MAP[scale], path.name
        assert "?" not in label
        assert "\ufffd" not in label


def test_builtin_template_display_metadata_is_readable() -> None:
    for path in PROJECT_TEMPLATES.glob("builtin_*.json"):
        template = _load_template(path.name)
        meta = template["template"]
        profile = template["projectState"]["profile"]
        name = meta.get("name", "")
        summary = meta.get("summary", "")
        source_label = meta.get("sourceLabel", "")

        assert source_label == SOURCE_LABEL, path.name
        assert "?" not in source_label
        assert "\ufffd" not in source_label
        assert profile.get("dimension") == "2D", path.name
        assert summary.endswith("。"), path.name
        assert any("\u4e00" <= char <= "\u9fff" for char in summary), path.name
        assert "?" not in name
        assert "\ufffd" not in name
        if meta.get("gameName") != "2048":
            assert "（" in name and "）" in name, path.name

        if meta.get("id") == "builtin_indie_hades_l5_complete":
            assert meta.get("qualityClaim") == "L5_complete_consistent"
            assert meta.get("qualityTier") == "A+"
        else:
            assert meta.get("qualityClaim") == "L5_partial", path.name
            assert meta.get("qualityTier") == "B", path.name


def test_builtin_templates_have_valid_gameplay_systems() -> None:
    from core.design.gameplay_systems import validation_messages

    options = _load_gameplay_system_options()
    option_ids = {option["id"] for option in options}

    for path in PROJECT_TEMPLATES.glob("builtin_*.json"):
        template = _load_template(path.name)
        gameplay = template["projectState"].get("gameplaySystems", {})
        selected = gameplay.get("selected", [])
        weights = gameplay.get("weights", {})
        core_loops = gameplay.get("coreLoops", {})

        assert selected, path.name
        assert len(selected) == len(set(selected)), path.name
        assert set(selected) <= option_ids, path.name

        total_weight = 0
        for system_id in selected:
            weight_entry = weights.get(system_id, {})
            assert isinstance(weight_entry, dict), (path.name, system_id)
            assert weight_entry.get("weight_type") == "percent", (path.name, system_id)
            weight = weight_entry.get("weight")
            assert isinstance(weight, int), (path.name, system_id, weight)
            assert 0 < weight <= 100, (path.name, system_id, weight)
            total_weight += weight
            assert str(core_loops.get(system_id, "")).strip(), (path.name, system_id)

        assert total_weight == 100, path.name
        assert validation_messages(options, gameplay) == [], path.name


def test_legacy_template_gameplay_systems_can_be_inferred() -> None:
    from core.design.gameplay_systems import (
        infer_gameplay_systems_from_template,
        validation_messages,
    )

    options = _load_gameplay_system_options()
    template = _load_template("builtin_indie_slay_the_spire.json")
    state = template["projectState"]
    state["gameplaySystems"] = {"schemaVersion": "1.0", "selected": []}

    inferred = infer_gameplay_systems_from_template(state, options)
    gameplay = inferred["gameplaySystems"]

    assert gameplay["selected"]
    assert sum(entry["weight"] for entry in gameplay["weights"].values()) == 100
    assert validation_messages(options, gameplay) == []


def test_empty_project_still_requires_manual_gameplay_system_selection() -> None:
    from core.design.gameplay_systems import empty_state, validation_messages

    options = _load_gameplay_system_options()

    assert validation_messages(options, empty_state()) == ["至少选择一个玩法系统。"]
