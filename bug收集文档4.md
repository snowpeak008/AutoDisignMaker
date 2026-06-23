# Bug 收集文档（第四轮）

**扫描时间**: 2026-06-23  
**前提**: 第三轮5个 bug 已全部修复

---

## BUG-015 — 中等 | step_00 `_genre_key` 未覆盖 step_01 新增的品类

**文件**: `pipeline/step_00_idea_intake/helpers.py:64`  
**函数**: `_genre_key` + `GENRE_DEFAULT_EVIDENCE`

`step_01` `_pick_template_key` 支持 `strategy`、`rpg`、`moba` 三个新品类，但 `step_00` 的 `_genre_key` 只返回 `roguelike_action`、`fps`、`puzzle` 或 `""`：

```python
def _genre_key(raw_text, selections) -> str:
    ...
    if any(token in haystack for token in ("strategy", "rts", ...)): # ← 缺失
        return "strategy"
    ...
    return ""   # strategy/rpg/moba 游戏全部落到空字符串
```

`_genre_key` 返回 `""` → `GENRE_DEFAULT_EVIDENCE.get("")` = `{}` → 问答引擎对这些品类无法使用 genre_inference，所有 CQ-005~012 证据全为空。

**结果**:
- Strategy 游戏在 step_01 能推导出正确系统（5个），但 step_00 问答覆盖率仍为极低值（仅靠显式 selection 匹配）
- 相同数据在不同品类下表现差异很大，行为不一致

**修复**:
1. `_genre_key` 补充 strategy/rpg/moba 识别
2. `GENRE_DEFAULT_EVIDENCE` 补充对应品类的默认证据

```python
# _genre_key 补充:
if any(token in haystack for token in ("strategy", "rts", "4x", "策略", "战棋")):
    return "strategy"
if any(token in haystack for token in ("rpg", "jrpg", "arpg", "角色扮演")):
    return "rpg"
if any(token in haystack for token in ("moba", "推塔", "对线")):
    return "moba"

# GENRE_DEFAULT_EVIDENCE 补充:
"strategy": {
    "CQ-005": "核心循环：规划部署 -> 执行操作 -> 观察结果 -> 调整策略。",
    "CQ-006": "主要压力：资源竞争、单位损耗、时间窗口和对手压制。",
    "CQ-008": "顶层系统：单位、地图、经济、AI 和战斗解算系统。",
}
```

---

## BUG-016 — 低 | step_04 品类键名与 step_01 不一致

**文件**: `pipeline/step_04_art_requirements/helpers.py:196`  
**对比**: `pipeline/step_01_gameplay_framework/helpers.py:64`

```python
# step_01 _pick_template_key 返回:
"roguelike_action"   # ← 含 "_action" 后缀

# step_04 MarketResearchSkill.genre_tokens 键名:
"roguelike"          # ← 无后缀
```

两个模块对同一品类使用不同字符串。当前不影响功能（两者独立使用自己的键），但如果将来有代码直接使用 step_01 的 `template_key` 输出去查询 step_04 市场库，就会找不到数据（`"roguelike_action"` ≠ `"roguelike"`）。

**修复**: 统一使用 `"roguelike_action"`，或在 step_04 中接受两个键名（别名）。

---

## BUG-017 — 低 | CQ-013/CQ-014 `item_types` 过窄，在典型设计文档中几乎不可能被回答

**文件**: `pipeline/step_00_idea_intake/data/core_questions.json`

```json
{"id": "CQ-013", "item_types": ["技术"], "keywords": ["技术", "引擎", "配置", "数据", "性能"]}
{"id": "CQ-014", "item_types": ["生产", "QA"],  "keywords": ["阶段", "验收", "测试", "QA", "里程碑"]}
```

Hades 模板（和大多数 L4 设计文档）中不包含 "技术"、"生产"、"QA" 类型的选项，也不包含 "引擎"、"里程碑" 等关键词。这两个问题在实际运行中几乎永远显示 `answered: false`，拖低覆盖率但无法通过正常设计流程补全。

**修复**: 补充来自实际 L4 设计决策中出现的 item_types 和 keywords：

```json
{"id": "CQ-013", 
 "item_types": ["技术", "平台范围", "运营模式", "商业模式", "项目规模"],
 "keywords": ["技术", "引擎", "配置", "平台", "性能", "indie", "买断", "离线"]}
{"id": "CQ-014", 
 "item_types": ["生产", "QA", "项目规模", "社交模式"],
 "keywords": ["阶段", "验收", "测试", "QA", "里程碑", "成长", "解锁", "成就"]}
```

---

## 汇总

| ID | 严重程度 | 文件 | 问题简述 |
|----|---------|------|---------|
| BUG-015 | 中等 | `step_00/helpers.py:64` + `core_questions.json` | strategy/rpg/moba 品类无 genre_inference，与 step_01 行为不对称 |
| BUG-016 | 低 | `step_04/helpers.py:196` | 品类键 "roguelike" vs step_01 的 "roguelike_action" 不一致 |
| BUG-017 | 低 | `step_00/data/core_questions.json` | CQ-013/CQ-014 keywords 在实际设计文档中几乎无法匹配 |
