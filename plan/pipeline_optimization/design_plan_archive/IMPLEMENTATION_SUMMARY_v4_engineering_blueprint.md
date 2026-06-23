# AutoDesignMaker 流水线优化 — 实施总结

**版本**: v4.0 Engineering Blueprint  
**日期**: 2026-06-23  
**状态**: 未开始（全部待实施）

---

## 交付物清单

| 文件 | 内容 | 状态 |
|------|------|------|
| README.md | 完整工程蓝图：架构/阶段/验收标准 | 已创建 |
| STEP00_FINAL_PLAN.json | 步骤00完整模块设计（含类签名/数据契约/测试用例） | 已创建 |
| STEP01_FINAL_PLAN.json | 步骤01完整模块设计 | 已创建 |
| STEP02_FINAL_PLAN.json | 步骤02完整模块设计 | 已创建 |
| STEP03_FINAL_PLAN.json | 步骤03完整模块设计 | 已创建 |
| STEP04_FINAL_PLAN.json | 步骤04完整模块设计 | 已创建 |
| STEP05_06_FINAL_PLAN.json | 步骤05-06完整模块设计 | 已创建 |

---

## 核心改进（对比旧版 v3.0）

| 维度 | 旧版 v3.0 | 新版 v4.0 |
|------|-----------|-----------|
| 模块描述 | 模块名称 + 方法列表（无签名） | 完整方法签名 + 参数类型 + 返回类型 + Raises |
| 数据类 | 无 | 每个核心对象都有 `@dataclass` 字段定义 |
| 数据契约 | 文件名列表 | 输入/输出 schema 路径 + 字段约束 |
| 任务粒度 | "实现X" | 具体方法级任务 + 小时估算 |
| 测试用例 | 测试文件名 | 每个 test_* 函数名 + 涵盖的场景 |
| 回退策略 | "添加回退" | 具体回退逻辑（品类模板/通用答案/minimal schema） |
| 步骤依赖 | 隐式 | 明确 blocked_by 标注 |

---

## 实施路线图

### Phase 0 — 基础设施（Week 1）

- [ ] 修复 PLAN-002（`core/design/export_adapter.py`）
- [ ] 验证修复：Hades 模板 entity_coverage ≥ 38%
- [ ] 搭建 pytest 基础设施（`core/tests/conftest.py`）
- [ ] 配置 pre-commit hooks（black+flake8+mypy）
- [ ] 创建步骤标准目录模板脚本

### Phase 1 — 核心模块（Weeks 2-4）

#### Week 2 — 步骤00 创意收集

- [ ] T00-01 创建五层模块目录结构
- [ ] T00-02 实现 ConceptData dataclass + ConceptParseError
- [ ] T00-03 实现 ConceptProcessor._parse_raw_concept()
- [ ] T00-04 实现 ConceptProcessor._get_option_detail() 含 @lru_cache
- [ ] T00-05 实现 ConceptProcessor.process()
- [ ] T00-06 创建 data/core_questions.json（15个完整问题）
- [ ] T00-07 实现 DesignQuestion + EvaluationResult dataclass
- [ ] T00-08 实现 QuestionEngine 全部方法
- [ ] T00-09 实现 InterviewAdapter（重试+回退）
- [ ] T00-10 实现 ContentGenerator.generate()
- [ ] T00-11 重构 plugin.py 为编排层
- [ ] T00-12 单元测试（覆盖率 >80%）

#### Week 3 — 步骤01 玩法框架

- [ ] T01-01 创建五层模块目录结构
- [ ] T01-02 实现 Step00Data + DataInheritor.load()
- [ ] T01-03 实现 LoopNode + CoreLoopResult dataclass
- [ ] T01-04 实现 LoopExtractor._parse_loop_from_answers()
- [ ] T01-05 创建 data/genre_templates.json（5个品类）
- [ ] T01-06 实现 LoopExtractor._fill_from_genre_template()
- [ ] T01-07 实现 LoopExtractor.extract()
- [ ] T01-08 实现 GameSystem + GenreTemplate dataclass
- [ ] T01-09 实现 SystemDeducer._select_template() + _map_loop_to_systems()
- [ ] T01-10 实现 SystemDeducer._resolve_dependencies()（拓扑排序）
- [ ] T01-11 实现 ResourceAnalyzer 全部方法
- [ ] T01-12 重构 plugin.py
- [ ] T01-13 单元测试（覆盖率 >80%）

#### Week 4 — 步骤02 设计冻结

- [ ] T02-00 验证 PLAN-002 已修复（必须通过，否则不开始本周工作）
- [ ] T02-01 创建五层模块目录结构
- [ ] T02-02 实现 EntityValidator（_compute_coverage + _find_missing_entities）
- [ ] T02-03 实现 GraphGenerator（_build_adjacency + _detect_cycles + _render_mermaid）
- [ ] T02-04 实现 PhaseClassifier._score_system() + classify()
- [ ] T02-05 实现 FreezeBundler.bundle()
- [ ] T02-06 实现 EntitySupplementAdapter（含回退）
- [ ] T02-07 重构 plugin.py
- [ ] T02-08 单元测试（覆盖率 >80%）

**Phase 1 里程碑检查**:
- [ ] core_loop.json 输出率 100%
- [ ] systems.json 包含 3-8 个系统
- [ ] entity 传递率 >70%
- [ ] 问答覆盖率 >40%

### Phase 2 — 智能生成（Weeks 5-7）

#### Week 5 — AI 适配器层

- [ ] T-AI-01 实现 core/adapters/codex_adapter.py（缓存+重试+回退）
- [ ] T-AI-02 步骤00 AI 补全集成测试
- [ ] T-AI-03 步骤01 循环提取 AI 集成测试

#### Week 6 — 步骤03 程序需求

- [ ] T03-01 创建五层模块目录结构 + converters 子目录
- [ ] T03-02 实现 ProgramRequirement + ValidationReport dataclass
- [ ] T03-03 实现 BaseConverter 抽象基类
- [ ] T03-04 实现 ConverterRegistry.load() + get() + register()
- [ ] T03-05 实现5个核心转换器（skill/character/item/system/operation）
- [ ] T03-06 实现 GenericConverter（兜底）
- [ ] T03-07 实现 SystemBinder（精确+模糊匹配）
- [ ] T03-08 实现 RequirementValidator
- [ ] T03-09 重构 plugin.py
- [ ] T03-10 单元测试（覆盖率 >80%）

#### Week 7 — 步骤04 美术需求

- [ ] T04-01 创建五层模块目录结构
- [ ] T04-02 实现 ArtAsset dataclass
- [ ] T04-03 实现 EntityToAssetConverter 5种转换方法
- [ ] T04-04 实现 EntityToAssetConverter._convert_generic()
- [ ] T04-05 创建 knowledge/market_data/ 5个品类 JSON
- [ ] T04-06 实现 MarketResearchSkill
- [ ] T04-07 实现 AssetRegistry
- [ ] T04-08 实现 Markdown 需求文档生成器
- [ ] T04-09 重构 plugin.py
- [ ] T04-10 单元测试（覆盖率 >80%）

**Phase 2 里程碑检查**:
- [ ] entity_coverage >80%
- [ ] 需求-系统绑定率 >90%
- [ ] 步骤05警告 <10
- [ ] 资产数量 >40

### Phase 3 — 质量提升（Weeks 8-9）

#### Week 8 — 步骤05-06 智能评审

- [ ] T05-01 实现 Finding + ReviewReport dataclass
- [ ] T05-02 实现 BaseIntelligentReviewer（review/score/verdict）
- [ ] T05-03 实现 PlaceholderDetector
- [ ] T05-04 实现 ProgramRequirementReviewer 5个检查方法
- [ ] T05-05 实现 ArtRequirementReviewer 4个检查方法
- [ ] T05-06 重构 step_05/plugin.py
- [ ] T05-07 重构 step_06/plugin.py
- [ ] T05-08 单元测试（覆盖率 >80%）

#### Week 9 — 集成与优化

- [ ] 全流水线端到端测试（Hades模板）
- [ ] Bug修复
- [ ] 性能优化（profiling slow paths）
- [ ] 代码审查（所有新模块）
- [ ] 文档完善

**Phase 3 里程碑检查**:
- [ ] 综合质量 >65/100
- [ ] false_pass_rate = 0%
- [ ] 所有代码通过 mypy + flake8

### Phase 4 — 验证（Week 10）

- [ ] Hades 模板完整流水线测试
- [ ] 空白 Roguelike 项目测试
- [ ] 空白 FPS 项目测试
- [ ] 空白 Puzzle 项目测试
- [ ] 性能基准测试（每步 <5秒）

---

## 成功标准

### 硬性指标（必须满足）

- [ ] PLAN-002 修复通过（entity_coverage ≥ 38%）
- [ ] core_loop.json 输出率 100%
- [ ] systems.json 包含 3-8 个系统
- [ ] 代码覆盖率 >80%
- [ ] 通过 mypy --strict
- [ ] false_pass_rate = 0%

### 软性指标（应该满足）

- [ ] 问答覆盖率 >55%
- [ ] entity 传递率 >85%
- [ ] 需求占位符率 <25%
- [ ] 步骤05警告 <15
- [ ] 综合质量 >65/100
- [ ] 资产数量 >40

---

**状态**: 未开始，等待 Phase 0 启动
