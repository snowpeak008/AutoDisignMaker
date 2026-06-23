# Phase 4 — 多品类验证（Week 10）

## 目标

在 Hades 以外的3个品类项目上验证流水线通用性，所有品类均通过 Step 05/06 评审。

---

## 测试矩阵

| 测试场景 | 品类模板 | 关注指标 | 通过标准 |
|---------|---------|---------|---------|
| Hades（已有 L5 实体） | roguelike_action | entity_coverage, 需求质量 | coverage ≥ 0.75 |
| 空白 Roguelike | roguelike_action | template 回退路径 | loop 非空，系统 ≥5 |
| 空白 FPS | fps | 品类模板完整性 | loop 非空，系统 ≥4 |
| 空白 Puzzle | puzzle | 品类模板完整性 | loop 非空，系统 ≥3 |

---

## 验证任务

### V-T01 — Hades 完整流水线验证

```bash
# 1. 在 DesignEngine 填写 ≥40 个 L5 实体
# 2. 导出存档
# 3. 运行全流水线 Step 00-06
# 4. 评估综合质量
python tools/validators/pipeline_quality.py --run-full --save-id <ID>
```

**期望结果**:
- entity_coverage_rate ≥ 0.75
- 问答覆盖率 ≥ 0.55
- Step 05 verdict = PASS，warnings ≤ 5
- Step 06 verdict = PASS
- 综合质量 ≥ 75/100

---

### V-T02 — 空白 Roguelike 项目验证

**创建方式**: 新建项目，只填写 L1 项目愿景（规模/平台/商业模式），不填 L5 实体

**验证点**:
- Step 01: `template_key = "roguelike_action"`，`source_kind = "template_fallback"`
- Step 01: `system_count ≥ 5`
- Step 02: 合成实体 ≥ 20，`entity_coverage_rate ≥ 0.20`
- Step 05: verdict 不为 BLOCKED（流水线不中断）

---

### V-T03 — 空白 FPS 项目验证

**创建方式**: 新建项目，在 concept.md 中包含 "fps" / "射击" / "shooter" 关键词

**验证点**:
- `template_key = "fps"`
- fps 品类 core_loop 包含适当节点（发现目标/移动射击等）
- Step 05: verdict 不为 BLOCKED

---

### V-T04 — 空白 Puzzle 项目验证

**验证点**:
- `template_key = "puzzle"`
- puzzle 品类 core_loop 包含适当节点（观察/尝试/反馈等）

---

### V-T05 — 性能基准测试

```bash
python -m cProfile -o profile.out -m pytest core/tests/integration/ -v
python -c "import pstats; p = pstats.Stats('profile.out'); p.sort_stats('cumtime'); p.print_stats(20)"
```

**性能目标**:
- 单步骤处理（不含 AI）< 3秒
- 全流水线（Step 00-06，不含 AI）< 30秒
- `_load_templates()` 调用 < 100ms（含缓存）

---

## Phase 4 最终验收

### 必须通过（全部）
- [ ] Hades 存档综合质量 ≥ 75/100
- [ ] 3个空白品类均通过 Step 05/06 评审（verdict ≠ BLOCKED）
- [ ] 性能测试无超时
- [ ] 全部单元测试通过，覆盖率 ≥ 75%

### 推荐完成（至少5项）
- [ ] 问答覆盖率 ≥ 0.60
- [ ] entity_coverage ≥ 0.80（有 L5 实体时）
- [ ] system_binding_rate ≥ 95%
- [ ] Step 03 需求数 ≥ 100（有真实 L5 实体时）
- [ ] 资产数量 ≥ 80（有真实 L5 实体时）
- [ ] 无 CRITICAL 级别审查问题
