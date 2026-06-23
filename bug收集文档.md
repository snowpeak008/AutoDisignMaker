# Bug 收集文档

**扫描时间**: 2026-06-23  
**扫描范围**: pipeline/step_00-05/helpers.py + core/design/export_adapter.py

---

## BUG-001 — 严重 | AttributeError 崩溃

**文件**: `core/design/export_adapter.py:204`  
**函数**: `_framework_markdown_from_project_state`

```python
# 当前（错误）：trailing comma 使默认值缺失，等价于 .get("coreLoops")，返回 None
core_loops = gameplay.get("coreLoops", )

# 下面这行在 core_loops is None 时崩溃
loops = [core_loops.get(sid, "") for sid in selected if core_loops.get(sid)]
# AttributeError: 'NoneType' object has no attribute 'get'
```

**修复**: `gameplay.get("coreLoops", )` → `gameplay.get("coreLoops", {})`

---

## BUG-002 — 严重 | EntityValidator 覆盖率永远为 1.0

**文件**: `pipeline/step_02_design_review_freeze/helpers.py:109-121`  
**函数**: `EntityValidator.validate`

```python
missing_entities: list[dict[str, str]] = []   # 初始化后从未被填充

covered_nodes = len(concrete_nodes)
total_nodes = covered_nodes + len(missing_entities)  # = covered_nodes + 0
coverage_rate = covered_nodes / total_nodes           # = 1.0 永远
```

`missing_entities` 始终是空列表，导致 `total_nodes == covered_nodes`，`coverage_rate` 永远是 `1.0`。PLAN-002 的验证（entity_coverage ≥ 38%）会无条件通过，掩盖真实问题。

**修复方向**: `validate()` 需要接收预期的总节点数（如来自 DesignEngine 的 `design_node_count`）作为分母，或在方法签名中增加 `expected_total: int` 参数，用 `covered / expected_total` 计算覆盖率。

---

## BUG-003 — 中等 | SystemDeducer 切片逻辑无效（无法限制系统数量上限）

**文件**: `pipeline/step_01_gameplay_framework/helpers.py:90`  
**函数**: `SystemDeducer.deduce`

```python
systems = systems[: max(5, len(systems))]
# max(5, n) >= n 永远成立，切片等同于 systems[:]，完全没有截断效果
```

当模板补充后 systems 超过合理数量（比如8个），不会被截断，也不会保证最小值。

**修复**: 明确写出上下限，例如 `systems[:8]`（仅设上限），或根据设计意图调整。

---

## BUG-004 — 中等 | 模糊匹配阈值过低导致虚假绑定

**文件**: `pipeline/step_03_program_requirements/helpers.py:103`  
**函数**: `SystemBinder._best_binding`

```python
if best_score >= 0.18:   # 0.18 极低，几乎任意两段文本都能超过此阈值
    return {"system_id": best_id, "confidence": round(best_score, 4), "method": "fuzzy_name"}
```

`SequenceMatcher.ratio()` 对于完全无关的中英文混合文本（如"实现 L5实体战士的角色行为" vs "SYS-001 combat"）也会轻易超过 0.18，导致几乎所有需求都被 fuzzy 匹配，`system_binding_rate` 虚高，掩盖真实绑定质量问题。

**修复**: 合理阈值应在 `0.35`~`0.45` 区间，或对中英文分别处理。

---

## BUG-005 — 低 | 环路表示末尾节点重复

**文件**: `pipeline/step_02_design_review_freeze/helpers.py:197`  
**函数**: `GraphGenerator._cycles`

```python
# path 在调用时已经是 path + [target]，所以 path 末尾已经是 node_id
cycles.append(path[path.index(node_id):] + [node_id])
# 对于 A→B→A 环路，path=["A","B","A"]，结果是 ["A","B","A","A"]，末尾 A 重复两次
```

产生的环路表示如 `["A","B","A","A"]`，最后节点重复。虽不影响 `cycle_free` 判断，但如果下游消费这个列表会得到错误的环路成员。

**修复**: 去掉末尾追加 `[node_id]`，或改为 `path[path.index(node_id):]`（末尾已含 node_id）。

---

## BUG-006 — 低 | `blocking_issue_count` 语义错误

**文件**: `pipeline/step_05_program_review/helpers.py:117`  
**函数**: `IntelligentReviewer._report`

```python
"blocking_issue_count": counts.get("BLOCKER", 0) + counts.get("CRITICAL", 0),
```

设计计划规定只有 BLOCKER 才停止流水线，CRITICAL 需要人工确认后继续。将两者合并为 `blocking_issue_count` 会导致任何 CRITICAL 问题都被误判为"阻断"，且字段名产生歧义。

**修复**: 分开输出 `blocker_count` 和 `critical_count`，或将字段改名为 `requires_action_count`，并在流水线判断处只检查 `BLOCKER`。

---

## 汇总

| ID | 严重程度 | 文件 | 行号 | 问题简述 |
|----|---------|------|------|---------|
| BUG-001 | 严重 | `core/design/export_adapter.py` | 204 | `get("coreLoops", )` → None → AttributeError 崩溃 |
| BUG-002 | 严重 | `step_02/helpers.py` | 109-121 | `missing_entities` 恒空，coverage 永远 1.0 |
| BUG-003 | 中等 | `step_01/helpers.py` | 90 | `systems[:max(5, len)]` 无截断效果 |
| BUG-004 | 中等 | `step_03/helpers.py` | 103 | fuzzy 阈值 0.18 过低，虚假绑定 |
| BUG-005 | 低 | `step_02/helpers.py` | 197 | 环路末尾节点重复 |
| BUG-006 | 低 | `step_05/helpers.py` | 117 | BLOCKER+CRITICAL 合并为 blocking_issue_count 语义错误 |
