# 快速开始指南

## Phase 0 - Week 1（立即开始）

### Day 1: 验证PLAN-002

```bash
# 1. 运行验证脚本
python tests/verify_plan002.py

# 2. 加载Hades模板测试
# 在GUI中：项目 -> 查看项目模板 -> Hades L5 Complete -> 载入
# 预期：39/103节点有实体

# 3. 如果失败，检查
grep -n "save_current_design_project" core/ui/app_window.py
grep -n "designEntities" core/engines/execution_objects/design_project.py
```

### Day 2-3: 基础设施

```bash
# 1. 安装pre-commit
pip install pre-commit
pre-commit install

# 2. 配置pytest
pip install pytest pytest-cov

# 3. 创建模块模板
mkdir -p pipeline/step_00_idea_intake/{core,adapters,schemas,prompts,data,tests}
```

### Day 4-5: 文档与准备

- 阅读所有STEP*_FINAL_PLAN.json
- 分配开发任务
- 准备Week 2开发环境

## Phase 1 - Week 2-4

按照README.md中的计划执行

## 验证检查点

每周五检查：
- [ ] 代码覆盖率 >75%
- [ ] 所有测试通过
- [ ] 代码审查完成
- [ ] 文档更新完成

## 问题上报

遇到问题：
1. 检查对应STEP*_FINAL_PLAN.json的风险部分
2. 查看Codex审核建议
3. 必要时调整计划
