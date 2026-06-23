# Step 02 — 设计冻结 实施指南

## 现状评估

| 指标 | 当前值 | 目标 |
|------|--------|------|
| entity_coverage_rate | 45.6% | ≥ 80% |
| 真实 L5 实体数 | 0 | ≥ 40（用户填写）|
| 合成实体数 | 47 | — |
| invalid_entities | 0 | 0 |
| entity_id 序号 | 有跳号（SEL索引） | 连续 ENT-001 起 |

---

## 提升路径分析

### 路径 A（高价值，依赖用户）: 填写真实 L5 实体

用户在 DesignEngine 中为核心节点填写 L5 实体后：
- `item_type = "L5实体"` 的 selection 数量增加
- `extract_l5_entities` 走真实路径而非 `_synthetic_entities`
- 每个真实实体有明确的 `kind`（weapon/character/ability/room）
- entity_coverage_rate 从 45.6% 提升至 80%+

**用户操作指南**: 参见 `knowledge/governance/L5_ENTITY_GUIDE.md`

### 路径 B（中价值，纯代码）: 改善合成实体质量

即使用户不填 L5 实体，也可提升合成实体的种类分布：

**修复 entity_id 连续性问题**:
```python
def extract_l5_entities(parsed: dict) -> list[dict]:
    entities = []
    l5_index = 0  # 只对 L5实体 计数
    for item in parsed.get("selections", []):
        if _text(_field(item, "item_type")) != "L5实体":
            continue
        l5_index += 1
        entities.append({
            "entity_id": f"ENT-{l5_index:03d}",  # 连续编号
            ...
        })
    return entities or _synthetic_entities(parsed)
```

**改善合成实体 kind 分布**（补充关键词）:
```python
def _entity_kind_for(item: Any) -> str:
    text = ...
    if any(token in text for token in ("weapon", "武器", "sword", "剑", "枪", "弓")):
        return "weapon"
    if any(token in text for token in ("enemy", "boss", "monster", "敌人", "首领", "怪物")):
        return "enemy"
    # ... 现有规则
```

---

## 关键函数说明

### `_expected_node_count(parsed, entities)`

**优先级**（从高到低）:
1. `parsed["design_summary"]["node_count"]`（来自 export_adapter 写入）
2. `parsed["design_node_count"]`
3. `parsed["expected_total"]`
4. 合成回退数量（entities 有 inference → 选择数量）
5. 覆盖节点数（最差情况，导致 coverage=1.0，BUG-007 残留）

**BUG-007 修复**: 第5级兜底应报告为数据不足，而非返回 covered 数量：
```python
# 当无法确定 expected_total 时，记录警告并返回一个保守估计
# 而不是用 covered_nodes 数量（会导致 coverage=1.0）
return max(len(concrete_nodes) * 3, 30)  # 保守估计：至少3倍已覆盖节点
```

---

## GraphGenerator 环检测说明

**当前实现**: DFS + visiting 集合，已修复 BUG-005（末尾节点重复）

**节点类型**:
- `type = "system"`: 来自 system_graph.nodes
- `type = "entity"`: 来自 entity_report.entities
- `type = "design_node"`: 被实体依赖但不在系统图中的节点

**当前数据特点**: 所有合成实体的 `dependencies = []`，因此无边可形成环。只有真实 L5 实体（有 `dependencies`）时才会形成有意义的依赖图。

---

## 实施检查清单

- [ ] 修复 entity_id 连续编号（L5实体计数，非全 selection 计数）
- [ ] 补充 `_entity_kind_for` 的 weapon/enemy 关键词
- [ ] 修复 BUG-007 的最终兜底逻辑（返回保守估计而非 covered 数量）
- [ ] 补充 `launch_ops` 阶段的分类关键词（Phase 分类器覆盖所有6个阶段）
- [ ] 验证 Hades 存档 entity_coverage_report.json 中 invalid_entities = 0
