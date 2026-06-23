# KPI 基线（2026-06-23 Hades 实测）

## 当前质量快照

**测量时间**: 2026-06-23 19:04  
**存档**: save_20260623_190332_e0188e  
**综合质量**: 55/100

---

## 各步骤指标

### Step 00 — 创意收集

| 指标 | 当前值 | 备注 |
|------|--------|------|
| 总问题数 | 15 | |
| 已回答问题数 | 6 | |
| 未回答问题数 | 9 | |
| 问答覆盖率 | 40.0% | 恰好在目标线上 |
| 回答的问题域 | project(3), technology(1), risk(1), project(1) | 缺 core/systems/content/resources |
| fallback_used | false | 有真实 selections |

**未回答的关键问题**:
- CQ-005: 核心循环（无 "核心循环" item_type）
- CQ-006: 主要压力来源
- CQ-007: 奖励节奏
- CQ-008: 顶层系统拆分
- CQ-009: 核心内容对象
- CQ-010: 关键资源关系
- CQ-011: 运行时流程
- CQ-012: 反馈/UI/表现需求
- CQ-014: 开发阶段验证方式

---

### Step 01 — 玩法框架

| 指标 | 当前值 | 备注 |
|------|--------|------|
| core_loop 节点数 | 7 | 非空 ✅ |
| core_loop source_kind | template_fallback | 非 explicit ⚠️ |
| template_key | roguelike_action | 正确识别品类 ✅ |
| system_count | 7 | 在目标范围内 ✅ |
| definition_rate | 1.0 | ✅ |
| 显式系统数 | 1 | 名称含 "system_layer：" 前缀 ⚠️ |
| 模板系统数 | 6 | 质量良好 ✅ |

---

### Step 02 — 设计冻结

| 指标 | 当前值 | 备注 |
|------|--------|------|
| entity_count | 47 | 全为合成实体 ⚠️ |
| 真实 L5实体数 | 0 | 用户未填写 ❌ |
| concrete_node_count | 103 | 从 design_summary.node_count 读取 ✅ |
| covered_concrete_nodes | 47 | |
| entity_coverage_rate | 45.63% | 低于目标 80% ❌ |
| invalid_entities | 0 | ✅ |
| 实体 kind 分布 | design_selection(36), system(5), resource(4), ui(3), scene(1), character(1), ability(1) | |

---

### Step 03 — 程序需求

| 指标 | 当前值 | 备注 |
|------|--------|------|
| 需求总数 | 157 | ✅ |
| 系统绑定数 | 153 | |
| system_binding_rate | 97.5% | ✅ 超过目标 |
| 占位符需求数 | 0 | ✅ |
| placeholder_rate | 0% | ✅ |
| 绑定方式分布 | 未测量 | 推测大多为 design_node_dependency |
| 需求业务深度 | 低 | 大多为 "实现 L4 决策" 格式 ⚠️ |

---

### Step 04 — 美术需求

| 指标 | 当前值 | 备注 |
|------|--------|------|
| 资产总数 | 50 | ✅ 超过目标 40 |
| P0 资产数 | 未测量 | |
| P1 资产数 | 未测量 | |
| 资产类型分布 | 未测量（推测多为 config）| |
| 资产业务深度 | 低 | 资产名含设计决策长文本 ⚠️ |

---

### Step 05 — 程序评审

| 指标 | 当前值 | 备注 |
|------|--------|------|
| verdict | PASS | ✅ |
| BLOCKER 数 | 0 | ✅ |
| CRITICAL 数 | 0 | ✅ |
| WARNING 数 | 4 | ✅ (目标 <15) |
| WARNING 原因 | 全为 "not bound to a system" | REQ-001~004 无绑定 |
| allowed_to_enter_plan | true | ✅ |

---

### Step 06 — 美术评审

| 指标 | 当前值 | 备注 |
|------|--------|------|
| verdict | PASS | ✅ |
| 所有 items | 0 | 无任何问题 ✅ |

---

## 综合评分细分

| 步骤 | 权重 | 步骤得分 | 加权得分 |
|------|------|---------|---------|
| Step 00 | 15% | 42 | 6.3 |
| Step 01 | 20% | 60 | 12.0 |
| Step 02 | 20% | 40 | 8.0 |
| Step 03 | 20% | 65 | 13.0 |
| Step 04 | 15% | 58 | 8.7 |
| Step 05/06 | 10% | 78 | 7.8 |
| **合计** | **100%** | — | **55.8 ≈ 55** |
