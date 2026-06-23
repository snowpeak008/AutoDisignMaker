# Step 04 — 美术需求 实施指南

## 现状评估

| 指标 | 当前值 | 目标 |
|------|--------|------|
| 资产总数 | 50 | ≥ 80（有真实 L5 实体时）|
| 资产类型 | 多为 config | ui+effect+environment 均有 |
| 资产名称质量 | 含 L4 决策长文本 | 简洁的游戏对象名 |
| P0 资产数 | 未测量 | ≥ 20% 比例 |

---

## 资产类型映射规范

### `_asset_type_for()` 优先级（高→低）

```
ui       ← kind/schema/label 含 ui/hud/menu/界面
effect   ← kind/schema/label 含 ability/effect/attack/技能/攻击/特效
environment ← kind/schema/label 含 room/level/environment/房间/场景
audio    ← kind/schema/label 含 audio/sound/音乐/音效
config   ← kind/schema/label 含 config/resource/currency/配置/资源
art_asset ← 其他（fallback）
```

### 当前问题

Hades 合成实体大多为 `design_selection` kind，关键词匹配到 `config`，导致资产类型过于单一。  
**根本原因**: 同样是合成实体质量问题，依赖用户填写真实 L5 实体解决。

---

## 多资产生成（Phase 2）

当实体为特定 kind 时，生成多条资产：

```python
MULTI_ASSET_MAP = {
    "character": [
        {"suffix": "_原画",    "asset_type": "art_asset",   "priority": "P0", "complexity": "l"},
        {"suffix": "_动画集",  "asset_type": "animation",   "priority": "P0", "complexity": "xl"},
        {"suffix": "_UI头像",  "asset_type": "ui",          "priority": "P1", "complexity": "s"},
    ],
    "weapon": [
        {"suffix": "_武器原画",  "asset_type": "art_asset", "priority": "P0", "complexity": "m"},
        {"suffix": "_攻击特效",  "asset_type": "effect",    "priority": "P0", "complexity": "m"},
        {"suffix": "_图标",      "asset_type": "ui",        "priority": "P1", "complexity": "s"},
    ],
    "ability": [
        {"suffix": "_施放特效",  "asset_type": "effect",    "priority": "P0", "complexity": "l"},
        {"suffix": "_命中特效",  "asset_type": "effect",    "priority": "P0", "complexity": "m"},
        {"suffix": "_技能图标",  "asset_type": "ui",        "priority": "P1", "complexity": "s"},
    ],
    "room": [
        {"suffix": "_场景原画",  "asset_type": "environment","priority": "P0", "complexity": "xl"},
        {"suffix": "_地块集",    "asset_type": "environment","priority": "P0", "complexity": "l"},
        {"suffix": "_环境音效",  "asset_type": "audio",     "priority": "P1", "complexity": "m"},
    ],
    "enemy": [
        {"suffix": "_角色原画",  "asset_type": "art_asset", "priority": "P0", "complexity": "l"},
        {"suffix": "_攻击特效",  "asset_type": "effect",    "priority": "P0", "complexity": "m"},
        {"suffix": "_死亡特效",  "asset_type": "effect",    "priority": "P1", "complexity": "m"},
    ],
}
```

---

## market_data 参考库结构

**路径**: `knowledge/market_data/roguelike.json`

```json
{
  "genre": "roguelike_action",
  "art_style": "stylized_action_readability",
  "color_palette": ["高对比度", "清晰可读", "动感配色"],
  "style_direction": "角色轮廓清晰、特效高对比、UI极简",
  "reference_principles": [
    "角色剪影在任何背景下可辨识",
    "攻击特效帧间隔适合高速战斗节奏",
    "奖励图标色彩层级分明（金/银/铜）"
  ],
  "reference_games": [
    {"name": "Hades", "art_style": "神话题材高对比", "notable_elements": ["角色轮廓", "特效层次", "UI紧凑"]},
    {"name": "Dead Cells", "art_style": "像素高对比", "notable_elements": ["流畅动画", "打击感特效"]}
  ],
  "asset_benchmarks": {
    "character_art": 8,
    "enemy_art": 15,
    "vfx": 30,
    "ui": 25,
    "environment": 10
  }
}
```

---

## 实施检查清单

- [ ] Phase 2: 实现 MULTI_ASSET_MAP 多资产生成
- [ ] Phase 2: 创建 `knowledge/market_data/roguelike.json`
- [ ] Phase 2: MarketResearchSkill 优先读取参考库，fallback 时记录 `mode = "local_fallback"`
- [ ] 验证 Hades 存档 Step 04 资产中 effect/ui/environment 类型均有
- [ ] 单元测试：character/weapon/ability 实体各产生正确数量资产
