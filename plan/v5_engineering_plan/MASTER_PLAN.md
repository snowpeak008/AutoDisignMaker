# AutoDesignMaker — 工程化开发计划 v5.0

**创建日期**: 2026-06-23  
**评估基线**: 综合质量 55/100（Hades 存档实测）  
**计划目标**: 综合质量 ≥ 75/100  
**总工期**: 10 周

---

## 一、项目现状诊断

### 1.1 流水线质量基线（2026-06-23 实测）

| 步骤 | 指标 | 当前值 | 目标值 | 差距 |
|------|------|--------|--------|------|
| Step 00 | 问答覆盖率 | 40% | >60% | -20pp |
| Step 01 | core_loop 来源 | template_fallback | explicit | 未显式 |
| Step 02 | entity_coverage | 45.6% | >80% | -34.4pp |
| Step 03 | 系统绑定率 | 97.5% | >90% | ✅ |
| Step 03 | 占位符率 | 0% | <25% | ✅ |
| Step 04 | 资产数量 | 50 | >40 | ✅ |
| Step 05 | 警告数 | 4 | <15 | ✅ |
| Step 05/06 | 评审结果 | PASS | PASS | ✅ |
| **综合** | **质量** | **55/100** | **≥75/100** | **-20分** |

### 1.2 根因分析

**根因 A（最高优先级）**: DesignEngine 中无真实 L5 实体  
→ 所有47个实体均为 `local_selection_fallback`（合成实体），非游戏机制层面的真实对象（武器/角色/技能/房间）  
→ 直接导致 entity_coverage 45.6%，requirements/assets 质量受限

**根因 B**: Concept 层核心游戏设计问题未回答（CQ-005 ~ CQ-012）  
→ 核心循环、压力来源、奖励节奏、系统拆分均为空白  
→ Step 01 只能回退到品类模板，loop 不项目专属

**根因 C**: 步骤间数据流不够密实  
→ Step 01 推导的系统未被 Step 03 精确绑定  
→ 合成实体的 node_id 是 SEL-XXX 而非真实设计节点 ID

### 1.3 与目标分差的量化映射

| 提分路径 | 预期提分 | 优先级 |
|---------|---------|--------|
| 填入 L5 实体（≥40个）→ entity_coverage >80% | +8分 | P0 |
| 补充 CQ-005~012 答案 → 问答覆盖率 >60% | +5分 | P0 |
| Step 01 显式循环提取 → loop 项目专属 | +3分 | P1 |
| Step 03 需求从实体而非 selection 生成 | +4分 | P1 |
| 增加 Step 05/06 内容深度检查 | +3分 | P2 |

---

## 二、整体架构设计原则

### 2.1 分层职责（不可越层）

```
用户输入层   → DesignEngine UI（L1-L5 设计决策 + L5 实体）
              ↓ export_adapter.py 生成 concept/framework/design.md
导入层       → pipeline/step_XX/plugin.py run_import_step()
              ↓ 解析 source_artifacts/ 下的 MD 包
处理层       → pipeline/step_XX/helpers.py 业务处理类
              ↓ 结构化 JSON 输出
制品层       → sandbox/outputs/artifacts/stage_XX/*.json
              ↓ artifact reviewer + validator
归档层       → saves/{id}/workspace/outputs/
```

### 2.2 模块结构标准（每步骤强制遵循）

```
pipeline/step_NN_name/
├── plugin.py            # 编排层：仅做 run_import_step() + helpers 调用 + StageResult 组装
├── helpers.py           # 业务层：所有业务逻辑类（Processor/Validator/Generator 等）
├── data/                # 静态数据（questions/templates/references）
│   └── *.json
├── prompts/             # AI 提示词
│   └── main.txt
└── tests/               # 步骤级测试
    ├── unit/
    └── fixtures/
```

### 2.3 数据契约原则

- 步骤间通过 `sandbox/outputs/artifacts/stage_XX/*.json` 传递数据
- 每个输出文件须包含 `schema_version`、`generated_at`、`source` 字段
- 下游步骤通过文件路径读取，不允许直接调用上游步骤的 Python 类
- 所有 helpers.py 处理类只接受 `parsed: dict` 输入，不直接读文件

---

## 三、实施计划（10 周）

| 阶段 | 周次 | 主要目标 | 关键交付物 |
|------|------|---------|-----------|
| Phase 0 | Week 1 | 基础设施 + L5 实体填写指导 | 开发环境配置完成，L5实体录入规范文档 |
| Phase 1 | Weeks 2-4 | Step 00-02 完整业务逻辑 | entity_coverage >70%，问答覆盖率 >55% |
| Phase 2 | Weeks 5-7 | Step 03-04 质量提升 | 需求质量明显提升，资产分类更精细 |
| Phase 3 | Weeks 8-9 | 评审增强 + 集成优化 | 综合质量 >70/100 |
| Phase 4 | Week 10 | 多品类验证 | 3个品类全部通过 E2E 测试 |

详见 `phases/` 目录下各阶段详细计划。

---

## 四、验收标准

### 4.1 硬性指标（必须全部满足）

- [ ] entity_coverage_rate ≥ 0.75（75%）
- [ ] 问答覆盖率 ≥ 0.55（55%）
- [ ] core_loop source_kind = "explicit"（至少对有显式循环定义的项目）
- [ ] 单元测试覆盖率 ≥ 75%
- [ ] Step 05/06 对真实内容均返回 PASS
- [ ] 通过 mypy --strict + flake8

### 4.2 软性指标（努力达到）

- [ ] 综合质量 ≥ 75/100
- [ ] system_binding_rate ≥ 95%（当有真实系统数据时）
- [ ] 资产数量 ≥ 60（当有真实 L5 实体时）
- [ ] 步骤警告数 = 0（无 BLOCKER/CRITICAL）

---

## 五、关键依赖与风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 用户未填写 L5 实体 | entity_coverage 无法超过合成实体上限（~47%） | Phase 0 提供 L5 实体录入规范和示例 |
| DesignEngine L5 实体 schema 多样性 | 转换器覆盖不足 | GenericConverter 兜底，Phase 2 逐步扩展 |
| AI API 响应不稳定 | 问答补全回退到品类模板 | 重试3次 + 品类模板离线兜底 |
| PLAN-002 复现 | entity 再次丢失 | export_adapter 集成测试持续监控 |

---

## 六、目录索引

```
plan/v5_engineering_plan/
├── MASTER_PLAN.md              ← 本文件
├── architecture/
│   ├── 01_system_architecture.md
│   ├── 02_data_flow_contracts.md
│   └── 03_module_specifications.md
├── phases/
│   ├── phase_0_foundation.md
│   ├── phase_1_core.md
│   ├── phase_2_generation.md
│   ├── phase_3_quality.md
│   └── phase_4_validation.md
├── steps/
│   ├── step_00_idea_intake.md
│   ├── step_01_gameplay_framework.md
│   ├── step_02_design_freeze.md
│   ├── step_03_program_requirements.md
│   ├── step_04_art_requirements.md
│   └── step_05_06_reviews.md
├── standards/
│   ├── code_standards.md
│   ├── data_contracts.md
│   ├── testing_strategy.md
│   └── quality_gates.md
└── metrics/
    ├── kpi_baseline.md
    └── kpi_targets.md
```
