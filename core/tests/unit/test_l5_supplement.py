from __future__ import annotations

import json
from types import SimpleNamespace

from core.adapters.base import ModelResult
from core.runtime import preflight
from pipeline.step_01_gameplay_framework.helpers import pick_genre_template_key
from pipeline.step_02_design_review_freeze.helpers import (
    EntityValidator,
    extract_l5_entities,
    should_supplement,
)
from pipeline.step_02_design_review_freeze.supplement import EntitySupplementAdapter


def _selection(
    index: int,
    item_type: str,
    option: str,
    purpose: str = "",
    dependencies: list[str] | None = None,
    layer_title: str = "测试层",
) -> SimpleNamespace:
    return SimpleNamespace(
        index=index,
        id=f"SEL-{index:03d}",
        layer_number=5,
        item_type=item_type,
        option=option,
        label=f"{item_type}：{option}",
        purpose=purpose,
        dependencies=dependencies or [],
        unlocks=[],
        layer_status="Submitted / accepted",
        layer_title=layer_title,
        source_ref=f"test.md:{index}",
    )


class FakeAdapter:
    def __init__(self, text: str = "", status: str = "success") -> None:
        self.text = text
        self.status = status
        self.calls = 0

    def generate(self, task):
        self.calls += 1
        return ModelResult(task_id=task.task_id, status=self.status, text=self.text)


class RaisingAdapter:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def generate(self, task):
        self.calls += 1
        raise self.exc


def _entity(label: str, kind: str = "weapon", node_id: str = "combat_node") -> dict:
    return {
        "label": label,
        "kind": kind,
        "schema": f"{kind}.v1",
        "node_id": node_id,
        "supplement_basis": f"{label} basis",
    }


def test_extract_l5_entities_reads_approximate_status() -> None:
    parsed = {
        "source": "test.md",
        "selections": [
            _selection(1, "L5实体", "主角剑（概略）", "kind=weapon；status=approximate")
        ],
    }

    entities = extract_l5_entities(parsed)

    assert entities[0]["status"] == "approximate"
    assert entities[0]["schema"] == "unknown"


def test_extract_l5_entities_defaults_to_precise_status() -> None:
    parsed = {
        "source": "test.md",
        "selections": [
            _selection(1, "L5实体", "冥河之刃", "kind=weapon；schema=weapon.v1")
        ],
    }

    entities = extract_l5_entities(parsed)

    assert entities[0]["status"] == "precise"


def test_synthetic_entities_do_not_include_status() -> None:
    parsed = {
        "source": "test.md",
        "selections": [_selection(1, "玩法系统", "战斗系统", "combat")],
    }

    entities = extract_l5_entities(parsed)

    assert "status" not in entities[0]
    assert entities[0]["inference"]["mode"] == "local_selection_fallback"


def test_supplement_triggered_for_approximate_entity() -> None:
    entities = [{"kind": "weapon", "status": "approximate"}]

    assert should_supplement(entities, 1.0, "codex") is True


def test_supplement_not_triggered_for_adapter_none() -> None:
    entities = [{"kind": "weapon", "status": "approximate"}]

    assert should_supplement(entities, 0.1, "none") is False


def test_supplement_triggered_for_low_coverage() -> None:
    entities = [{"kind": "weapon", "status": "precise"}]

    assert should_supplement(entities, 0.5, "codex") is True


def test_public_genre_template_key_accessor() -> None:
    assert pick_genre_template_key("Hades roguelike action", []) == "roguelike_action"


def test_validate_entity_rejects_missing_kind(tmp_path) -> None:
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")

    assert (
        adapter._validate_entity({"label": "无 kind", "schema": "weapon.v1"}) is False
    )


def test_validate_entity_rejects_missing_node_id(tmp_path) -> None:
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")

    assert (
        adapter._validate_entity(
            {
                "label": "无节点",
                "kind": "weapon",
                "schema": "weapon.v1",
                "supplement_basis": "test",
            }
        )
        is False
    )


def test_cache_hit_returns_cached_entities(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "same",
        "selections": [
            _selection(1, "L5实体", "主角剑", "kind=weapon；status=approximate")
        ],
    }
    original = extract_l5_entities(parsed)
    fake = FakeAdapter(
        json.dumps({"supplemented_entities": [_entity("冥河之刃")]}, ensure_ascii=False)
    )
    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path, adapter_name="codex", model_adapter=fake
    )

    first = adapter.supplement(original, parsed)
    second = adapter.supplement(original, parsed)

    assert fake.calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.entities[0]["label"] == "冥河之刃"


def test_cache_miss_on_different_hash(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "one",
        "selections": [
            _selection(1, "L5实体", "主角剑", "kind=weapon；status=approximate")
        ],
    }
    original = extract_l5_entities(parsed)
    fake = FakeAdapter(
        json.dumps({"supplemented_entities": [_entity("冥河之刃")]}, ensure_ascii=False)
    )
    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path, adapter_name="codex", model_adapter=fake
    )

    adapter.supplement(original, parsed)
    parsed["source_sha256"] = "two"
    adapter.supplement(original, parsed)

    assert fake.calls == 2


def test_cache_accepts_legacy_entities_without_supplement_basis(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "same",
        "selections": [
            _selection(1, "L5实体", "主角剑", "kind=weapon；status=approximate")
        ],
    }
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")
    request = adapter._build_request(extract_l5_entities(parsed), parsed)
    (tmp_path / "ai_supplement_cache.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "request_hash": request.request_hash,
                "adapter": "codex",
                "entities": [
                    {
                        "label": "旧缓存武器",
                        "kind": "weapon",
                        "schema": "weapon.v1",
                        "node_id": "combat_node",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = adapter.supplement(extract_l5_entities(parsed), parsed)

    assert result.cache_hit is True
    assert result.entities[0]["label"] == "旧缓存武器"


def test_corrupt_cache_is_ignored(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "same",
        "selections": [
            _selection(1, "L5实体", "主角剑", "kind=weapon；status=approximate")
        ],
    }
    (tmp_path / "ai_supplement_cache.json").write_text("{broken", encoding="utf-8")
    fake = FakeAdapter(
        json.dumps({"supplemented_entities": [_entity("冥河之刃")]}, ensure_ascii=False)
    )
    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path, adapter_name="codex", model_adapter=fake
    )

    result = adapter.supplement(extract_l5_entities(parsed), parsed)

    assert fake.calls == 1
    assert result.cache_hit is False


def test_supplement_uses_fallback_on_ai_failure(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "selections": [],
    }
    original = [
        {
            "entity_id": "ENT-001",
            "label": "本地实体",
            "kind": "weapon",
            "schema": "weapon.v1",
        }
    ]
    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path,
        adapter_name="codex",
        model_adapter=FakeAdapter(status="failed"),
    )

    result = adapter.supplement(original, parsed)

    assert result.fallback_used is True
    assert result.added_count >= 1


def test_call_ai_reuses_one_adapter_instance_for_retries(tmp_path, monkeypatch) -> None:
    request = EntitySupplementAdapter(
        cache_dir=tmp_path, adapter_name="codex"
    )._build_request(
        [],
        {"source": "test.md", "raw_text": "Hades roguelike action", "selections": []},
    )
    fake = FakeAdapter(status="failed")
    created = 0
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")

    def fake_model_adapter():
        nonlocal created
        created += 1
        return fake

    monkeypatch.setattr(adapter, "_model_adapter", fake_model_adapter)

    assert adapter._call_ai(request) == []
    assert created == 1
    assert fake.calls == 2


def test_call_ai_raises_adapter_configuration_errors(tmp_path) -> None:
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="missing")
    request = adapter._build_request(
        [],
        {
            "source": "test.md",
            "raw_text": "Hades roguelike action",
            "selections": [],
        },
    )

    try:
        adapter._call_ai(request)
    except ValueError as exc:
        assert "unknown adapter" in str(exc)
    else:
        raise AssertionError("expected invalid adapter configuration to raise")


def test_supplement_falls_back_on_adapter_configuration_error(tmp_path) -> None:
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="missing")

    result = adapter.supplement(
        [],
        {
            "source": "test.md",
            "raw_text": "Hades roguelike action",
            "selections": [],
        },
    )

    assert result.fallback_used is True
    assert result.added_count >= 1
    assert "unknown adapter" in result.error


def test_call_ai_runtime_adapter_creation_failure_falls_back(
    tmp_path, monkeypatch
) -> None:
    request = EntitySupplementAdapter(
        cache_dir=tmp_path, adapter_name="codex"
    )._build_request(
        [],
        {"source": "test.md", "raw_text": "Hades roguelike action", "selections": []},
    )
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")
    monkeypatch.setattr(
        adapter, "_model_adapter", lambda: (_ for _ in ()).throw(OSError("io"))
    )

    assert adapter._call_ai(request) == []


def test_supplement_result_written_to_cache(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "same",
        "selections": [
            _selection(1, "L5实体", "主角剑", "kind=weapon；status=approximate")
        ],
    }
    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path,
        adapter_name="codex",
        model_adapter=FakeAdapter(
            json.dumps(
                {"supplemented_entities": [_entity("冥河之刃")]}, ensure_ascii=False
            )
        ),
    )

    adapter.supplement(extract_l5_entities(parsed), parsed)

    payload = json.loads(
        (tmp_path / "ai_supplement_cache.json").read_text(encoding="utf-8")
    )
    assert payload["request_hash"]
    assert payload["entities"][0]["label"] == "冥河之刃"


def test_merge_replaces_approximate_with_ai_entity(tmp_path) -> None:
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")
    original = [
        {
            "entity_id": "ENT-001",
            "label": "主角剑",
            "kind": "weapon",
            "schema": "unknown",
            "status": "approximate",
        }
    ]

    merged, added, completed = adapter._merge_entities(original, [_entity("冥河之刃")])

    assert merged[0]["label"] == "冥河之刃"
    assert added == 0
    assert completed == 1


def test_merge_preserves_precise_entities(tmp_path) -> None:
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")
    original = [
        {
            "entity_id": "ENT-001",
            "label": "精准武器",
            "kind": "weapon",
            "schema": "weapon.v1",
            "status": "precise",
        }
    ]

    merged, added, completed = adapter._merge_entities(original, [_entity("冥河之刃")])

    assert merged[0]["label"] == "精准武器"
    assert added == 1
    assert completed == 0


def test_merge_ids_are_continuous(tmp_path) -> None:
    adapter = EntitySupplementAdapter(cache_dir=tmp_path, adapter_name="codex")
    original = [
        {
            "entity_id": "ENT-099",
            "label": "精准武器",
            "kind": "weapon",
            "schema": "weapon.v1",
            "status": "precise",
        }
    ]

    merged, _, _ = adapter._merge_entities(
        original, [_entity("火球术", "ability", "ability_node")]
    )

    assert [entity["entity_id"] for entity in merged] == ["ENT-001", "ENT-002"]


def test_entity_validator_accepts_supplement_adapter(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "same",
        "design_summary": {"node_count": 2},
        "selections": [
            _selection(
                1,
                "L5实体",
                "主角剑",
                "kind=weapon；status=approximate",
                ["combat_node"],
            )
        ],
    }
    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path,
        adapter_name="codex",
        model_adapter=FakeAdapter(
            json.dumps(
                {
                    "supplemented_entities": [
                        _entity("冥河之刃", "weapon", "combat_node"),
                        _entity("冲刺斩击", "ability", "ability_node"),
                    ]
                },
                ensure_ascii=False,
            )
        ),
    )

    report = EntityValidator().validate(parsed, supplement_adapter=adapter)

    assert report["ai_supplement"]["triggered"] is True
    assert report["ai_supplement"]["entities_completed"] == 1
    assert report["entity_count"] == 2
    assert report["entity_coverage_rate"] == 1.0


def test_entity_validator_passes_real_missing_nodes_to_fallback(tmp_path) -> None:
    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "missing-node-test",
        "design_summary": {"node_count": 3},
        "selections": [
            _selection(1, "combat_system_decision", "Combat", layer_title="设计决策"),
            _selection(
                2, "currency_system_decision", "Currency", layer_title="设计决策"
            ),
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
    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path,
        adapter_name="codex",
        model_adapter=FakeAdapter('{"supplemented_entities": []}'),
    )

    report = EntityValidator().validate(parsed, supplement_adapter=adapter)
    node_ids = {entity["node_id"] for entity in report["entities"]}

    assert report["ai_supplement"]["fallback_used"] is True
    assert report["covered_concrete_nodes"] == 3
    assert report["entity_coverage_rate"] == 1.0
    assert {"currency_system_decision", "level_space_decision"} <= node_ids
    assert report["missing_entities"] == []


def test_entity_validator_without_adapter_keeps_legacy_report_shape() -> None:
    parsed = {
        "source": "test.md",
        "design_summary": {"node_count": 1},
        "selections": [
            _selection(1, "L5实体", "冥河之刃", "kind=weapon；schema=weapon.v1")
        ],
    }

    report = EntityValidator().validate(parsed)

    assert "ai_supplement" not in report
    assert report["entity_count"] == 1


def test_stage2_supplement_adapter_defaults_to_none(tmp_path, monkeypatch) -> None:
    from core.engines import generation

    monkeypatch.setattr(
        generation,
        "load_project_settings",
        lambda _root: {"pipeline_adapter": "none"},
    )

    assert generation._stage2_supplement_adapter(tmp_path) is None


def test_load_project_settings_defaults_pipeline_adapter_to_none(
    tmp_path, monkeypatch
) -> None:
    settings_path = tmp_path / "project_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(preflight, "project_settings_path", lambda _root: settings_path)

    settings = preflight.load_project_settings(tmp_path)

    assert settings["pipeline_adapter"] == "none"


def test_load_project_settings_preserves_invalid_pipeline_adapter(
    tmp_path, monkeypatch
) -> None:
    settings_path = tmp_path / "project_settings.json"
    settings_path.write_text(
        json.dumps({"pipeline_adapter": "codxe"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "project_settings_path", lambda _root: settings_path)

    settings = preflight.load_project_settings(tmp_path)

    assert settings["pipeline_adapter"] == "codxe"


def test_stage2_outputs_include_ai_supplement_metadata(tmp_path, monkeypatch) -> None:
    from core.engines import generation

    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "same",
        "design_summary": {"node_count": 2},
        "selections": [
            _selection(
                1,
                "L5实体",
                "主角剑",
                "kind=weapon；status=approximate",
                ["combat_node"],
            )
        ],
    }
    fake_adapter = EntitySupplementAdapter(
        cache_dir=tmp_path,
        adapter_name="codex",
        model_adapter=FakeAdapter(
            json.dumps(
                {
                    "supplemented_entities": [
                        _entity("冥河之刃", "weapon", "combat_node"),
                        _entity("冲刺斩击", "ability", "ability_node"),
                    ]
                },
                ensure_ascii=False,
            )
        ),
    )
    monkeypatch.setattr(
        generation, "_stage2_supplement_adapter", lambda _out_dir: fake_adapter
    )

    result = generation._stage2_outputs(parsed, tmp_path)
    report = json.loads(
        (tmp_path / "entity_coverage_report.json").read_text(encoding="utf-8")
    )

    assert result["design_entity_count"] == 2
    assert report["ai_supplement"]["triggered"] is True
    assert report["entity_coverage_rate"] == 1.0


def test_stage2_outputs_fall_back_on_invalid_adapter_name(
    tmp_path, monkeypatch
) -> None:
    from core.engines import generation

    parsed = {
        "source": "test.md",
        "raw_text": "Hades roguelike action",
        "source_sha256": "same",
        "design_summary": {"node_count": 2},
        "selections": [
            _selection(
                1,
                "L5实体",
                "主角剑",
                "kind=weapon；status=approximate",
                ["combat_node"],
            )
        ],
    }
    monkeypatch.setattr(
        generation,
        "load_project_settings",
        lambda _root: {"pipeline_adapter": "gemini"},
    )

    result = generation._stage2_outputs(parsed, tmp_path)
    report = json.loads(
        (tmp_path / "entity_coverage_report.json").read_text(encoding="utf-8")
    )

    assert result["content_exists"] is True
    assert report["ai_supplement"]["triggered"] is True
    assert report["ai_supplement"]["fallback_used"] is True
    assert "unknown adapter" in report["ai_supplement"]["error"]
