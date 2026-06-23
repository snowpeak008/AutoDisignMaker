# Step 00 — 创意收集 实施指南

## 现状评估

| 指标 | 当前值 | 目标 |
|------|--------|------|
| 问答覆盖率 | 40% | ≥ 60% |
| 未回答关键问题 | CQ-005~012（9题）| 0 题 |
| core_loop evidence | 无 | 有 |
| fallback_used | false | false |

---

## 核心类说明

### `ConceptProcessor.build_profile()`

**职责**: 从 `parsed.selections` 中匹配项目定位、核心循环和约束条件。

**当前问题**: `_matching_items` 的 tokens 覆盖不足，无法匹配 Hades 项目中的 "system_layer" 条目。

**修复动作**:
```python
# 在 build_profile 中增加"系统"相关提取
"key_systems": self._matching_items(
    selections,
    ("system_layer", "玩法系统", "系统图", "游戏系统"),
    limit=8,
),
```

---

### `QuestionEngine.evaluate()`

**职责**: 对每个问题判断是否有 evidence，计算覆盖率。

**当前问题**: 部分问题的 `item_types` 和 `keywords` 覆盖不足。

**data/core_questions.json 需更新的条目**:

```json
[
  {
    "id": "CQ-005",
    "domain": "core",
    "question": "核心循环是否明确？",
    "item_types": ["核心循环", "core_loop", "主循环", "Loop", "游戏循环"],
    "keywords": ["循环", "loop", "->", "→", "进入", "战斗", "奖励", "升级", "挑战"]
  },
  {
    "id": "CQ-008",
    "domain": "systems",
    "question": "顶层系统拆分是否明确？",
    "item_types": ["system_layer", "玩法系统", "系统图", "Layer 3", "游戏系统"],
    "keywords": ["系统", "system", "模块", "战斗系统", "经济系统", "成长系统"]
  },
  {
    "id": "CQ-009",
    "domain": "content",
    "question": "核心内容对象有哪些？",
    "item_types": ["L5实体", "content_type_decision", "character_unit_decision", "item_resource"],
    "keywords": ["武器", "角色", "敌人", "技能", "房间", "物品", "weapon", "enemy", "ability"]
  }
]
```

---

## 输出文件规范

### concept_profile.json

```json
{
  "schema_version": 1,
  "generated_at": "ISO8601",
  "source": "...concept.md",
  "project_positioning": {
    "label": "indie 独立游戏，buyout 买断制",
    "source": "concept.md:7",
    "confidence": "explicit"
  },
  "core_loop": {
    "label": "进入战斗 -> 获得奖励 -> 构筑成长",
    "source": "concept.md:XX",
    "confidence": "explicit|fallback"
  },
  "key_constraints": [...],
  "key_systems": [...],
  "selected_item_count": 20,
  "fallback_used": false
}
```

### core_question_coverage_report.json

```json
{
  "schema_version": 1,
  "total_questions": 15,
  "answered_questions": 9,
  "coverage_rate": 0.60,
  "target_coverage_rate": 0.40,
  "questions": [...]
}
```

---

## 实施检查清单

- [ ] `data/core_questions.json` 更新 CQ-005、CQ-008、CQ-009 的 item_types 和 keywords
- [ ] `build_profile` 增加 `key_systems` 字段提取
- [ ] 运行 Hades 存档 Step 00，验证 coverage_rate ≥ 0.55
- [ ] 验证 CQ-005 和 CQ-008 从 Hades 的 system_layer 条目中找到 evidence

---

## 与其他步骤的接口

**输出到 Step 01**: `design_extraction.json`（含 selections + raw_text）  
**Step 01 使用**: `LoopExtractor.extract(parsed)` — `parsed` 即 `design_extraction.json` 内容
