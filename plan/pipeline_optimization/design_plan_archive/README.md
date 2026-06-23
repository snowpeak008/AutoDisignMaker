# AutoDesignMaker 流水线优化 - 最终方案

**版本**: v3.0 Final (Codex Reviewed)  
**创建日期**: 2026-06-22  
**审核状态**: ✅ 已通过Codex审核  
**总体评分**: 8.2/10

---

## 📋 方案总览

本优化方案经过深度代码分析、问题诊断、方案设计和Codex专业审核，现已准备实施。

### 当前问题
- 问答覆盖率：6.67%
- core_loop输出率：0%
- designEntities传递率：0%
- 需求占位符率：100%
- 步骤05警告数：107个
- **综合质量：32/100**

### 优化目标
- 问答覆盖率：→ 55-65%
- core_loop输出率：→ 100%
- designEntities传递率：→ 85-95%
- 需求占位符率：→ 15-25%
- 步骤05警告数：→ 5-15
- **综合质量：→ 60-70/100**

---

## 📁 方案文件清单

| 文件 | 步骤 | Codex评分 | 优先级 | 状态 |
|------|------|----------|--------|------|
| [STEP00_FINAL_PLAN.json](STEP00_FINAL_PLAN.json) | 创意收集 | 8.5/10 | 高 | ✅ 可实施 |
| [STEP01_FINAL_PLAN.json](STEP01_FINAL_PLAN.json) | 玩法框架 | 9.0/10 | 极高 | ✅ 可实施 |
| [STEP02_FINAL_PLAN.json](STEP02_FINAL_PLAN.json) | 设计冻结 | 7.5/10 | 极高 | ⚠️ 依赖PLAN-002 |
| [STEP03_FINAL_PLAN.json](STEP03_FINAL_PLAN.json) | 程序需求 | 8.0/10 | 高 | ✅ 可实施 |
| [STEP04_FINAL_PLAN.json](STEP04_FINAL_PLAN.json) | 美术需求 | 8.0/10 | 高 | ✅ 可实施 |
| [STEP05_06_FINAL_PLAN.json](STEP05_06_FINAL_PLAN.json) | 评审增强 | 8.0/10 | 中 | ✅ 可实施 |

---

## 🚀 实施计划（10周）

### Phase 0: 基础验证（Week 1）
**关键任务**: 验证PLAN-002修复

- [ ] 验证PLAN-002：加载Hades模板 → 检查entity_coverage
- [ ] 如未修复：立即修复（预留2-3天）
- [ ] 搭建标准化模块结构模板
- [ ] 配置pytest基础设施
- [ ] 配置pre-commit hooks (black, flake8, mypy)

**验收标准**:
- PLAN-002已修复且验证通过
- 标准化模块结构模板可用
- CI/CD流水线配置完成

---

### Phase 1: 核心模块（Weeks 2-4）

#### Week 2: 步骤00 - 创意收集
- [ ] Day 1: 创建标准化目录结构
- [ ] Day 2: ConceptProcessor实现（含@lru_cache）
- [ ] Day 3: QuestionEngine实现（从JSON加载问题）
- [ ] Day 4: 创建data/core_questions.json
- [ ] Day 5: 单元测试（覆盖率>75%）

**交付物**: ConceptProcessor + QuestionEngine

#### Week 3: 步骤01 - 玩法框架
- [ ] Day 1: 创建标准化目录结构
- [ ] Day 2: LoopExtractor实现 + 数据继承
- [ ] Day 3: SystemDeducer实现
- [ ] Day 4: 创建genre_templates.json（3个品类）
- [ ] Day 5: 单元测试

**交付物**: LoopExtractor + SystemDeducer + 品类模板

#### Week 4: 步骤02 - 设计冻结
- [ ] Day 1: EntityValidator实现
- [ ] Day 2: GraphGenerator实现（含cycle detection）
- [ ] Day 3: PhaseClassifier实现
- [ ] Day 4: Codex集成（实体补全）
- [ ] Day 5: 测试

**交付物**: EntityValidator + GraphGenerator + PhaseClassifier

**里程碑**: core_loop输出率100%，问答覆盖率>40%

---

### Phase 2: 智能生成（Weeks 5-7）

#### Week 5: Codex集成基础
- [ ] CodexAdapter基类（含缓存、重试、回退）
- [ ] 步骤00问答补全集成
- [ ] 步骤01循环推导集成
- [ ] 集成测试

**交付物**: CodexAdapter完整实现

#### Week 6: 实体转换器
- [ ] EntityToRequirementConverter
- [ ] 转换器注册表（支持5种schema）
- [ ] SystemBinder（含模糊匹配）
- [ ] 单元测试

**交付物**: 实体到需求转换完成

#### Week 7: 美术需求生成
- [ ] 步骤02实体补全集成
- [ ] EntityToAssetConverter
- [ ] MarketResearchSkill实现
- [ ] 创建market_data参考库
- [ ] 集成测试

**交付物**: 实体到资产转换完成

**里程碑**: entity_coverage>80%，需求-系统绑定率100%，步骤05警告<10

---

### Phase 3: 质量提升（Weeks 8-9）

#### Week 8: 评审增强
- [ ] IntelligentReviewer实现
- [ ] 占位符检测
- [ ] 规格完整性检查
- [ ] 严重性分级（BLOCKER/CRITICAL/WARNING/INFO）
- [ ] 端到端测试

**交付物**: 智能评审系统

#### Week 9: 集成与优化
- [ ] Bug修复
- [ ] 性能优化
- [ ] 代码审查
- [ ] 文档完善
- [ ] 全流程测试

**交付物**: 生产就绪代码

**里程碑**: 综合质量>65/100

---

### Phase 4: 验证（Week 10）

#### 验证测试
- [ ] Hades模板完整测试
- [ ] 空白Roguelike项目测试
- [ ] 空白FPS项目测试
- [ ] 空白Puzzle项目测试
- [ ] 性能基准测试
- [ ] 用户验收测试

**交付物**: 验证通过的生产版本

---

## 🎯 成功标准

### 定量指标

| 指标 | 当前值 | 目标值 | 验证方式 |
|------|--------|--------|---------|
| 代码覆盖率 | 0% | >75% | pytest --cov |
| 问答覆盖率 | 6.67% | 55-65% | question_engine.get_coverage_rate() |
| core_loop输出率 | 0% | 100% | 检查core_loop.json非空 |
| systems定义率 | 0% | 100% | 检查systems.json包含5+系统 |
| entity传递率 | 0% | 85-95% | entity_validator.validate() |
| 需求占位符率 | 100% | 15-25% | intelligent_reviewer.detect_placeholders() |
| 需求-系统绑定率 | 0% | 90-95% | 检查system_id字段 |
| 步骤05警告数 | 107 | 5-15 | ProgReview_report.json |
| 资产数量 | 3 | 40-60 | asset_registry.json |
| **综合质量** | **32/100** | **60-70/100** | 加权评分 |

### 定性指标
- [ ] 所有模块有完整docstring
- [ ] 所有公共API有类型注解
- [ ] 通过mypy类型检查
- [ ] 通过flake8风格检查
- [ ] 代码审查通过

---

## ⚠️ 关键风险与缓解

### 🔴 严重风险

#### 1. PLAN-002未修复
- **概率**: 高
- **影响**: 严重（阻塞步骤02）
- **缓解**: Phase 0 Week 1立即验证并修复

#### 2. Codex API不稳定
- **概率**: 中
- **影响**: 高
- **缓解**: 重试机制 + 品类模板回退 + 离线模式

#### 3. 实体Schema覆盖不足
- **概率**: 高
- **影响**: 中
- **缓解**: 转换器注册表 + 分阶段覆盖 + 通用转换器

---

## 📊 Codex审核摘要

### 各步骤评分

| 步骤 | 可行性 | 完整性 | 关键改进 |
|------|--------|--------|---------|
| 步骤00 | 8.5/10 | 8/10 | 缓存+回退+数据化 ✅ |
| 步骤01 | 9.0/10 | 9/10 | 数据继承+品类模板 ✅ |
| 步骤02 | 7.5/10 | 7/10 | PLAN-002依赖 ⚠️ |
| 步骤03 | 8.0/10 | 7.5/10 | 转换器注册表 ✅ |
| 步骤04 | 8.0/10 | 7.5/10 | 市场数据库 ✅ |
| 步骤05-06 | 8.0/10 | 8/10 | 智能评审 ✅ |

### 批准条件（已满足）
- ✅ 采纳风险缓解策略
- ✅ 使用10周计划（非9周）
- ✅ Phase 0验证PLAN-002
- ✅ 添加pre-commit hooks
- ✅ 建立转换器注册表

---

## 💻 技术规范

### 代码质量标准
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    hooks: [black]
  - repo: https://github.com/PyCQA/flake8
    hooks: [flake8]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks: [mypy]
```

### 测试要求
- 单元测试覆盖率 >75%
- 集成测试覆盖关键流程
- 每个模块有测试fixtures

### 文档要求
- 每个模块：docstring + 使用示例
- 每个函数：Args/Returns/Raises
- 每个数据类：字段描述

---

## 📞 下一步行动

### 立即行动（今天）
1. ✅ 审查此方案（已完成）
2. ⏳ 团队会议：分配负责人
3. ⏳ 准备开发环境

### 明天（Phase 0开始）
1. ⏳ 验证PLAN-002修复状态
2. ⏳ 如未修复，立即修复
3. ⏳ 搭建基础设施

### 本周内
1. ⏳ 完成Phase 0所有任务
2. ⏳ 准备进入Phase 1

---

## 📚 参考资料

- [Hades质量评估报告](../../hades_quality_report.md)
- [PLAN-001](../PLAN-001-export-adapter-l5-entities.md)
- [PLAN-002](../PLAN-002-template-designentities-lost.md)
- [Codex审核结果](CODEX_REVIEW_RESULT.md) (如有)

---

**项目负责人**: 待分配  
**Codex审核人**: Codex CLI  
**总体评分**: 8.2/10  
**批准状态**: ✅ APPROVED  
**创建时间**: 2026-06-22  
**最后更新**: 2026-06-23  
**状态**: 📋 就绪，等待实施
