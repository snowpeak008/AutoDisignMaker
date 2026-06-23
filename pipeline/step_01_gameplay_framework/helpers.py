from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.io import now_iso, read_json


GENRE_TEMPLATES_PATH = Path(__file__).with_name("data") / "genre_templates.json"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _field(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _label(item: Any) -> str:
    label = _field(item, "label", "")
    if label:
        return _text(label)
    item_type = _text(_field(item, "item_type"))
    option = _text(_field(item, "option"))
    return f"{item_type}: {option}" if item_type else option


def _selection_text(item: Any) -> str:
    return " ".join(
        _text(_field(item, name))
        for name in ("item_type", "option", "purpose", "layer_title")
    )


@lru_cache(maxsize=1)
def _load_templates_cached(path: str, mtime_ns: int, size: int) -> dict[str, Any]:
    """Load genre templates for one file signature."""
    payload = read_json(Path(path), {})
    return payload if isinstance(payload, dict) else {}


def _load_templates() -> dict[str, Any]:
    """Load genre templates and refresh when the file signature changes."""
    try:
        stat = GENRE_TEMPLATES_PATH.stat()
        signature = (str(GENRE_TEMPLATES_PATH), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        signature = (str(GENRE_TEMPLATES_PATH), -1, -1)
    return _load_templates_cached(*signature)


def _clear_template_cache() -> None:
    """Clear cached genre templates for tests and dynamic template updates."""
    _load_templates_cached.cache_clear()


def _pick_template_key(raw_text: str, selections: list[Any]) -> str:
    """Pick the closest known genre template from raw text and selections."""
    text = (
        raw_text + " " + " ".join(_selection_text(item) for item in selections)
    ).lower()
    if any(
        token in text for token in ("rogue", "肉鸽", "roguelite", "roguelike", "hades")
    ):
        return "roguelike_action"
    if any(token in text for token in ("fps", "射击", "枪", "shooter")):
        return "fps"
    if any(token in text for token in ("puzzle", "解谜", "match", "消除")):
        return "puzzle"
    if any(token in text for token in ("strategy", "rts", "4x", "策略", "战棋")):
        return "strategy"
    if any(
        token in text for token in ("rpg", "jrpg", "arpg", "role-playing", "角色扮演")
    ):
        return "rpg"
    if any(token in text for token in ("moba", "推塔", "对线")):
        return "moba"
    return "generic"


def pick_genre_template_key(raw_text: str, selections: list[Any]) -> str:
    """Public accessor for genre template key detection."""
    return _pick_template_key(raw_text, selections)


class LoopExtractor:
    """Extract a core gameplay loop from explicit selections or templates."""

    def extract(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Return the selected or fallback core-loop report."""
        selections = [item for item in parsed.get("selections", []) if item]
        explicit_loop = self._explicit_loop(selections)
        template_key = _pick_template_key(_text(parsed.get("raw_text")), selections)
        templates = _load_templates()
        template = templates.get(template_key) or templates.get("generic", {})
        loop = explicit_loop or list(template.get("core_loop", []))
        if not loop:
            loop = ["理解目标", "执行核心动作", "获得反馈", "推进下一目标"]
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "source": _text(parsed.get("source")),
            "template_key": template_key,
            "source_kind": "explicit" if explicit_loop else "template_fallback",
            "loop": loop,
            "output_rate": 1.0 if loop else 0.0,
        }

    def _explicit_loop(self, selections: list[Any]) -> list[str]:
        """Parse explicit core-loop selections into ordered nodes."""
        for item in selections:
            if _text(_field(item, "item_type")) != "核心循环":
                continue
            value = _text(_field(item, "option"))
            normalized = re.sub(r"\s*(?:->|→|=>|⇒|/|、|,|，)\s*", "->", value)
            parts = [part.strip() for part in normalized.split("->") if part.strip()]
            return parts or ([value] if value else [])
        return []


class SystemDeducer:
    """Deduce top-level gameplay systems from graphs and genre templates."""

    def deduce(
        self, parsed: dict[str, Any], system_graph: dict[str, Any]
    ) -> dict[str, Any]:
        """Return normalized system definitions capped for planning."""
        selections = [item for item in parsed.get("selections", []) if item]
        systems = self._systems_from_graph(system_graph)
        template_key = _pick_template_key(_text(parsed.get("raw_text")), selections)
        templates = _load_templates()
        template = templates.get(template_key) or templates.get("generic", {})
        systems.extend(
            self._systems_from_template(
                template, existing_names={item["name"] for item in systems}
            )
        )
        systems = systems[:8]
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "source": _text(parsed.get("source")),
            "template_key": template_key,
            "systems": systems,
            "system_count": len(systems),
            "definition_rate": 1.0 if len(systems) >= 5 else round(len(systems) / 5, 4),
        }

    def _systems_from_graph(self, system_graph: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert graph nodes into normalized system definitions."""
        systems: list[dict[str, Any]] = []
        for index, node in enumerate(system_graph.get("nodes", []), 1):
            if not isinstance(node, dict):
                continue
            name = _text(node.get("name"))
            name = re.sub(
                r"^(system_layer|system)[：:]\s*", "", name, flags=re.IGNORECASE
            ).strip()
            if not name:
                continue
            systems.append(
                {
                    "id": _text(node.get("id")) or f"SYS-{index:03d}",
                    "name": name,
                    "responsibility": f"承载{name}相关的核心玩法职责。",
                    "source": _text(node.get("source")),
                    "confidence": "explicit",
                }
            )
        return systems

    def _systems_from_template(
        self, template: dict[str, Any], *, existing_names: set[str]
    ) -> list[dict[str, Any]]:
        """Return template systems not already present in explicit graph systems."""
        systems: list[dict[str, Any]] = []
        for item in template.get("systems", []):
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            if not name or name in existing_names:
                continue
            systems.append(
                {
                    "id": _text(item.get("id"))
                    or f"SYS-FALLBACK-{len(systems) + 1:03d}",
                    "name": name,
                    "responsibility": _text(item.get("responsibility"))
                    or f"提供{name}能力。",
                    "source": "genre_template",
                    "confidence": "fallback",
                }
            )
            existing_names.add(name)
        return systems
