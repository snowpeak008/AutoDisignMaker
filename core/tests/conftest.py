from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_step01_template_cache() -> None:
    """Clear Step 01 genre template cache around every test."""
    from pipeline.step_01_gameplay_framework.helpers import _clear_template_cache

    _clear_template_cache()
    yield
    _clear_template_cache()


@pytest.fixture
def parsed_with_l5_entities() -> dict:
    """Return parsed design data containing one explicit L5 entity."""
    return {
        "selections": [
            {
                "item_type": "L5实体",
                "option": "短剑",
                "purpose": "kind=weapon；schema=weapon.v1",
                "id": "SEL-001",
                "dependencies": ["weapon_node"],
                "source_ref": "test/design.md:1",
            }
        ],
        "raw_text": "Hades roguelike action",
        "source": "test/design.md",
        "design_summary": {"node_count": 1},
    }


@pytest.fixture
def parsed_no_l5() -> dict:
    """Return parsed design data that must use local fallback entities."""
    return {
        "selections": [
            {
                "item_type": "核心循环",
                "option": "进入 -> 战斗 -> 奖励",
                "id": "SEL-001",
                "source_ref": "test/concept.md:1",
            }
        ],
        "raw_text": "roguelike action",
        "source": "test/concept.md",
    }
