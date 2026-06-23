# 质量门禁（Quality Gates）

## 一、流水线质量门禁体系

每个步骤输出须通过所在层的质量门禁，才允许进入下一步骤。

```
Step 00 → [Gate-00] → Step 01 → [Gate-01] → Step 02 → [Gate-02]
       → Step 03 → [Gate-03] → Step 04 → [Gate-04]
       → Step 05/06 → [Final-Gate]
```

---

## 二、各步骤门禁定义

### Gate-00（Step 00 输出验证）

| 检查项 | 规则 | 失败处理 |
|--------|------|---------|
| design_extraction.json 存在 | 必须 | BLOCK（停止） |
| selections 非空 | 推荐 | WARN（继续，记录 fallback_used） |
| coverage_rate ≥ 0.40 | 推荐 | WARN（继续，记录覆盖率不足） |
| source 字段非空 | 必须 | WARN |

### Gate-01（Step 01 输出验证）

| 检查项 | 规则 | 失败处理 |
|--------|------|---------|
| core_loop.json 非空（loop 列表 ≥ 1 项）| 必须 | BLOCK |
| system_definitions.json 存在 | 必须 | BLOCK |
| system_count ≥ 1 | 必须 | WARN |
| definition_rate ≥ 0.6 | 推荐 | WARN |

### Gate-02（Step 02 输出验证）

| 检查项 | 规则 | 失败处理 |
|--------|------|---------|
| entity_coverage_report.json 存在 | 必须 | BLOCK |
| entity_count ≥ 1 | 必须 | BLOCK |
| entity_coverage_rate > 0 | 必须 | WARN |
| invalid_entities 为空 | 推荐 | WARN（记录无效实体）|
| cycle_free = true（依赖图）| 推荐 | WARN |

### Gate-03（Step 03 输出验证）

| 检查项 | 规则 | 失败处理 |
|--------|------|---------|
| program_requirements_contract.json 存在 | 必须 | BLOCK |
| requirements 非空 | 必须 | BLOCK → 触发 Step 05 BLOCKER |
| placeholder_rate ≤ 0.5 | 必须 | BLOCK → 触发 Step 05 BLOCKER |
| system_binding_rate ≥ 0.5 | 推荐 | WARN |

### Gate-04（Step 04 输出验证）

| 检查项 | 规则 | 失败处理 |
|--------|------|---------|
| asset_registry.json 存在 | 必须 | BLOCK |
| asset_count ≥ 1 | 必须 | BLOCK → 触发 Step 06 BLOCKER |
| P0 资产数量 ≥ 1 | 推荐 | WARN |

### Final-Gate（Step 05/06 综合评审）

| 检查项 | 规则 | 处理 |
|--------|------|------|
| ProgReview_report.verdict = PASS/WARN | 必须 | FAIL/BLOCKED 停止后续 |
| ArtReview_report.verdict = PASS/WARN | 必须 | FAIL/BLOCKED 停止后续 |
| 无 BLOCKER 级别问题 | 必须 | 有 BLOCKER → 流水线停止 |
| CRITICAL 问题 ≤ 3 | 推荐 | 超过 → 需人工确认 |

---

## 三、代码质量门禁（CI/CD）

| 门禁 | 工具 | 必须通过 |
|------|------|---------|
| 类型检查 | `mypy --ignore-missing-imports` | 无 error 级别 |
| 风格检查 | `flake8 --max-line-length=100` | 无警告 |
| 格式检查 | `black --check --line-length=100` | 无差异 |
| 单元测试 | `pytest core/tests/unit/` | 100% 通过 |
| 覆盖率 | `pytest --cov` | ≥ 75% |

---

## 四、综合质量评分计算

评分公式（满分 100 分）:

```
Score = 
  W00 * score_step00 +
  W01 * score_step01 +
  W02 * score_step02 +
  W03 * score_step03 +
  W04 * score_step04 +
  W05 * score_step05_06

权重分配:
  W00 = 0.15  (Step 00: 创意收集)
  W01 = 0.20  (Step 01: 玩法框架)
  W02 = 0.20  (Step 02: 设计冻结)
  W03 = 0.20  (Step 03: 程序需求)
  W04 = 0.15  (Step 04: 美术需求)
  W05 = 0.10  (Step 05/06: 评审)
```

各步骤评分细则:

| 步骤 | 指标 | 满分100时的条件 |
|------|------|---------------|
| Step 00 | coverage_rate | ≥ 0.75 → 100; ≥ 0.55 → 75; ≥ 0.40 → 55; < 0.40 → 30 |
| Step 01 | system_count + source_kind | count≥5 且 explicit → 90; count≥5 且 fallback → 65; count<5 → 40 |
| Step 02 | entity_coverage_rate | ≥ 0.80 → 100; ≥ 0.70 → 80; ≥ 0.50 → 55; < 0.50 → 35 |
| Step 03 | binding_rate + 0占位符 | binding≥95% → 90; binding≥80% → 70; placeholder>0 → -20 |
| Step 04 | asset_count | ≥ 80 → 100; ≥ 50 → 75; ≥ 20 → 50; < 20 → 25 |
| Step 05/06 | verdict + warning_count | PASS+0warnings → 100; PASS+warns → 80; WARN → 60; FAIL → 20; BLOCKED → 0 |

---

## 五、里程碑质量门禁

| 里程碑 | 时间点 | 最低质量要求 |
|--------|--------|------------|
| Phase 0 完成 | Week 1末 | PLAN-002 验证通过 |
| Phase 1 完成 | Week 4末 | 综合质量 ≥ 60/100 |
| Phase 2 完成 | Week 7末 | 综合质量 ≥ 65/100 |
| Phase 3 完成 | Week 9末 | 综合质量 ≥ 70/100 + 代码质量门禁全通过 |
| Phase 4 完成 | Week 10末 | 综合质量 ≥ 75/100 + 3品类验证通过 |
