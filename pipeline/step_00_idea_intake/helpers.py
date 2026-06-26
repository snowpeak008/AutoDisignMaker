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
        "CQ-011": "运行时流程：房间加载 -> 战斗清场 -> 奖励结算 -> 下一房间，由 room_state_machine 驱动。",
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
    "farming_sim": {
        "CQ-005": "核心循环：耕种播种 -> 照料作物 -> 收获出售 -> 购买升级 -> 扩展农场。",
        "CQ-006": "主要压力：时间管理、能量消耗、季节截止日和资金限制。",
        "CQ-007": "奖励节奏：每日收获、季末评分、社区关系提升和农场扩展解锁。",
        "CQ-008": "顶层系统：农业耕种、NPC关系、探索采集、工艺制作和时间日历系统。",
        "CQ-009": "核心内容对象：作物、NPC、农场建筑、工具、矿物和节日事件。",
        "CQ-010": "资源关系：金币收入、体力消耗、种子购买、工具升级和关系值投入。",
        "CQ-011": "运行时流程：每日开始 -> 农场操作 -> NPC交互 -> 资源消耗 -> 时间推进 -> 存档。",
        "CQ-012": "表现需求：农场视觉、作物生长状态、NPC头像、季节色调和 UI 日历。",
    },
    "card_game": {
        "CQ-005": "核心循环：抽牌 -> 打出卡牌 -> 结算效果 -> 消灭对手 -> 升级卡组。",
        "CQ-006": "主要压力：手牌质量、资源（法力/行动点）限制、对手压制和随机性。",
        "CQ-007": "奖励节奏：胜局奖励、卡包开箱、卡组构筑优化和段位晋升。",
        "CQ-008": "顶层系统：卡牌、费用、战场状态、卡组构筑和对战结算系统。",
        "CQ-009": "核心内容对象：卡牌、费用资源、英雄/角色、战场区域和卡包。",
        "CQ-010": "资源关系：费用生成、卡牌消耗、血量损耗和资源兑换。",
        "CQ-011": "运行时流程：回合开始 -> 资源补充 -> 打牌结算 -> 回合结束 -> 胜负判定。",
        "CQ-012": "表现需求：卡牌图案、打出动效、伤害数字、战场状态可读性和手牌布局。",
    },
    "bullet_heaven": {
        "CQ-005": "核心循环：自动攻击 -> 击杀敌人 -> 获得经验 -> 升级选择 -> 生存更久。",
        "CQ-006": "主要压力：敌人密度、精英/Boss波次、选择取舍和时间压力。",
        "CQ-007": "奖励节奏：升级选择、被动叠加、关卡结算奖励和局外成长解锁。",
        "CQ-008": "顶层系统：自动战斗、敌人生成、升级构筑、局外成长和关卡推进系统。",
        "CQ-009": "核心内容对象：角色、武器/被动、敌人、精英、Boss和升级选项。",
        "CQ-010": "资源关系：经验值、金币/宝石、武器进化条件和局外货币。",
        "CQ-011": "运行时流程：生成敌人 -> 自动攻击 -> 掉落经验 -> 升级选择 -> 时间计数 -> 结算。",
        "CQ-012": "表现需求：弹幕密度可读性、升级选项 UI、角色状态栏和 Boss 血条。",
    },
    "hypercasual": {
        "CQ-005": "核心循环：单指操作 -> 即时反馈 -> 得分/通过 -> 下一关/重试。",
        "CQ-006": "主要压力：反应速度、精准度和递增难度。",
        "CQ-007": "奖励节奏：每关通过、新高分、皮肤解锁和广告奖励。",
        "CQ-008": "顶层系统：核心机制、难度递增、得分统计和广告变现系统。",
        "CQ-009": "核心内容对象：核心操控单元、障碍/目标、关卡和得分。",
        "CQ-010": "资源关系：生命次数、广告获取复活和皮肤货币。",
        "CQ-011": "运行时流程：输入操作 -> 物理/规则响应 -> 碰撞检测 -> 结算/重试。",
        "CQ-012": "表现需求：核心操控反馈、障碍视觉区分和得分大字显示。",
    },
    "idle": {
        "CQ-005": "核心循环：挂机积累 -> 登录收取 -> 消费升级 -> 产出加速 -> 达成里程碑。",
        "CQ-006": "主要压力：等待时间、升级成本和产出瓶颈。",
        "CQ-007": "奖励节奏：离线收益、里程碑奖励、限时活动和突破重置。",
        "CQ-008": "顶层系统：生产链、升级树、离线计算、突破重置和活动系统。",
        "CQ-009": "核心内容对象：生产建筑/单位、货币层级、升级节点和里程碑。",
        "CQ-010": "资源关系：多层货币、生产速率、升级消耗和重置收益。",
        "CQ-011": "运行时流程：离线时间计算 -> 登录结算 -> 操作升级 -> 后台持续生产。",
        "CQ-012": "表现需求：产出数字动效、升级按钮状态、进度条和里程碑弹窗。",
    },
    "match3": {
        "CQ-005": "核心循环：观察棋盘 -> 滑动消除 -> 触发连锁 -> 完成目标 -> 下一关。",
        "CQ-006": "主要压力：步数限制、目标类型、障碍物和棋盘随机性。",
        "CQ-007": "奖励节奏：关卡通过、星级评定、道具奖励和新关卡解锁。",
        "CQ-008": "顶层系统：棋盘消除、目标达成、道具增强、关卡编辑和进度系统。",
        "CQ-009": "核心内容对象：方块/元素种类、道具、障碍、关卡目标和关卡包。",
        "CQ-010": "资源关系：步数消耗、道具费用、生命次数和关卡货币。",
        "CQ-011": "运行时流程：滑动输入 -> 匹配校验 -> 消除动画 -> 下落补充 -> 目标更新 -> 结算。",
        "CQ-012": "表现需求：元素颜色区分、消除特效、连锁动画和目标进度 UI。",
    },
    "souls_like": {
        "CQ-005": "核心循环：探索区域 -> 击败敌人 -> 积累魂值 -> 死亡/存入 -> 挑战Boss。",
        "CQ-006": "主要压力：高死亡惩罚、敌人攻击型态学习、耐力管理和路径记忆。",
        "CQ-007": "奖励节奏：敌人掉落、Boss击败里程碑、属性成长和区域开通。",
        "CQ-008": "顶层系统：战斗动作、耐力管理、属性成长、地图探索和货币存取系统。",
        "CQ-009": "核心内容对象：武器、防具、魂值、篝火/存档点、Boss和区域。",
        "CQ-010": "资源关系：魂值积累/损失、消耗品消耗、强化材料和传送解锁。",
        "CQ-011": "运行时流程：位置管理 -> 攻击判定 -> 耐力消耗 -> 受击结算 -> 死亡/复活流程。",
        "CQ-012": "表现需求：攻击音效反馈、受击硬直感、Boss动作预告和血量/耐力双条。",
    },
    "action_adventure": {
        "CQ-005": "核心循环：探索场景 -> 击败敌人 -> 推进叙事 -> 解锁新区域 -> 成长强化。",
        "CQ-006": "主要压力：战斗难度、叙事选择后果、资源管理和探索谜题。",
        "CQ-007": "奖励节奏：剧情推进、区域探索完成度、能力解锁和收集物。",
        "CQ-008": "顶层系统：战斗、叙事、探索、成长和任务追踪系统。",
        "CQ-009": "核心内容对象：角色、敌人、场景区域、任务节点、对话和收集物。",
        "CQ-010": "资源关系：弹药/消耗品、经验成长、货币消费和资源采集。",
        "CQ-011": "运行时流程：场景加载 -> 移动探索 -> 战斗触发 -> 结算 -> 剧情推进 -> 存档。",
        "CQ-012": "表现需求：场景光影、角色动作流畅度、UI 信息层级和叙事镜头。",
    },
    "survival_horror": {
        "CQ-005": "核心循环：探索环境 -> 管理资源 -> 回避/击败威胁 -> 解谜推进 -> 逃脱目标。",
        "CQ-006": "主要压力：弹药/道具匮乏、威胁强度、解谜障碍和逃脱时间窗口。",
        "CQ-007": "奖励节奏：安全区域到达、道具发现、区域清除和剧情解锁。",
        "CQ-008": "顶层系统：威胁 AI、资源管理、解谜机制、场景探索和存档系统。",
        "CQ-009": "核心内容对象：敌人类型、弹药道具、谜题、存档点和关键道具。",
        "CQ-010": "资源关系：弹药消耗、治疗品使用、存档墨水/资源和道具合成。",
        "CQ-011": "运行时流程：移动探索 -> 威胁感知 -> 战斗/回避决策 -> 资源结算 -> 推进状态。",
        "CQ-012": "表现需求：氛围音效、威胁视觉提示、资源栏紧张感和存档UI。",
    },
    "looter_shooter": {
        "CQ-005": "核心循环：进入任务 -> 战斗击败敌人 -> 拾取战利品 -> 强化角色 -> 挑战更高难度。",
        "CQ-006": "主要压力：敌人等级差距、弹药消耗、词条随机性和技能冷却。",
        "CQ-007": "奖励节奏：稀有武器掉落、任务完成奖励、赛季通行证和公会挑战。",
        "CQ-008": "顶层系统：射击战斗、战利品系统、角色成长、任务地图和社交组队系统。",
        "CQ-009": "核心内容对象：武器（品质/词条）、技能树、任务、地图区域和Boss。",
        "CQ-010": "资源关系：弹药消耗、货币兑换、强化材料和赛季货币。",
        "CQ-011": "运行时流程：任务加载 -> 战斗击杀 -> 掉落拾取 -> 结算强化 -> 下一任务。",
        "CQ-012": "表现需求：武器手感、命中反馈、掉落特效、词条对比 UI 和技能特效。",
    },
    "battle_royale": {
        "CQ-005": "核心循环：跳伞降落 -> 搜寻物资 -> 战斗对抗 -> 缩圈生存 -> 最终决战。",
        "CQ-006": "主要压力：物资质量差距、缩圈压力、敌方突袭和团队协作。",
        "CQ-007": "奖励节奏：击杀奖励、生存时长积分、赛季通行证和皮肤解锁。",
        "CQ-008": "顶层系统：物资搜刮、射击战斗、缩圈机制、载具和组队通信系统。",
        "CQ-009": "核心内容对象：武器、防具、消耗品、载具、地图区域和缩圈。",
        "CQ-010": "资源关系：弹药消耗、护甲耐久、治疗品和战利品分配。",
        "CQ-011": "运行时流程：跳伞落地 -> 物资搜寻 -> 遭遇战斗 -> 缩圈移动 -> 最终结算。",
        "CQ-012": "表现需求：缩圈边界提示、枪械手感、击倒/击杀反馈和小地图信息。",
    },
    "hero_shooter": {
        "CQ-005": "核心循环：选择英雄 -> 配合队友 -> 目标争夺 -> 技能组合 -> 赢得回合。",
        "CQ-006": "主要压力：英雄克制关系、团队配合缺口、技能时机和目标压力。",
        "CQ-007": "奖励节奏：回合胜利积分、赛季通行证、皮肤和高光集锦。",
        "CQ-008": "顶层系统：英雄技能、目标占点、团队组合、地图机制和回合结算系统。",
        "CQ-009": "核心内容对象：英雄（技能套件）、地图、目标点、Ultimate技能和皮肤。",
        "CQ-010": "资源关系：Ultimate充能、治疗资源、复活限制和赛季货币。",
        "CQ-011": "运行时流程：回合准备 -> 占点交战 -> 技能释放 -> 击杀复活 -> 目标结算。",
        "CQ-012": "表现需求：英雄技能特效区分、目标进度 UI、团队状态面板和击杀反馈。",
    },
    "mmorpg": {
        "CQ-005": "核心循环：接取任务 -> 击败怪物/探索 -> 获得经验/装备 -> 成长强化 -> 挑战副本。",
        "CQ-006": "主要压力：角色成长瓶颈、装备词条差距、副本协作要求和在线竞争。",
        "CQ-007": "奖励节奏：经验成长、装备掉落、每日任务奖励、赛季更新和公会活动。",
        "CQ-008": "顶层系统：战斗技能、任务系统、装备成长、副本组队、社交公会和经济市场系统。",
        "CQ-009": "核心内容对象：职业/角色、装备、技能树、任务、副本、NPC和玩家经济。",
        "CQ-010": "资源关系：经验、金币、装备材料、消耗品、绑定货币和交易行。",
        "CQ-011": "运行时流程：服务器同步 -> 任务状态 -> 战斗结算 -> 掉落分配 -> 成长记录 -> 存档。",
        "CQ-012": "表现需求：技能特效层级、装备外观、副本 UI、血条/仇恨条和世界聊天。",
    },
    "factory_sim": {
        "CQ-005": "核心循环：采集资源 -> 建造机器 -> 自动化生产 -> 解锁科技 -> 扩展产线。",
        "CQ-006": "主要压力：产线瓶颈、资源吞吐不平衡、电力/空间限制和科技依赖链。",
        "CQ-007": "奖励节奏：科技解锁、产线升级里程碑、自动化完成感和成就。",
        "CQ-008": "顶层系统：资源采集、传送带物流、机器加工、科技树和电力能源系统。",
        "CQ-009": "核心内容对象：资源种类、机器设备、传送带、科技节点和产品目标。",
        "CQ-010": "资源关系：原料输入、中间品转化、产品输出、能耗和运输效率。",
        "CQ-011": "运行时流程：物品生成 -> 传送带运输 -> 机器加工 -> 产品输出 -> 科技触发。",
        "CQ-012": "表现需求：传送带流向可读性、机器状态指示、资源图标区分和产线全局视图。",
    },
    "exploration": {
        "CQ-005": "核心循环：选择方向 -> 移动探索 -> 发现内容 -> 完成收集/支线 -> 扩展地图认知。",
        "CQ-006": "主要压力：方向感迷失、能量/补给限制和隐藏内容触发条件。",
        "CQ-007": "奖励节奏：新区域发现、收集物完成度、故事碎片和成就解锁。",
        "CQ-008": "顶层系统：移动探索、地图发现、NPC对话、收集系统和叙事推进系统。",
        "CQ-009": "核心内容对象：地图区域、收集物、NPC、路径节点和叙事碎片。",
        "CQ-010": "资源关系：体力/时间消耗、道具使用和地图解锁条件。",
        "CQ-011": "运行时流程：移动输入 -> 区域触发 -> 内容发现 -> 状态记录 -> 存档。",
        "CQ-012": "表现需求：地图雾化效果、探索进度指示、NPC 对话气泡和收集物高亮。",
    },
    "metroidvania": {
        "CQ-005": "核心循环：探索区域 -> 击败敌人/Boss -> 获得能力 -> 解锁新区域 -> 深入探索。",
        "CQ-006": "主要压力：能力门控阻挡、敌人挑战、平台精准度和路径记忆。",
        "CQ-007": "奖励节奏：新能力解锁、Boss击败、地图完成度和收集物。",
        "CQ-008": "顶层系统：动作战斗、能力成长、地图互联、Boss挑战和收集系统。",
        "CQ-009": "核心内容对象：能力道具、敌人、Boss、地图房间、收集物和存档点。",
        "CQ-010": "资源关系：生命上限、能力消耗、货币升级和地图解锁条件。",
        "CQ-011": "运行时流程：移动操作 -> 碰撞判定 -> 战斗结算 -> 能力触发 -> 地图状态更新。",
        "CQ-012": "表现需求：动作流畅感、地图连通视觉、能力反馈特效和 Boss 动作预告。",
    },
    "brawler": {
        "CQ-005": "核心循环：选择角色 -> 实时对战 -> 击败对手/目标 -> 获得奖励 -> 角色升级。",
        "CQ-006": "主要压力：角色克制、操作精准度、能量管理和地图机制。",
        "CQ-007": "奖励节奏：胜场奖励箱、角色解锁/升级、赛季奖励和俱乐部活动。",
        "CQ-008": "顶层系统：实时战斗、角色技能、地图模式、成长系统和赛季通行证系统。",
        "CQ-009": "核心内容对象：角色（技能套件）、地图、游戏模式、能量和皮肤。",
        "CQ-010": "资源关系：战斗能量、技能冷却、奖励箱货币和赛季点数。",
        "CQ-011": "运行时流程：匹配开始 -> 移动攻击 -> 技能释放 -> 击败结算 -> 奖励分发。",
        "CQ-012": "表现需求：角色技能特效区分、生命条可读性、地图目标指示和命中反馈。",
    },
}

GENRE_DETECTION_RULES = (
    ("roguelike_action", ("hades", "rogue", "roguelike", "roguelite", "肉鸽")),
    (
        "farming_sim",
        (
            "stardew",
            "farming",
            "farm",
            "harvest",
            "种田",
            "农场",
            "生活模拟",
            "life sim",
        ),
    ),
    (
        "card_game",
        (
            "deck",
            "card",
            "卡牌",
            "构筑卡组",
            "slay the spire",
            "clash royale",
            "marvel snap",
            "hearthstone",
            "炉石",
        ),
    ),
    (
        "bullet_heaven",
        (
            "vampire survivors",
            "survivor",
            "bullet heaven",
            "幸存者",
            "弹幕生存",
            "auto battle",
            "自动战斗",
        ),
    ),
    ("match3", ("match-3", "match3", "match 3", "消除", "royal match", "bejeweled")),
    (
        "hypercasual",
        (
            "hypercasual",
            "hyper casual",
            "超休闲",
            "flappy",
            "helix",
            "stack",
            "runner",
            "跑酷",
            "subway surfers",
            "crossy",
        ),
    ),
    ("idle", ("idle", "clicker", "incremental", "放置", "挂机", "coin master")),
    (
        "souls_like",
        (
            "souls",
            "soulslike",
            "souls-like",
            "elden ring",
            "sekiro",
            "dark souls",
            "魂系",
            "高难度动作",
        ),
    ),
    (
        "action_adventure",
        (
            "god of war",
            "last of us",
            "death stranding",
            "action adventure",
            "动作冒险",
            "叙事动作",
        ),
    ),
    ("survival_horror", ("survival horror", "resident evil", "生存恐怖", "恐怖射击")),
    (
        "looter_shooter",
        ("looter shooter", "looter-shooter", "borderlands", "掠夺射击", "战利品射击"),
    ),
    ("battle_royale", ("battle royale", "battle-royale", "apex", "吃鸡", "大逃杀")),
    (
        "hero_shooter",
        ("hero shooter", "valorant", "splatoon", "overwatch", "英雄射击", "团队射击"),
    ),
    (
        "mmorpg",
        (
            "mmorpg",
            "mmo",
            "world of warcraft",
            "wow",
            "final fantasy xiv",
            "ff14",
            "runescape",
            "大型多人在线",
            "网络游戏",
            "网游",
        ),
    ),
    ("factory_sim", ("factory", "factorio", "automation", "工厂", "自动化", "生产线")),
    (
        "exploration",
        (
            "exploration",
            "open world",
            "sandbox",
            "a short hike",
            "探索",
            "开放世界",
            "沙盒",
        ),
    ),
    (
        "metroidvania",
        (
            "metroidvania",
            "metroid",
            "castlevania",
            "dead cells",
            "hollow knight",
            "银河城",
            "动作平台",
        ),
    ),
    ("moba", ("moba", "推塔", "对线")),
    ("brawler", ("brawler", "brawl stars", "arena", "乱斗", "竞技场")),
    ("fps", ("fps", "shooter", "射击", "枪")),
    ("puzzle", ("puzzle", "match", "解谜", "消除")),
    ("strategy", ("strategy", "rts", "4x", "策略", "战棋")),
    ("rpg", ("rpg", "jrpg", "arpg", "role-playing", "角色扮演")),
)


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
    haystack = (
        raw_text + " " + " ".join(_selection_text(item) for item in selections)
    ).lower()
    for genre, tokens in GENRE_DETECTION_RULES:
        if any(token in haystack for token in tokens):
            return genre
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

    def _first_matching(
        self, selections: list[Any], tokens: tuple[str, ...]
    ) -> dict[str, Any]:
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
        if (
            any(token in lower for token in ("rpg", "jrpg", "arpg"))
            or "角色扮演" in raw_text
        ):
            return "接取目标 -> 探索战斗 -> 获得装备 -> 角色成长 -> 推进剧情"
        if any(
            token in lower for token in ("moba", "tower defense", "tower_defense")
        ) or any(token in raw_text for token in ("塔防", "推塔")):
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
        item_types = {
            _text(item).lower() for item in question.get("item_types", []) if item
        }
        keywords = [
            _text(item).lower() for item in question.get("keywords", []) if item
        ]
        evidence: list[dict[str, str]] = []
        for item in selections:
            item_type = _text(_field(item, "item_type")).lower()
            haystack = _selection_text(item).lower()
            if item_type in item_types or any(
                keyword in haystack for keyword in keywords
            ):
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
                    "match": (
                        "raw_text_multi_keyword" if len(raw_matches) > 1 else "raw_text"
                    ),
                }
            )
        if not evidence:
            genre = _genre_key(raw_text, selections)
            default_label = GENRE_DEFAULT_EVIDENCE.get(genre, {}).get(
                _text(question.get("id"))
            )
            if default_label:
                evidence.append(
                    {
                        "label": default_label,
                        "source": f"genre_template:{genre}",
                        "match": "genre_inference",
                    }
                )
        return evidence
