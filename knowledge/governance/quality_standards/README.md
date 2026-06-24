# 质量标准体系

**当前版本**: v1.0.0
**发布日期**: 2026-06-24
**适用范围**: AutoDesignMaker Step 00-09 质量优化、Hades 范本质量复盘和后续模板优化。

## 文档导航

### 标准文档

- [质量基线标准](standards/QUALITY_BASELINE.md)
- [优化流程标准](standards/OPTIMIZATION_WORKFLOW.md)
- [实体覆盖标准](standards/ENTITY_COVERAGE_STANDARD.md)
- [任务生成标准](standards/TASK_GENERATION_STANDARD.md)
- [AI 补全标准](standards/AI_SUPPLEMENT_STANDARD.md)

### 可复用模板

- [优化计划模板](templates/OPTIMIZATION_PLAN_TEMPLATE.md)
- [检查清单模板](templates/CHECKLIST_TEMPLATE.md)
- [任务文档模板](templates/TASK_DOCUMENT_TEMPLATE.md)
- [开发指南模板](templates/DEVELOPMENT_GUIDE_TEMPLATE.md)

### 操作手册

- [AI 补全修复手册](playbooks/AI_SUPPLEMENT_FIX_PLAYBOOK.md)
- [实体扩展手册](playbooks/ENTITY_EXPANSION_PLAYBOOK.md)
- [任务清理手册](playbooks/TASK_CLEANUP_PLAYBOOK.md)

### 指标定义

- [核心指标定义](metrics/CORE_METRICS.md)
- [评分规则](metrics/SCORING_RUBRIC.md)
- [阈值参考](metrics/THRESHOLD_REFERENCE.md)

## 使用流程

1. 运行 `python tools/validators/pipeline_quality.py` 或读取最新质量报告。
2. 对照质量基线识别 P0/P1/P2 问题。
3. 使用优化计划模板建立任务计划。
4. 按操作手册修复，并在每个阶段运行测试。
5. 验证指标改善后，将经验回写到本标准体系。
