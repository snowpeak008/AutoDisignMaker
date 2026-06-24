# 质量基线标准 v1.0.0

## Step 00-06 基线

| 指标 | 最低要求 | 理想目标 | 说明 |
|------|----------|----------|------|
| question_coverage_rate | >= 0.55 | >= 0.85 | 核心问题覆盖率 |
| design_entity_coverage_rate | >= 0.38 | >= 0.75 | L5 实体覆盖率 |
| requirement_system_binding_rate | >= 0.90 | >= 0.95 | 需求绑定率 |
| requirement_placeholder_rate | <= 0.25 | <= 0.10 | 占位符率 |
| stage05_blocking_issue_count | 0 | 0 | 程序评审阻断数 |

## Step 07-09 基线

| 指标 | 最低要求 | 理想目标 | 说明 |
|------|----------|----------|------|
| task_count | >= 100 | >= 150 | 程序任务规模 |
| task_title_avg_length | <= 100 | <= 80 | 标题可读性 |
| task_priority_coverage | >= 0.80 | >= 0.95 | 优先级标注 |
| asset_alignment_rate | >= 0.80 | >= 0.95 | 资产对齐率 |

## 等级定义

- A: 所有 P0 指标达标，主要 P1 指标达到理想目标。
- B: 所有 P0 指标达最低要求，但存在可优化项。
- C: 无阻断，但存在多个低于最低要求的指标。
- F: 存在 BLOCKER 或关键产物缺失。
