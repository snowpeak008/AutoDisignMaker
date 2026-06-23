from __future__ import annotations

from pathlib import Path
from typing import Any

from core.io import now_iso, read_json


CORE_QUESTIONS_PATH = Path(__file__).with_name("data") / "core_questions.json"

GENRE_DEFAULT_EVIDENCE = {
    "roguelike_action": {
        "CQ-005": "核心循环：进入房间 -> 战斗清场 -> 选择奖励 -> 构筑成长 -> 挑战首领。",
        "CQ-006": "主要压力：房间战斗、敌人组合、死亡重开和资源取舍。",
        "CQ-007": "奖励节奏：清场奖励、构筑选择、局内强化和局外永久成长。",
        "CQ-008": "顶层系统：即时战斗、房间推进、奖励选择、构筑成长和局外成长。",
        "CQ-009": "核心内容对象：武器、敌人、技能/祝福、房间、资源和首领。",
        "CQ-010": "资源关系：清场奖励、货币消耗、升级解锁和构筑收益。",
        "CQ-012": "表现需求：攻击反馈、命中特效、奖励图标、房间可读性和战斗 UI。",
    },
    "fps": {
        "CQ-005": "核心循环：发现目标 -> 移动占位 -> 射击消灭 -> 获取装备 -> 完成目标。",
        "CQ-006": "主要压力：敌方火力、位置暴露、弹药消耗和目标时间窗口。",
        "CQ-008": "顶层系统：射击、移动、装备、目标和生成系统。",
    },
    "puzzle": {
        "CQ-005": "核心循环：观察局面 -> 尝试操作 -> 获得反馈 -> 解锁下一关。",
        "CQ-006": "主要压力：规则理解、步数限制、错误反馈和渐进难度。",
        "CQ-007": "奖励节奏：解开谜题、获得星级/收集物、解锁新规则和新关卡。",
        "CQ-008": "顶层系统：谜题规则、输入操作、反馈、提示和关卡推进。",
        "CQ-009": "核心内容对象：谜题关卡、机关、规则块、提示和章节。",
        "CQ-010": "资源关系：提示次数、步数限制、关卡解锁和星级评价。",
        "CQ-011": "运行时流程：输入操作、规则校验、状态变化、反馈展示和通关结算。",
        "CQ-012": "表现需求：棋盘可读性、错误反馈、提示动画和状态区分。",
    },
    "strategy": {
        "CQ-005": "核心循环：规划部署 -> 执行操作 -> 观察结果 -> 调整策略 -> 争夺胜利。",
        "CQ-006": "主要压力：资源竞争、单位损耗、时间窗口和对手压制。",
        "CQ-007": "奖励节奏：控制区域、积累资源、科技升级和战术优势扩大。",
        "CQ-008": "顶层系统：单位、地图、经济、AI 和战斗解算系统。",
        "CQ-009": "核心内容对象：单位、建筑、地图区域、资源点和科技。",
        "CQ-010": "资源关系：采集、消耗、生产、科技解锁和维护成本。",
        "CQ-011": "运行时流程：下达指令、单位执行、战斗结算、资源刷新和胜负判定。",
        "CQ-012": "表现需求：单位轮廓、地图态势、选择反馈和战斗信息层级。",
    },
    "rpg": {
        "CQ-005": "核心循环：接取目标 -> 探索遭遇 -> 战斗解谜 -> 获得装备 -> 角色成长。",
        "CQ-006": "主要压力：角色强度、资源消耗、敌人难度和剧情选择后果。",
        "CQ-007": "奖励节奏：经验、装备、技能点、任务奖励和剧情推进。",
        "CQ-008": "顶层系统：任务、角色成长、战斗、背包装备和叙事系统。",
        "CQ-009": "核心内容对象：角色、敌人、任务、装备、技能和剧情节点。",
        "CQ-010": "资源关系：经验、货币、消耗品、装备强化和技能解锁。",
        "CQ-011": "运行时流程：任务状态、遭遇触发、战斗结算、掉落和存档。",
        "CQ-012": "表现需求：角色状态 UI、技能反馈、装备图标和剧情对话呈现。",
    },
    "moba": {
        "CQ-005": "核心循环：选择角色 -> 对线发育 -> 争夺资源 -> 团战推进 -> 摧毁目标。",
        "CQ-006": "主要压力：对线压制、视野缺失、团战时机和经济差距。",
        "CQ-007": "奖励节奏：经验金币、装备成型、地图资源和目标推进。",
        "CQ-008": "顶层系统：英雄、兵线地图、团战、经济和目标系统。",
        "CQ-009": "核心内容对象：英雄、技能、装备、兵线、防御塔和地图资源。",
        "CQ-010": "资源关系：经验、金币、装备购买、地图资源和复活时间。",
        "CQ-011": "运行时流程：匹配开局、对线、资源刷新、团战结算和胜负判定。",
        "CQ-012": "表现需求：技能范围、血条状态、地图提示、击杀反馈和团队 UI。",
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _field(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _selection_text(item: Any) -> str:
    return " ".join(
        _text(_field(item, name))
        for name in ("item_type", "option", "purpose", "layer_title", "source_ref")
    )


def _selection_label(item: Any) -> str:
    label = _field(item, "label", "")
    if label:
        return _text(label)
    item_type = _text(_field(item, "item_type"))
    option = _text(_field(item, "option"))
    return f"{item_type}: {option}" if item_type else option


def _selection_source(item: Any) -> str:
    return _text(_field(item, "source_ref") or _field(item, "source"))


def _genre_key(raw_text: str, selections: list[Any]) -> str:
    """Return a known genre key when context is explicit enough."""
    haystack = (raw_text + " " + " ".join(_selection_text(item) for item in selections)).lower()
    if any(token in haystack for token in ("hades", "rogue", "roguelike", "roguelite", "肉鸽")):
        return "roguelike_action"
    if any(token in haystack for token in ("fps", "shooter", "射击", "枪")):
        return "fps"
    if any(token in haystack for token in ("puzzle", "match", "解谜", "消除")):
        return "puzzle"
    if any(token in haystack for token in ("strategy", "rts", "4x", "策略", "战棋")):
        return "strategy"
    if any(token in haystack for token in ("rpg", "jrpg", "arpg", "role-playing", "角色扮演")):
        return "rpg"
    if any(token in haystack for token in ("moba", "推塔", "对线")):
        return "moba"
    return ""


class ConceptProcessor:
    """Build a structured concept profile from parsed design selections."""

    def build_profile(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Extract positioning, loop, constraints, and key systems."""
        selections = [item for item in parsed.get("selections", []) if item]
        raw_text = _text(parsed.get("raw_text"))
        profile = {
            "schema_version": 1,
            "generated_at": now_iso(),
            "source": _text(parsed.get("source")),
            "project_positioning": self._first_matching(
                selections, ("项目定位", "游戏类型", "玩法想法")
            ),
            "core_loop": self._first_matching(selections, ("核心循环",)),
            "key_constraints": self._matching_items(
                selections,
                ("平台", "商业模式", "技术", "约束", "资源"),
                limit=8,
            ),
            "key_systems": self._matching_items(
                selections,
                ("system_layer", "玩法系统", "系统图", "游戏系统"),
                limit=8,
            ),
            "selected_item_count": len(selections),
            "fallback_used": not bool(selections),
        }
        if not profile["project_positioning"]:
            profile["project_positioning"] = {
                "label": raw_text[:80] or "待补充项目定位",
                "source": _text(parsed.get("source")) or "fallback",
                "confidence": "fallback",
            }
        if not profile["core_loop"]:
            profile["core_loop"] = {
                "label": self._fallback_loop(raw_text),
                "source": _text(parsed.get("source")) or "fallback",
                "confidence": "fallback",
            }
        return profile

    def _first_matching(self, selections: list[Any], tokens: tuple[str, ...]) -> dict[str, Any]:
        """Return the first selection matching any token."""
        items = self._matching_items(selections, tokens, limit=1)
        return items[0] if items else {}

    def _matching_items(
        self, selections: list[Any], tokens: tuple[str, ...], *, limit: int
    ) -> list[dict[str, Any]]:
        """Return normalized selections whose text contains any token."""
        result: list[dict[str, Any]] = []
        for item in selections:
            haystack = _selection_text(item)
            if not any(token.lower() in haystack.lower() for token in tokens):
                continue
            result.append(
                {
                    "label": _selection_label(item),
                    "source": _selection_source(item),
                    "confidence": "explicit",
                }
            )
            if len(result) >= limit:
                break
        return result

    def _fallback_loop(self, raw_text: str) -> str:
        """Return a deterministic genre fallback loop."""
        lower = raw_text.lower()
        if "rogue" in lower or "肉鸽" in raw_text or "Roguelike" in raw_text:
            return "进入战斗 -> 获得奖励 -> 构筑成长 -> 挑战下一房间"
        if any(token in lower for token in ("strategy", "rts", "4x")) or any(
            token in raw_text for token in ("策略", "战棋")
        ):
            return "规划部署 -> 执行操作 -> 观察结果 -> 调整策略 -> 争夺胜利"
        if any(token in lower for token in ("rpg", "jrpg", "arpg")) or "角色扮演" in raw_text:
            return "接取目标 -> 探索战斗 -> 获得装备 -> 角色成长 -> 推进剧情"
        if any(token in lower for token in ("moba", "tower defense", "tower_defense")) or any(
            token in raw_text for token in ("塔防", "推塔")
        ):
            return "部署/选路 -> 对抗敌方 -> 获取资源 -> 升级构筑 -> 推进目标"
        if "puzzle" in lower or "解谜" in raw_text:
            return "观察局面 -> 尝试操作 -> 获得反馈 -> 解锁下一谜题"
        if "fps" in lower or "射击" in raw_text:
            return "发现目标 -> 移动射击 -> 占领空间 -> 获取装备"
        return "理解目标 -> 执行核心动作 -> 获得反馈 -> 推进下一目标"


class QuestionEngine:
    """Evaluate core question coverage from selections and raw text."""

    def __init__(self, questions_path: Path = CORE_QUESTIONS_PATH) -> None:
        raw_questions = read_json(questions_path, [])
        self.questions = raw_questions if isinstance(raw_questions, list) else []

    def evaluate(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Return structured question coverage for a parsed design document."""
        selections = [item for item in parsed.get("selections", []) if item]
        raw_text = _text(parsed.get("raw_text"))
        evaluated = []
        for question in self.questions:
            evidence = self._evidence_for(question, selections, raw_text)
            evaluated.append(
                {
                    "id": _text(question.get("id")),
                    "domain": _text(question.get("domain")),
                    "question": _text(question.get("question")),
                    "answered": bool(evidence),
                    "evidence": evidence[:5],
                }
            )
        answered = sum(1 for item in evaluated if item["answered"])
        total = len(evaluated)
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "source": _text(parsed.get("source")),
            "total_questions": total,
            "answered_questions": answered,
            "unanswered_questions": total - answered,
            "coverage_rate": round(answered / total, 4) if total else 0.0,
            "target_coverage_rate": 0.55,
            "needs_ai_supplement": bool(total and answered / total < 0.4),
            "questions": evaluated,
        }

    def _evidence_for(
        self,
        question: dict[str, Any],
        selections: list[Any],
        raw_text: str,
    ) -> list[dict[str, str]]:
        """Find selection or raw-text evidence for one coverage question."""
        item_types = {_text(item).lower() for item in question.get("item_types", []) if item}
        keywords = [_text(item).lower() for item in question.get("keywords", []) if item]
        evidence: list[dict[str, str]] = []
        for item in selections:
            item_type = _text(_field(item, "item_type")).lower()
            haystack = _selection_text(item).lower()
            if item_type in item_types or any(keyword in haystack for keyword in keywords):
                evidence.append(
                    {
                        "label": _selection_label(item),
                        "source": _selection_source(item),
                        "match": "selection",
                    }
                )
        raw_lower = raw_text.lower()
        raw_matches = [keyword for keyword in keywords if keyword in raw_lower]
        minimum_matches = 2 if len(keywords) >= 3 else 1
        if not evidence and len(raw_matches) >= minimum_matches:
            evidence.append(
                {
                    "label": raw_text[:120],
                    "source": "raw_text",
                    "match": "raw_text_multi_keyword" if len(raw_matches) > 1 else "raw_text",
                }
            )
        if not evidence:
            genre = _genre_key(raw_text, selections)
            default_label = GENRE_DEFAULT_EVIDENCE.get(genre, {}).get(_text(question.get("id")))
            if default_label:
                evidence.append(
                    {
                        "label": default_label,
                        "source": f"genre_template:{genre}",
                        "match": "genre_inference",
                    }
                )
        return evidence
