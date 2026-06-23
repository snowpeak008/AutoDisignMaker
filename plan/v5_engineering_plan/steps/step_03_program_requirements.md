# Step 03 — 程序需求 实施指南

## 现状评估

| 指标 | 当前值 | 目标 |
|------|--------|------|
| 需求总数 | 157 | ≥ 150（保持），≥ 200（有真实实体时）|
| system_binding_rate | 97.5% | ≥ 95% |
| placeholder_rate | 0% | 0% |
| 需求业务深度 | 低（L4 决策格式）| 高（L5 实体格式）|
| unmatched 需求数 | 4 | 0 |

---

## 需求质量提升策略

### 当前需求格式（L4决策驱动）

```json
{
  "requirement": "实现并验证"项目规模：indie"：Hades 项目配置。",
  "acceptance": "可通过配置、运行流程或人工检查证明已按来源实现。"
}
```

### 目标需求格式（L5实体驱动）

```json
{
  "requirement": "实现 L5实体"短剑"的武器输入、命中、伤害和反馈。",
  "acceptance": "实体"短剑"有可执行数据结构、运行时行为和至少一条验证路径。"
}
```

**关键差异**: 目标格式包含具体游戏机制词汇（命中/伤害/反馈），可直接指导开发。

---

## SCHEMA_ROUTES 扩展计划

### 当前（7种）
```python
SCHEMA_ROUTES = {
    "character": "角色行为、状态和交互",
    "enemy":     "敌人行为、攻击模式和生成条件",
    "weapon":    "武器输入、命中、伤害和反馈",
    "ability":   "技能触发、效果、冷却和组合规则",
    "room":      "房间生成、遭遇配置和出口规则",
    "resource":  "资源产出、消耗、存储和展示",
    "ui":        "界面状态、输入反馈和信息层级",
}
```

### Phase 2 扩展（+5种）
```python
SCHEMA_ROUTES.update({
    "scene":     "场景视觉、环境交互和氛围构建",
    "config":    "配置参数、数据表和平衡调整接口",
    "audio":     "音效触发条件、音量控制和混音规则",
    "system":    "系统初始化、事件管理和模块间通信",
    "narrative": "叙事触发条件、对话树和剧情状态",
})
```

---

## 多需求生成（Phase 2 实现）

当实体为核心类型时，生成多条需求而非一条：

```python
MULTI_REQ_TEMPLATES = {
    "weapon": [
        ("输入响应", "实现{label}的输入响应、攻击触发和手感反馈"),
        ("命中判定", "实现{label}的命中检测、伤害计算和击退效果"),
        ("视觉音效", "实现{label}的攻击动画、命中特效和音效触发"),
    ],
    "ability": [
        ("触发冷却", "实现{label}的施放条件、冷却管理和资源消耗"),
        ("效果执行", "实现{label}的目标选取、效果计算和状态施加"),
        ("视觉反馈", "实现{label}的施放动画、命中特效和UI图标更新"),
    ],
    "character": [
        ("属性初始化", "实现{label}的属性数据结构、基础值和成长曲线"),
        ("状态行为", "实现{label}的状态机、行为驱动和决策逻辑"),
        ("受击死亡", "实现{label}的受击反应、死亡处理和重生/复活逻辑"),
    ],
}
```

---

## SystemBinder 绑定质量监控

### 当前绑定分布（推测）

大多数需求走 `design_node_dependency` 路径（`system_id = "SEL-XXX"`），而非实际系统 ID（`SYS-COMBAT`）。  
这是因为合成实体的 `node_id = SEL-XXX`，而系统的 `id = SYS-COMBAT`，两者无法精确匹配。

### 目标绑定分布（有真实 L5 实体时）

真实 L5 实体的 `dependencies = ["weapon_node"]`，而 Step 01 的系统中可能有 `id = "weapon_node"` 或通过 fuzzy match 关联到 `SYS-COMBAT`。

### 验证命令

```python
from collections import Counter
methods = Counter(r["system_binding"]["method"] for r in requirements)
print(methods)
# 目标: {"dependency_id": N, "design_node_dependency": M, "fuzzy_name": K, "unmatched": 0}
```

---

## 实施检查清单

- [ ] 扩展 SCHEMA_ROUTES 至 12 种（+scene/config/audio/system/narrative）
- [ ] Phase 2 实现 MULTI_REQ_TEMPLATES（weapon/ability/character 各3条）
- [ ] 验证 REQ-001~004 的 unmatched 问题（这些来自无 dependencies 的合成实体）
- [ ] 单元测试：每种 SCHEMA_ROUTES key 各1个转换用例
