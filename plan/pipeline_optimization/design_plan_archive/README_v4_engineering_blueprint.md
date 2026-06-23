# AutoDesignMaker 流水线优化 — 工程蓝图

**版本**: v4.0 Engineering Blueprint  
**日期**: 2026-06-23  
**状态**: 未开始（全部待实施）  
**总工期**: 10 周

---

## 一、当前问题诊断

| 指标 | 当前值 | 问题根因 |
|------|--------|---------|
| 综合质量 | 32/100 | 各步骤无真实业务逻辑 |
| 问答覆盖率 | 6.67% | plugin.py 仅20行骨架 |
| core_loop 输出率 | 0% | 步骤01不读取上游数据 |
| designEntities 传递率 | 0% | PLAN-002 bug 未修复 |
| 需求占位符率 | 100% | 无实体→需求转换器 |
| 步骤05警告数 | 107 | 评审不检测内容质量 |
| 资产数量 | 3 | 无实体→资产转换器 |

---

## 二、整体架构设计

### 2.1 分层模块体系

每个流水线步骤遵循统一的五层模块结构：

```
pipeline/step_NN_name/
├── plugin.py                  # 入口：StagePlugin 实现，只做编排
├── core/
│   ├── __init__.py
│   ├── processor.py           # 数据处理：解析/转换/聚合
│   ├── validator.py           # 合约验证：输入检查 + 输出验证
│   └── generator.py           # 内容生成：基于处理结果合成输出
├── adapters/
│   ├── __init__.py
│   └── ai_adapter.py          # AI调用封装：缓存 + 重试 + 回退
├── schemas/
│   ├── input.schema.json      # 输入数据契约（JSON Schema draft-7）
│   └── output.schema.json     # 输出数据契约
├── data/
│   └── *.json                 # 静态配置数据（问题库/模板库/参考库）
├── prompts/
│   ├── main.txt               # 主提示词
│   └── templates/
│       └── *.txt              # 子提示词模板
└── tests/
    ├── unit/
    │   └── test_*.py
    ├── integration/
    │   └── test_*.py
    └── fixtures/
        ├── input/             # 测试输入数据
        └── expected/          # 期望输出数据
```

### 2.2 步骤间数据流

```
step_00 输出:
  design_extraction_enhanced.json   ─→  step_01 读取
  skill_guidance.json               ─→  step_04 读取

step_01 输出:
  core_loop.json                    ─→  step_02 读取
  systems.json                      ─→  step_02, step_03 读取

step_02 输出:
  frozen_design.json                ─→  step_03, step_04 读取
  design_entities.json              ─→  step_03, step_04 读取

step_03 输出:
  program_requirements.md           ─→  step_05 评审
  requirements_by_system.json       ─→  step_05 评审

step_04 输出:
  asset_registry.json               ─→  step_06 评审
  art_requirements.md               ─→  step_06 评审
```

### 2.3 核心接口规范

```python
# 所有处理器基类（每步骤 processor.py 继承）
class BaseProcessor(Protocol):
    def process(self, ctx: StageContext) -> ProcessResult: ...
    def validate_input(self, data: dict) -> ValidationResult: ...

# 所有AI适配器基类（每步骤 ai_adapter.py 继承）
class BaseAIAdapter(Protocol):
    def call(self, prompt: str, context: dict, *, retries: int = 3) -> AIResult: ...
    def call_with_fallback(self, prompt: str, context: dict, fallback: dict) -> AIResult: ...
```

---

## 三、实施计划（10周）

### Phase 0 — 基础设施（Week 1）

**目标**: 建立开发基础，修复关键 Bug

| 任务 | 文件/命令 | 负责人 | 状态 |
|------|-----------|--------|------|
| 修复 PLAN-002（designEntities 丢失） | `core/design/export_adapter.py` | - | [ ] |
| 验证修复：Hades模板 entity_coverage ≥ 38% | `python tools/validators/pipeline_quality.py` | - | [ ] |
| 搭建 pytest 基础设施 | `core/tests/conftest.py` | - | [ ] |
| 配置 pre-commit hooks（black+flake8+mypy） | `.pre-commit-config.yaml` | - | [ ] |
| 创建步骤标准目录模板 | `tools/dev/scaffold_step.py` | - | [ ] |

**验收**: PLAN-002 修复通过 + CI 绿色

---

### Phase 1 — 核心模块（Weeks 2-4）

**目标**: 步骤00-02 完整业务逻辑

#### Week 2 — 步骤00 创意收集

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T00-01 | 创建 `pipeline/step_00_idea_intake/core/` 结构 | 2h | [ ] |
| T00-02 | 实现 `ConceptProcessor.process()` 解析concept.md | 4h | [ ] |
| T00-03 | 实现 `QuestionEngine` 加载问题库 + 覆盖率计算 | 4h | [ ] |
| T00-04 | 创建 `data/core_questions.json`（15个问题完整定义） | 3h | [ ] |
| T00-05 | 实现 `AIAdapter.run_guided_interview()` 含重试+回退 | 4h | [ ] |
| T00-06 | 实现 `ContentGenerator.generate()` | 3h | [ ] |
| T00-07 | 重构 `plugin.py` 为编排层 | 2h | [ ] |
| T00-08 | 单元测试（覆盖率 >80%） | 4h | [ ] |

#### Week 3 — 步骤01 玩法框架

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T01-01 | 创建 `pipeline/step_01_gameplay_framework/core/` 结构 | 2h | [ ] |
| T01-02 | 实现 `DataInheritor` 读取步骤00输出 + Schema验证 | 3h | [ ] |
| T01-03 | 实现 `LoopExtractor.extract()` 从概念数据推导核心循环 | 5h | [ ] |
| T01-04 | 创建 `data/genre_templates.json`（roguelike/fps/rpg/puzzle/strategy） | 4h | [ ] |
| T01-05 | 实现 `SystemDeducer.deduce()` 基于循环+品类模板推导系统 | 5h | [ ] |
| T01-06 | 实现 `ResourceAnalyzer.analyze()` 分析系统间资源流动 | 3h | [ ] |
| T01-07 | 重构 `plugin.py` | 2h | [ ] |
| T01-08 | 单元测试（覆盖率 >80%） | 4h | [ ] |

#### Week 4 — 步骤02 设计冻结

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T02-01 | 创建 `pipeline/step_02_design_review_freeze/core/` 结构 | 2h | [ ] |
| T02-02 | 实现 `EntityValidator.validate()` 验证实体覆盖率 | 4h | [ ] |
| T02-03 | 实现 `GraphGenerator.generate()` 生成 Mermaid 系统依赖图（含环检测） | 5h | [ ] |
| T02-04 | 实现 `PhaseClassifier.classify()` core_playable/social/full_feature分类 | 4h | [ ] |
| T02-05 | 实现 `FreezeBundler.bundle()` 打包冻结设计 | 3h | [ ] |
| T02-06 | 重构 `plugin.py` | 2h | [ ] |
| T02-07 | 单元测试（覆盖率 >80%） | 4h | [ ] |

**Phase 1 里程碑**:
- [ ] core_loop.json 输出率 100%
- [ ] systems.json 包含 3-8 个系统
- [ ] entity 传递率 >70%
- [ ] 问答覆盖率 >40%

---

### Phase 2 — 智能生成（Weeks 5-7）

**目标**: AI 深度集成，步骤03-04 完整实现

#### Week 5 — AI 适配器层

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T-AI-01 | 实现 `core/adapters/codex_adapter.py`（缓存+重试+回退） | 6h | [ ] |
| T-AI-02 | 实现适配器 in step_00: `guided_interview` 集成 | 4h | [ ] |
| T-AI-03 | 实现适配器 in step_01: `loop_extraction` 集成 | 4h | [ ] |
| T-AI-04 | 适配器集成测试 | 4h | [ ] |

#### Week 6 — 步骤03 程序需求

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T03-01 | 创建 `pipeline/step_03_program_requirements/core/` 结构 | 2h | [ ] |
| T03-02 | 实现 `ConverterRegistry`（支持15+种entity schema） | 5h | [ ] |
| T03-03 | 实现5种核心转换器：skill/character/item/system/operation_card | 8h | [ ] |
| T03-04 | 实现通用回退转换器 `GenericConverter` | 3h | [ ] |
| T03-05 | 实现 `SystemBinder`（精确匹配+模糊匹配） | 4h | [ ] |
| T03-06 | 实现 `RequirementValidator` | 3h | [ ] |
| T03-07 | 重构 `plugin.py` | 2h | [ ] |
| T03-08 | 单元测试（覆盖率 >80%） | 4h | [ ] |

#### Week 7 — 步骤04 美术需求

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T04-01 | 创建 `pipeline/step_04_art_requirements/core/` 结构 | 2h | [ ] |
| T04-02 | 实现 `EntityToAssetConverter` 转换15+种实体到资产 | 6h | [ ] |
| T04-03 | 创建 `knowledge/market_data/` 策划参考库（5个品类） | 5h | [ ] |
| T04-04 | 实现 `MarketResearchSkill`（读取参考库） | 4h | [ ] |
| T04-05 | 实现 `AssetRegistry` 管理资产目录 | 3h | [ ] |
| T04-06 | 重构 `plugin.py` | 2h | [ ] |
| T04-07 | 单元测试（覆盖率 >80%） | 4h | [ ] |

**Phase 2 里程碑**:
- [ ] entity_coverage >80%
- [ ] 需求-系统绑定率 100%
- [ ] 步骤05 警告 <10
- [ ] 资产数量 >40

---

### Phase 3 — 质量提升（Weeks 8-9）

**目标**: 智能评审，生产就绪

#### Week 8 — 步骤05-06 智能评审

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T05-01 | 实现 `PlaceholderDetector`（正则+语义检测） | 4h | [ ] |
| T05-02 | 实现 `IntelligentReviewer`（4级严重性分类） | 6h | [ ] |
| T05-03 | 增强步骤05 ProgReviewer（含占位符+绑定检查） | 4h | [ ] |
| T05-04 | 增强步骤06 ArtReviewer（含规格完整性+数量检查） | 4h | [ ] |
| T05-05 | 单元测试（覆盖率 >80%） | 4h | [ ] |

#### Week 9 — 集成优化

| 任务编号 | 任务 | 估时 | 状态 |
|---------|------|------|------|
| T-INT-01 | 全流水线端到端测试（Hades模板） | 6h | [ ] |
| T-INT-02 | Bug修复 | 8h | [ ] |
| T-INT-03 | 性能优化（slow paths profiling） | 4h | [ ] |
| T-INT-04 | 代码审查（所有新模块） | 4h | [ ] |
| T-INT-05 | 文档完善（所有公共API） | 4h | [ ] |

**Phase 3 里程碑**:
- [ ] 综合质量 >65/100
- [ ] false_pass_rate = 0%
- [ ] 所有代码通过 mypy + flake8

---

### Phase 4 — 验证（Week 10）

| 测试场景 | 验证方式 | 状态 |
|---------|---------|------|
| Hades模板完整流水线 | 对比基线数据 | [ ] |
| 空白 Roguelike 项目 | 验证系统推导 | [ ] |
| 空白 FPS 项目 | 验证系统推导 | [ ] |
| 空白 Puzzle 项目 | 验证系统推导 | [ ] |
| 性能基准测试 | 每步 <5秒（不含AI） | [ ] |

---

## 四、验收标准（硬性指标）

| 指标 | 当前值 | 目标值 | 验证命令 |
|------|--------|--------|---------|
| 代码覆盖率 | 0% | >80% | `pytest --cov` |
| 问答覆盖率 | 6.67% | >55% | `question_engine.coverage_rate()` |
| core_loop 输出率 | 0% | 100% | `assert core_loop.json 非空` |
| systems 定义率 | 0% | 100% | `assert len(systems) >= 3` |
| entity 传递率 | 0% | >85% | `entity_validator.validate()` |
| 需求占位符率 | 100% | <25% | `intelligent_reviewer.detect()` |
| 需求-系统绑定率 | 0% | >90% | `检查 system_id 字段` |
| 步骤05 警告数 | 107 | <15 | `ProgReview_report.json` |
| 资产数量 | 3 | >40 | `asset_registry.json` |
| **综合质量** | **32/100** | **>65/100** | 加权评分 |

## 五、代码规范

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks: [{id: black, args: [--line-length=100]}]
  - repo: https://github.com/PyCQA/flake8
    rev: 7.1.0
    hooks: [{id: flake8, args: [--max-line-length=100, --ignore=E203]}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks: [{id: mypy, args: [--strict, --ignore-missing-imports]}]
```

**强制规范**:
- 所有公共函数必须有类型注解和 one-line docstring
- 所有数据类使用 `@dataclass` 或 `TypedDict`
- 禁止在 `plugin.py` 中写业务逻辑（只做参数传递和异常处理）
- AI 调用必须通过适配器层，不允许在 core/ 直接调用

---

## 六、风险管理

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| PLAN-002 修复失败 | 高 | 严重 | Phase 0 优先修复，预留3天 |
| AI API 不稳定 | 中 | 高 | 重试3次 + 回退到品类模板 |
| entity schema 覆盖不足 | 高 | 中 | 通用转换器兜底 |
| 步骤间数据格式不兼容 | 中 | 中 | 每步 Schema 验证，快速失败 |
