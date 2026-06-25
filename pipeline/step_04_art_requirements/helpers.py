from __future__ import annotations

from pathlib import Path
from typing import Any

from core.io import now_iso, read_json
from pipeline.step_02_design_review_freeze.helpers import extract_l5_entities


MARKET_DATA_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "market_data"


def _text(value: Any) -> str:
    return str(value or "").strip()


class EntityToAssetConverter:
    """Convert design entities into traceable art asset requirements."""

    MULTI_ASSET_MAP = {
        "character": [
            {
                "suffix": "原画",
                "asset_type": "art_asset",
                "priority": "P0",
                "complexity": "l",
            },
            {
                "suffix": "动画集",
                "asset_type": "animation",
                "priority": "P0",
                "complexity": "xl",
            },
            {
                "suffix": "UI头像",
                "asset_type": "ui",
                "priority": "P1",
                "complexity": "s",
            },
        ],
        "weapon": [
            {
                "suffix": "武器原画",
                "asset_type": "art_asset",
                "priority": "P0",
                "complexity": "m",
            },
            {
                "suffix": "攻击特效",
                "asset_type": "effect",
                "priority": "P0",
                "complexity": "m",
            },
            {"suffix": "图标", "asset_type": "ui", "priority": "P1", "complexity": "s"},
        ],
        "ability": [
            {
                "suffix": "施放特效",
                "asset_type": "effect",
                "priority": "P0",
                "complexity": "l",
            },
            {
                "suffix": "命中特效",
                "asset_type": "effect",
                "priority": "P0",
                "complexity": "m",
            },
            {
                "suffix": "技能图标",
                "asset_type": "ui",
                "priority": "P1",
                "complexity": "s",
            },
        ],
        "room": [
            {
                "suffix": "场景原画",
                "asset_type": "environment",
                "priority": "P0",
                "complexity": "xl",
            },
            {
                "suffix": "地块集",
                "asset_type": "environment",
                "priority": "P0",
                "complexity": "l",
            },
            {
                "suffix": "环境音效",
                "asset_type": "audio",
                "priority": "P1",
                "complexity": "m",
            },
        ],
        "enemy": [
            {
                "suffix": "角色原画",
                "asset_type": "art_asset",
                "priority": "P0",
                "complexity": "l",
            },
            {
                "suffix": "攻击特效",
                "asset_type": "effect",
                "priority": "P0",
                "complexity": "m",
            },
            {
                "suffix": "死亡特效",
                "asset_type": "effect",
                "priority": "P1",
                "complexity": "m",
            },
        ],
    }

    def convert(self, parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert every extracted entity into one or more art assets."""
        return self.convert_entities(extract_l5_entities(parsed))

    def convert_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert extracted or frozen design entities into art assets."""
        assets: list[dict[str, Any]] = []
        for entity in entities:
            for spec in self._asset_specs_for(entity):
                asset_type = _text(spec.get("asset_type"))
                priority = _text(spec.get("priority")) or self._priority_for(asset_type)
                asset = {
                    "asset_id": f"ENTITY-ASSET-{len(assets) + 1:03d}",
                    "name": self._asset_name(entity, _text(spec.get("suffix"))),
                    "asset_type": asset_type,
                    "source": entity.get("source", ""),
                    "source_entity_id": entity.get("entity_id"),
                    "source_node_id": entity.get("node_id"),
                    "purpose": self._purpose_for(entity, asset_type),
                    "dependencies": (
                        [entity.get("node_id")] if entity.get("node_id") else []
                    ),
                    "unlocks": ["program_requirements", "art_production"],
                    "priority": priority,
                    "complexity": _text(spec.get("complexity"))
                    or self._complexity_for(asset_type),
                    "required_for_phase": self._phase_for(entity),
                    "status": "requirement_defined",
                    "trace_kind": "design_entity",
                }
                if priority == "P0":
                    asset["resolution"] = self._resolution_for(asset_type)
                assets.append(asset)
        return assets

    def _asset_type_for(self, entity: dict[str, Any]) -> str:
        """Infer the best single asset type for fallback entities."""
        text = " ".join(
            _text(entity.get(key)).lower() for key in ("kind", "schema", "label")
        )
        if any(token in text for token in ("ui", "hud", "menu", "界面")):
            return "ui"
        if any(
            token in text
            for token in ("ability", "effect", "attack", "技能", "攻击", "特效")
        ):
            return "effect"
        if any(
            token in text for token in ("room", "level", "environment", "房间", "场景")
        ):
            return "environment"
        if any(token in text for token in ("audio", "sound", "音乐", "音效")):
            return "audio"
        if any(
            token in text
            for token in ("config", "resource", "currency", "配置", "资源")
        ):
            return "config"
        return "art_asset"

    def _asset_specs_for(self, entity: dict[str, Any]) -> list[dict[str, str]]:
        """Return multi-asset specs for core kinds, or one fallback spec."""
        kind = _text(entity.get("kind")).lower()
        if kind in self.MULTI_ASSET_MAP:
            return self.MULTI_ASSET_MAP[kind]
        asset_type = self._asset_type_for(entity)
        return [
            {
                "suffix": "",
                "asset_type": asset_type,
                "priority": self._priority_for(asset_type),
                "complexity": self._complexity_for(asset_type),
            }
        ]

    def _asset_name(self, entity: dict[str, Any], suffix: str) -> str:
        """Return a concise asset name from entity label and optional suffix."""
        label = _text(entity.get("label")) or _text(entity.get("entity_id"))
        return f"{label}_{suffix}" if suffix else label

    def _purpose_for(self, entity: dict[str, Any], asset_type: str) -> str:
        """Return production purpose text for one asset type."""
        label = entity.get("label") or entity.get("entity_id")
        if asset_type == "ui":
            return f"为实体“{label}”提供可读的界面呈现和状态反馈。"
        if asset_type == "effect":
            return f"为实体“{label}”提供动作、命中、奖励或状态变化特效。"
        if asset_type == "environment":
            return f"为实体“{label}”提供场景、房间或关卡视觉资源。"
        if asset_type == "config":
            return f"为实体“{label}”提供可配置图标、数据表现或资源标识。"
        return f"为 L5实体“{label}”提供生产可追踪的美术资产。"

    def _priority_for(self, asset_type: str) -> str:
        """Return default production priority for one asset type."""
        return "P0" if asset_type in {"ui", "effect", "art_asset"} else "P1"

    def _complexity_for(self, asset_type: str) -> str:
        """Return default complexity for one asset type."""
        if asset_type in {"ui", "config"}:
            return "s"
        if asset_type in {"effect", "environment"}:
            return "m"
        if asset_type == "animation":
            return "xl"
        return "xs"

    def _resolution_for(self, asset_type: str) -> str:
        """Return default resolution or format requirement for P0 assets."""
        if asset_type == "ui":
            return "1024x1024 source, scalable UI atlas export"
        if asset_type == "effect":
            return "2048x2048 sprite sheet or engine VFX prefab"
        if asset_type == "environment":
            return "3840x2160 concept source plus production slices"
        if asset_type == "animation":
            return "engine-ready animation set with source frames"
        return "2048x2048 layered source"

    def _phase_for(self, entity: dict[str, Any]) -> str:
        """Infer the implementation phase that needs this asset."""
        text = " ".join(
            _text(entity.get(key)).lower()
            for key in ("kind", "schema", "node_id", "label")
        )
        if any(
            token in text
            for token in (
                "release",
                "launch",
                "analytics",
                "telemetry",
                "release_build",
                "build_pipeline",
                "运营",
                "发布",
                "上线",
                "埋点",
                "数据分析",
            )
        ):
            return "launch_ops"
        if any(token in text for token in ("currency", "resource", "economy", "资源")):
            return "economy"
        if any(
            token in text
            for token in ("progress", "upgrade", "unlock", "成长", "升级", "解锁")
        ):
            return "progression"
        if any(token in text for token in ("room", "enemy", "content", "房间", "敌人")):
            return "content_ops"
        if any(
            token in text
            for token in ("social", "guild", "friend", "社交", "好友", "公会")
        ):
            return "social"
        return "core_playable"


class MarketResearchSkill:
    """Load local market references before falling back to deterministic guidance."""

    def local_fallback(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Return genre art references without using network access."""
        raw_text = _text(parsed.get("raw_text")).lower()
        genre_tokens = {
            "roguelike_action": ("hades", "rogue", "roguelike", "roguelite", "肉鸽"),
            "fps": ("fps", "shooter", "射击", "枪"),
            "puzzle": ("puzzle", "解谜", "match", "消除"),
        }
        matched_genre = ""
        for key, tokens in genre_tokens.items():
            if any(token in raw_text for token in tokens):
                matched_genre = key
                library = self._library_reference(key)
                if library:
                    return library
                break
        if matched_genre == "roguelike_action":
            references = [
                "高对比角色剪影",
                "可读性战斗特效",
                "神话题材环境层次",
                "清晰奖励图标",
            ]
            style = "stylized_action_readability"
        elif matched_genre == "fps":
            references = ["枪口反馈清晰", "目标轮廓可读", "命中特效不遮挡视野"]
            style = "readable_shooter_feedback"
        elif matched_genre == "puzzle":
            references = ["高可读棋盘", "渐进提示反馈", "色块状态区分"]
            style = "clean_puzzle_readability"
        else:
            references = ["核心动作反馈", "状态层级清晰", "关键资源图标可辨识"]
            style = "functional_game_readability"
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "mode": "local_fallback",
            "style_direction": style,
            "reference_principles": references,
            "network_used": False,
        }

    def _library_reference(self, key: str) -> dict[str, Any]:
        """Return a market-data reference from the local knowledge library."""
        aliases = {"roguelike_action": ("roguelike_action", "roguelike")}
        payload = {}
        for candidate in aliases.get(key, (key,)):
            payload = read_json(MARKET_DATA_DIR / f"{candidate}.json", {})
            if isinstance(payload, dict) and payload:
                break
        if not isinstance(payload, dict) or not payload:
            return {}
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "mode": "reference_library",
            "genre": payload.get("genre", key),
            "style_direction": payload.get("style_direction", ""),
            "art_style": payload.get("art_style", ""),
            "color_palette": payload.get("color_palette", []),
            "reference_principles": payload.get("reference_principles", []),
            "reference_games": payload.get("reference_games", []),
            "asset_benchmarks": payload.get("asset_benchmarks", {}),
            "network_used": False,
        }
