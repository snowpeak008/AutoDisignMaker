from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.design.gameplay_systems import DEFAULT_INTERVIEW_QUESTIONS, _normalize_weights

TEMPLATE_DIR = PROJECT_ROOT / "knowledge" / "design_data" / "project_templates"
GAMEPLAY_OPTIONS_PATH = PROJECT_ROOT / "knowledge" / "design_data" / "gameplay_system_options.json"


GAMEPLAY_PROFILE_GROUPS = {
    "iaa_reflex_or_puzzle": {
        "selected": ["input_control", "action_rule", "objective", "settlement", "content_delivery"],
        "weights": {
            "input_control": 25,
            "action_rule": 25,
            "objective": 20,
            "settlement": 15,
            "content_delivery": 15,
        },
        "loops": {
            "input_control": "{name}: 玩家通过{focus}的低门槛输入进入单局挑战。",
            "action_rule": "{name}: 核心规则把{focus}转化为可重复尝试的即时判断。",
            "objective": "{name}: 玩家围绕{focus}追求更高分数、过关或更远进度。",
            "settlement": "{name}: 每轮结果快速反馈成败、分数和重试动机。",
            "content_delivery": "{name}: 障碍、关卡或模式变化持续刷新{focus}的短循环。",
        },
    },
    "iaa_service_puzzle_economy": {
        "selected": [
            "action_rule",
            "objective",
            "settlement",
            "progression",
            "resource_economy",
            "social_competition",
            "content_delivery",
            "liveops_event",
        ],
        "weights": {
            "action_rule": 18,
            "objective": 12,
            "settlement": 10,
            "progression": 15,
            "resource_economy": 15,
            "social_competition": 10,
            "content_delivery": 12,
            "liveops_event": 8,
        },
        "loops": {
            "action_rule": "{name}: 玩家围绕{focus}做出关卡、消除或互动选择。",
            "objective": "{name}: 关卡目标和阶段任务驱动短期推进。",
            "settlement": "{name}: 单局结算把通关、失败和奖励承接到下一轮。",
            "progression": "{name}: 长期装饰、收藏或账号成长承接重复游玩。",
            "resource_economy": "{name}: 货币、道具和体力类资源调节{focus}节奏。",
            "social_competition": "{name}: 轻社交、排行或互访为进度提供外部目标。",
            "content_delivery": "{name}: 关卡包、活动目标和障碍组合持续补充内容。",
            "liveops_event": "{name}: 限时活动和版本节奏维持长期回访。",
        },
    },
    "action_roguelite": {
        "selected": [
            "input_control",
            "action_rule",
            "objective",
            "settlement",
            "progression",
            "buildcraft",
            "randomness",
            "meta_structure",
        ],
        "weights": {
            "input_control": 18,
            "action_rule": 22,
            "objective": 10,
            "settlement": 8,
            "progression": 12,
            "buildcraft": 12,
            "randomness": 12,
            "meta_structure": 6,
        },
        "loops": {
            "input_control": "{name}: 玩家通过{focus}的移动、瞄准或闪避形成手感门槛。",
            "action_rule": "{name}: 战斗规则把敌人模式、风险和收益压缩到连续决策。",
            "objective": "{name}: 房间、路线和首领目标推动每轮 run 前进。",
            "settlement": "{name}: 战斗和 run 结算把失败、奖励和下一次尝试闭合。",
            "progression": "{name}: 永久解锁或能力成长承接反复挑战。",
            "buildcraft": "{name}: 武器、技能或增益组合形成每局差异化构筑。",
            "randomness": "{name}: 随机房间、掉落和奖励选择制造重玩性。",
            "meta_structure": "{name}: 局内 run 与局外准备共同组织长期循环。",
        },
    },
    "deckbuilding_roguelike": {
        "selected": [
            "action_rule",
            "objective",
            "settlement",
            "buildcraft",
            "randomness",
            "resource_economy",
            "meta_structure",
        ],
        "weights": {
            "action_rule": 20,
            "objective": 10,
            "settlement": 10,
            "buildcraft": 25,
            "randomness": 15,
            "resource_economy": 10,
            "meta_structure": 10,
        },
        "loops": {
            "action_rule": "{name}: 回合规则、敌人意图和资源消耗驱动{focus}。",
            "objective": "{name}: 路线节点、精英和首领目标组织爬塔推进。",
            "settlement": "{name}: 战斗结算把奖励选择、损耗和失败重开闭合。",
            "buildcraft": "{name}: 卡牌、遗物和流派协同构成主要策略深度。",
            "randomness": "{name}: 地图、奖励池和遭遇随机性制造每局差异。",
            "resource_economy": "{name}: 能量、金币、药水和生命共同约束路线取舍。",
            "meta_structure": "{name}: 单局构筑和局外解锁承接长期重玩。",
        },
    },
    "platform_metroidvania": {
        "selected": [
            "input_control",
            "action_rule",
            "objective",
            "settlement",
            "progression",
            "buildcraft",
            "content_delivery",
        ],
        "weights": {
            "input_control": 25,
            "action_rule": 20,
            "objective": 15,
            "settlement": 10,
            "progression": 12,
            "buildcraft": 8,
            "content_delivery": 10,
        },
        "loops": {
            "input_control": "{name}: 玩家通过{focus}的移动、跳跃或攻击输入建立技巧表达。",
            "action_rule": "{name}: 敌人、平台和能力规则把操作转换成可学习挑战。",
            "objective": "{name}: 关卡、地图或 Boss 目标牵引探索与通关。",
            "settlement": "{name}: 检查点、死亡和战斗结果给出明确重试反馈。",
            "progression": "{name}: 能力、区域和收集成长逐步扩展可达空间。",
            "buildcraft": "{name}: 武器、能力或徽章组合提供局部构筑选择。",
            "content_delivery": "{name}: 地图、关卡和遭遇节奏持续投放{focus}内容。",
        },
    },
    "automation_sandbox_sim": {
        "selected": [
            "action_rule",
            "objective",
            "settlement",
            "progression",
            "buildcraft",
            "randomness",
            "resource_economy",
            "content_delivery",
            "meta_structure",
        ],
        "weights": {
            "action_rule": 15,
            "objective": 10,
            "settlement": 5,
            "progression": 10,
            "buildcraft": 20,
            "randomness": 5,
            "resource_economy": 25,
            "content_delivery": 5,
            "meta_structure": 5,
        },
        "loops": {
            "action_rule": "{name}: 玩家围绕{focus}执行建造、规划和调整规则。",
            "objective": "{name}: 生产、经营或探索目标组织长期推进。",
            "settlement": "{name}: 产出效率、阶段成果或日程结果反馈决策质量。",
            "progression": "{name}: 科技、能力或设施成长扩大可用策略。",
            "buildcraft": "{name}: 设施、路线和系统组合构成主要创造空间。",
            "randomness": "{name}: 地图、资源或事件变化让规划问题保持新鲜。",
            "resource_economy": "{name}: 资源产消、瓶颈和转换链条支撑核心深度。",
            "content_delivery": "{name}: 新区域、任务或生产目标持续提供阶段内容。",
            "meta_structure": "{name}: 长期规划层把短期产出承接成下一阶段目标。",
        },
    },
    "narrative_choice_management": {
        "selected": [
            "input_control",
            "action_rule",
            "objective",
            "settlement",
            "progression",
            "resource_economy",
            "social_competition",
            "content_delivery",
        ],
        "weights": {
            "input_control": 10,
            "action_rule": 15,
            "objective": 15,
            "settlement": 10,
            "progression": 15,
            "resource_economy": 10,
            "social_competition": 10,
            "content_delivery": 15,
        },
        "loops": {
            "input_control": "{name}: 玩家通过轻量操作进入{focus}的情境选择。",
            "action_rule": "{name}: 互动、对话或管理规则承载核心决策。",
            "objective": "{name}: 剧情、角色或经营目标推动阶段推进。",
            "settlement": "{name}: 选择结果、任务完成和关系变化形成反馈。",
            "progression": "{name}: 角色、关系或设施成长承接长期投入。",
            "resource_economy": "{name}: 时间、资源或情绪成本限制玩家取舍。",
            "social_competition": "{name}: 角色关系、社区互动或对抗表达外部反馈。",
            "content_delivery": "{name}: 剧情章节、任务和事件持续投放体验内容。",
        },
    },
    "midcore_competitive_service": {
        "selected": [
            "action_rule",
            "objective",
            "settlement",
            "progression",
            "buildcraft",
            "social_competition",
            "content_delivery",
            "liveops_event",
        ],
        "weights": {
            "action_rule": 20,
            "objective": 15,
            "settlement": 10,
            "progression": 10,
            "buildcraft": 15,
            "social_competition": 15,
            "content_delivery": 8,
            "liveops_event": 7,
        },
        "loops": {
            "action_rule": "{name}: 对局规则把{focus}转化为高频竞技判断。",
            "objective": "{name}: 胜负、区域或模式目标驱动每场对局。",
            "settlement": "{name}: 对局结算承接奖励、段位和再次匹配。",
            "progression": "{name}: 账号、角色或卡牌成长支撑中长期目标。",
            "buildcraft": "{name}: 阵容、卡组或角色选择形成策略准备层。",
            "social_competition": "{name}: 匹配、排行、联盟或异步竞争提供外部压力。",
            "content_delivery": "{name}: 模式、地图和挑战持续更新对局内容。",
            "liveops_event": "{name}: 赛季、活动和版本平衡维持回流。",
        },
    },
    "large_service_mmo_arpg": {
        "selected": [
            "action_rule",
            "objective",
            "settlement",
            "progression",
            "buildcraft",
            "resource_economy",
            "meta_structure",
            "social_competition",
            "content_delivery",
            "liveops_event",
        ],
        "weights": {
            "action_rule": 12,
            "objective": 8,
            "settlement": 7,
            "progression": 18,
            "buildcraft": 14,
            "resource_economy": 14,
            "meta_structure": 8,
            "social_competition": 8,
            "content_delivery": 6,
            "liveops_event": 5,
        },
        "loops": {
            "action_rule": "{name}: 战斗、任务或职业规则支撑{focus}的日常操作。",
            "objective": "{name}: 主线、赛季、地图和副本目标组织长期推进。",
            "settlement": "{name}: 掉落、评分和副本结果承接下一轮投入。",
            "progression": "{name}: 等级、装备、技能或账号成长形成长期追求。",
            "buildcraft": "{name}: 职业、技能、装备和流派构成深度构筑。",
            "resource_economy": "{name}: 货币、材料、交易和消耗维持长线经济。",
            "meta_structure": "{name}: 日常、周常和赛季结构组织回流节奏。",
            "social_competition": "{name}: 公会、组队、交易或排行提供社区目标。",
            "content_delivery": "{name}: 地图、副本、活动和任务持续投放内容。",
            "liveops_event": "{name}: 版本、赛季和运营活动维持长期服务节奏。",
        },
    },
}


TEMPLATE_GAMEPLAY_PROFILES = {
    "builtin_3a_axiom_verge": {"group": "platform_metroidvania", "focus": "武器变体、地图探索和能力门控"},
    "builtin_3a_blasphemous": {"group": "platform_metroidvania", "focus": "硬核近战、处决反馈和暗黑地图探索"},
    "builtin_3a_celeste": {"group": "platform_metroidvania", "focus": "精准跳跃、冲刺节奏和高难关卡路线"},
    "builtin_3a_cuphead": {"group": "platform_metroidvania", "focus": "Boss 模式识别、弹幕闪避和武器输出窗口"},
    "builtin_3a_ori_and_the_blind_forest": {"group": "platform_metroidvania", "focus": "流畅移动、能力解锁和电影化关卡推进"},
    "builtin_3a_shovel_knight": {"group": "platform_metroidvania", "focus": "铲击动作、平台节奏和章节式冒险"},
    "builtin_3a_spiritfarer": {"group": "narrative_choice_management", "focus": "船上经营、角色关系和告别叙事"},
    "builtin_3a_terraria": {"group": "automation_sandbox_sim", "focus": "探索、采集、建造和 Boss 阶段推进"},
    "builtin_3a_undertale": {"group": "narrative_choice_management", "focus": "非暴力选择、弹幕回避和角色关系反馈"},
    "builtin_iaa_hypercasual_2048": {"group": "iaa_reflex_or_puzzle", "focus": "数字滑动、合并规划和高分追求"},
    "builtin_iaa_hypercasual_coin_master": {"group": "iaa_service_puzzle_economy", "focus": "老虎机抽取、村庄成长和社交攻防"},
    "builtin_iaa_hypercasual_crossy_road": {"group": "iaa_reflex_or_puzzle", "focus": "车道观察、跳跃时机和无尽前进"},
    "builtin_iaa_hypercasual_cut_the_rope": {"group": "iaa_reflex_or_puzzle", "focus": "绳索切割、物理摆动和糖果投喂"},
    "builtin_iaa_hypercasual_flappy_bird": {"group": "iaa_reflex_or_puzzle", "focus": "单键上升、障碍间隙和高频重试"},
    "builtin_iaa_hypercasual_fruit_ninja": {"group": "iaa_reflex_or_puzzle", "focus": "手势切割、连击节奏和炸弹规避"},
    "builtin_iaa_hypercasual_jetpack_joyride": {"group": "iaa_reflex_or_puzzle", "focus": "喷气高度控制、障碍闪避和金币收集"},
    "builtin_iaa_hypercasual_royal_match": {"group": "iaa_service_puzzle_economy", "focus": "三消目标、道具组合和房间装饰推进"},
    "builtin_iaa_hypercasual_stickman_hook": {"group": "iaa_reflex_or_puzzle", "focus": "钩索摆荡、释放时机和关卡冲刺"},
    "builtin_indie_celeste": {"group": "platform_metroidvania", "focus": "精准平台、冲刺路线和情绪化关卡节奏"},
    "builtin_indie_dead_cells": {"group": "action_roguelite", "focus": "横版战斗、武器流派和随机关卡推进"},
    "builtin_indie_enter_the_gungeon": {"group": "action_roguelite", "focus": "俯视射击、弹幕闪避和武器组合"},
    "builtin_indie_factorio": {"group": "automation_sandbox_sim", "focus": "自动化产线、资源瓶颈和科技扩张"},
    "builtin_indie_hades": {"group": "action_roguelite", "focus": "高速战斗、Boon 协同和逃脱路线选择"},
    "builtin_indie_hades_l5_complete": {"group": "action_roguelite", "focus": "高速战斗、Boon 协同和逃脱路线选择"},
    "builtin_indie_hades_l5_partial": {"group": "action_roguelite", "focus": "高速战斗、Boon 协同和逃脱路线选择"},
    "builtin_indie_hollow_knight": {"group": "platform_metroidvania", "focus": "手绘地图探索、精准战斗和护符构筑"},
    "builtin_indie_slay_the_spire": {"group": "deckbuilding_roguelike", "focus": "出牌顺序、卡组构筑和遗物协同"},
    "builtin_indie_stardew_valley": {"group": "automation_sandbox_sim", "focus": "农场经营、日程规划和社区关系"},
    "builtin_indie_the_binding_of_isaac_rebirth": {"group": "action_roguelite", "focus": "房间战斗、道具协同和随机路线"},
    "builtin_indie_vampire_survivors": {"group": "action_roguelite", "focus": "自动攻击、走位生存和武器进化"},
    "builtin_large_service_maplestory": {"group": "large_service_mmo_arpg", "focus": "横版职业成长、刷怪循环和社群长期目标"},
    "builtin_large_service_old_school_runescape": {"group": "large_service_mmo_arpg", "focus": "技能成长、任务探索和玩家社区驱动"},
    "builtin_large_service_path_of_exile": {"group": "large_service_mmo_arpg", "focus": "技能宝石、天赋树和赛季刷装循环"},
    "builtin_large_service_ragnarok_online": {"group": "large_service_mmo_arpg", "focus": "职业转职、组队刷怪和交易社群"},
    "builtin_large_service_warframe": {"group": "large_service_mmo_arpg", "focus": "战甲收集、装备构筑和版本活动回流"},
    "builtin_midcore_brawl_stars": {"group": "midcore_competitive_service", "focus": "英雄技能、短局对战和多模式竞技"},
    "builtin_midcore_clash_royale": {"group": "midcore_competitive_service", "focus": "卡组构筑、双路攻防和实时对战节奏"},
    "builtin_midcore_marvel_snap": {"group": "midcore_competitive_service", "focus": "卡牌构筑、三地形博弈和快速对局"},
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _option_ids() -> set[str]:
    return {
        str(option.get("id"))
        for option in _load_json(GAMEPLAY_OPTIONS_PATH).get("options", [])
        if option.get("id")
    }


def _format_core_loops(group: dict, profile: dict, name: str) -> dict[str, str]:
    focus = profile["focus"]
    loops = {}
    for system_id in group["selected"]:
        template = group["loops"][system_id]
        loops[system_id] = template.format(name=name, focus=focus)
    return loops


def _build_gameplay_systems(template_id: str, name: str) -> dict:
    profile = TEMPLATE_GAMEPLAY_PROFILES[template_id]
    group = GAMEPLAY_PROFILE_GROUPS[profile["group"]]
    selected = list(group["selected"])
    return {
        "schemaVersion": "1.0",
        "selected": selected,
        "custom": [],
        "weights": _normalize_weights(group["weights"], selected),
        "coreLoops": _format_core_loops(group, profile, name),
        "interview": {
            "questions": list(DEFAULT_INTERVIEW_QUESTIONS),
            "answers": [],
            "parsedSystemIds": [],
        },
    }


def _validate_profiles() -> None:
    option_ids = _option_ids()
    for group_name, group in GAMEPLAY_PROFILE_GROUPS.items():
        selected = group["selected"]
        missing_options = set(selected) - option_ids
        if missing_options:
            raise ValueError(f"{group_name} references unknown options: {sorted(missing_options)}")
        missing_weights = set(selected) - set(group["weights"])
        if missing_weights:
            raise ValueError(f"{group_name} missing weights: {sorted(missing_weights)}")
        missing_loops = set(selected) - set(group["loops"])
        if missing_loops:
            raise ValueError(f"{group_name} missing core loops: {sorted(missing_loops)}")
        weights = _normalize_weights(group["weights"], selected)
        total = sum(entry["weight"] for entry in weights.values())
        if total != 100:
            raise ValueError(f"{group_name} normalized weight total is {total}")


def main() -> int:
    _validate_profiles()
    template_paths = sorted(TEMPLATE_DIR.glob("builtin_*.json"))
    template_ids = {path.stem for path in template_paths}
    profile_ids = set(TEMPLATE_GAMEPLAY_PROFILES)
    missing_profiles = sorted(template_ids - profile_ids)
    stale_profiles = sorted(profile_ids - template_ids)
    if missing_profiles:
        raise ValueError(f"Missing template gameplay profiles: {missing_profiles}")
    if stale_profiles:
        raise ValueError(f"Stale template gameplay profiles: {stale_profiles}")

    for path in template_paths:
        payload = _load_json(path)
        meta = payload.get("template", {})
        name = str(meta.get("gameName") or meta.get("name") or path.stem)
        project_state = payload.setdefault("projectState", {})
        project_state["gameplaySystems"] = _build_gameplay_systems(path.stem, name)
        _write_json(path, payload)

    print(f"[OK] Updated gameplaySystems for {len(template_paths)} builtin templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
