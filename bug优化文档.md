# Bug 优化文档（第二轮）

**扫描时间**: 2026-06-23  
**前提**: 第一轮6个 bug 已全部修复

---

## BUG-007 — 中等 | `_expected_node_count` 最终回退仍使覆盖率为 1.0

**文件**: `pipeline/step_02_design_review_freeze/helpers.py:131`  
**函数**: `_expected_node_count`

```python
# 最后一行兜底回退：
return len({item["node_id"] for item in entities if item.get("node_id")})
```

此表达式与 `validate()` 中 `covered_nodes` 的计算完全相同：

```python
# validate() 中：
concrete_nodes = sorted({item["node_id"] for item in entities if item.get("node_id")})
covered_nodes = len(concrete_nodes)          # = N
expected_total = _expected_node_count(...)   # 最终回退也 = N
coverage_rate = covered_nodes / total_nodes  # = N/N = 1.0
```

触发条件：`parsed` 中没有 `design_summary.node_count`、`design_node_count`、`expected_total` 等字段，且所有实体均为真实 L5实体（非 synthetic）。  
这正是正常完整项目数据的典型情况，导致覆盖率永远报告 1.0，BUG-002 的逻辑在此路径下残留。

**修复方向**: 最终回退应使用设计引擎的已知总节点数，或从 `parsed` 的顶层字段中读取 `total_design_nodes`（由 `generation.py` 写入），而非用实体自身的 node_id 集合大小。

---

## BUG-008 — 低 | `_load_templates()` 每次调用读两次磁盘

**文件**: `pipeline/step_01_gameplay_framework/helpers.py:59, 88`  
**函数**: `LoopExtractor.extract`、`SystemDeducer.deduce`

```python
# 两处均使用相同模式：
template = _load_templates().get(template_key, _load_templates().get("generic", {}))
#           ↑ 第一次读文件                       ↑ 若 key 缺失则第二次读文件
```

`_load_templates()` 每次调用都打开并解析 `genre_templates.json`。当 `template_key` 不存在于文件时，触发第二次 I/O。虽然不影响正确性，但每次 `LoopExtractor.extract()` 或 `SystemDeducer.deduce()` 调用最多产生两次磁盘读取。

**修复**:

```python
templates = _load_templates()
template = templates.get(template_key) or templates.get("generic", {})
```

---

## BUG-009 — 低 | `requires_action_count` 漏计 BLOCKER

**文件**: `pipeline/step_05_program_review/helpers.py:121`  
**函数**: `IntelligentReviewer._report`

```python
"requires_action_count": critical_count,   # 只统计 CRITICAL，忽略 BLOCKER
"blocking_issue_count": blocker_count,
```

BLOCKER 是最严重级别，同样需要人工介入处理，却被排除在 `requires_action_count` 之外。若调用方用 `requires_action_count > 0` 来判断"是否需要关注"，会在只有 BLOCKER 而无 CRITICAL 时得到 `0`，误判为无需人工处理。

**修复**:

```python
"requires_action_count": blocker_count + critical_count,
```

---

## 汇总

| ID | 严重程度 | 文件 | 问题简述 |
|----|---------|------|---------|
| BUG-007 | 中等 | `step_02/helpers.py:131` | `_expected_node_count` 最终回退 = covered，覆盖率仍为 1.0 |
| BUG-008 | 低 | `step_01/helpers.py:59,88` | `_load_templates()` 每次最多读两次磁盘 |
| BUG-009 | 低 | `step_05/helpers.py:121` | `requires_action_count` 漏计 BLOCKER |
