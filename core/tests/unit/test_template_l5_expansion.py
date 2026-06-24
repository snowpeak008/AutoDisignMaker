from __future__ import annotations

import json
from pathlib import Path


PROJECT_TEMPLATES = Path("knowledge/design_data/project_templates")

PHASE1_COMPLETE_TARGETS = [
    "builtin_indie_dead_cells.json",
    "builtin_indie_hades_l5_partial.json",
    "builtin_3a_elden_ring.json",
    "builtin_3a_sekiro_shadows_die_twice.json",
    "builtin_iaa_hypercasual_crossy_road.json",
    "builtin_large_service_apex_legends.json",
    "builtin_midcore_clash_royale.json",
]

PHASE2_PARTIAL_TARGETS = [
    "builtin_indie_slay_the_spire.json",
    "builtin_indie_vampire_survivors.json",
    "builtin_indie_the_binding_of_isaac_rebirth.json",
    "builtin_indie_risk_of_rain_2.json",
    "builtin_indie_enter_the_gungeon.json",
    "builtin_indie_stardew_valley.json",
    "builtin_indie_factorio.json",
    "builtin_indie_a_short_hike.json",
]

PHASE3_PARTIAL_TARGETS = [
    "builtin_3a_doom_eternal.json",
    "builtin_3a_resident_evil_4_remake.json",
    "builtin_3a_god_of_war_ragnarok.json",
    "builtin_3a_the_last_of_us_part_ii.json",
    "builtin_3a_borderlands_3.json",
    "builtin_3a_halo_infinite.json",
    "builtin_3a_death_stranding.json",
]

PHASE4_PARTIAL_TARGETS = [
    "builtin_large_service_valorant.json",
    "builtin_large_service_world_of_warcraft.json",
    "builtin_large_service_final_fantasy_xiv.json",
    "builtin_large_service_old_school_runescape.json",
    "builtin_large_service_splatoon_3.json",
    "builtin_midcore_brawl_stars.json",
    "builtin_midcore_marvel_snap.json",
    "builtin_iaa_hypercasual_flappy_bird.json",
    "builtin_iaa_hypercasual_fruit_ninja.json",
    "builtin_iaa_hypercasual_helix_jump.json",
    "builtin_iaa_hypercasual_royal_match.json",
    "builtin_iaa_hypercasual_stack.json",
    "builtin_iaa_hypercasual_stickman_hook.json",
    "builtin_iaa_hypercasual_subway_surfers.json",
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


def _load_template(name: str) -> dict:
    return json.loads((PROJECT_TEMPLATES / name).read_text(encoding="utf-8"))


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
