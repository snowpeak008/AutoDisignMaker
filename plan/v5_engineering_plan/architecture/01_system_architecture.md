# 系统架构设计

## 一、总体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户操作层                                    │
│   DesignEngine UI → 填写 L1-L5 设计决策 + L5 实体                │
└────────────────────────────┬────────────────────────────────────┘
                             │ export_concept_package()
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     源包生成层                                    │
│   core/design/export_adapter.py                                  │
│   → devflow_Concept_v2/concept.md       (Step 00 输入)           │
│   → devflow_GameplayFramework_v2/       (Step 01 输入)           │
│   → devflow_Design_v2/design.md         (Step 02 输入)           │
└────────────────────────────┬────────────────────────────────────┘
                             │ sandbox/source_artifacts/
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     流水线执行层（步骤 00-06）                     │
│                                                                  │
│  Step 00 ──→ step_00/helpers.py                                  │
│    ├── ConceptProcessor   → concept_profile.json                 │
│    └── QuestionEngine     → core_question_coverage_report.json   │
│                     ↓ design_extraction.json                     │
│  Step 01 ──→ step_01/helpers.py                                  │
│    ├── LoopExtractor      → core_loop.json                       │
│    └── SystemDeducer      → system_definitions.json              │
│                     ↓ system_definitions.json                    │
│  Step 02 ──→ step_02/helpers.py                                  │
│    ├── EntityValidator    → entity_coverage_report.json          │
│    ├── GraphGenerator     → entity_dependency_graph.json         │
│    └── PhaseClassifier    → entity_phase_classification.json     │
│                     ↓ entity_coverage_report.json                │
│  Step 03 ──→ step_03/helpers.py                                  │
│    ├── EntityToRequirementConverter → program_requirements       │
│    └── SystemBinder                → requirements_by_system      │
│                     ↓ program_requirements_contract.json         │
│  Step 04 ──→ step_04/helpers.py                                  │
│    ├── EntityToAssetConverter → asset_registry.json              │
│    └── MarketResearchSkill    → market_analysis.md               │
│                     ↓ asset_registry.json                        │
│  Step 05/06 ──→ step_05/helpers.py                               │
│    └── IntelligentReviewer → ProgReview_report.json              │
│                            → ArtReview_report.json               │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     存档与制品层                                   │
│   core/save/manager.py → saves/{id}/workspace/outputs/           │
│   core/artifact/reviewer.py + validator.py                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、核心模块职责边界

### 2.1 core/ — 运行骨架（不含业务逻辑）

| 模块 | 职责 | 禁止事项 |
|------|------|---------|
| `core/paths.py` | 所有路径常量的唯一来源 | 其他文件不得硬编码路径 |
| `core/io.py` | 文件读写工具（read_json/write_json） | 不含业务判断逻辑 |
| `core/registry.py` | 步骤注册表 STEP_SPECS | 不含步骤执行逻辑 |
| `core/stage_plugin.py` | StagePlugin 抽象基类 | 不含具体步骤实现 |
| `core/context.py` | StageContext / StageResult 数据结构 | 不含业务字段 |
| `core/engines/generation.py` | 步骤编排主引擎 | 不含具体处理算法 |
| `core/design/export_adapter.py` | 从 DesignEngine 生成 MD 包 | 不直接写 artifacts/ |
| `core/adapters/` | AI 模型适配器（codex/openai/claude） | 不含业务提示词 |

### 2.2 pipeline/ — 步骤业务层（主修改区）

| 模块 | 职责 | 允许的依赖 |
|------|------|-----------|
| `plugin.py` | 编排：run_import_step + helpers 调用 | core/*, helpers.py |
| `helpers.py` | 所有业务处理类 | core/io, core/paths |
| `data/*.json` | 步骤静态数据 | 无 Python 依赖 |
| `prompts/` | AI 提示词 | 无 Python 依赖 |

### 2.3 跨步骤依赖（只读，不允许直接调用）

```
step_03/helpers.py  import  extract_l5_entities  from step_02/helpers.py  ← 允许（纯函数）
step_04/helpers.py  import  extract_l5_entities  from step_02/helpers.py  ← 允许（纯函数）
step_03/helpers.py  import  step_01/helpers.py                             ← 禁止（应读文件）
```

---

## 三、关键数据结构定义

### 3.1 StageContext（运行时上下文）

```python
@dataclass
class StageContext:
    stage_id: str                    # "00" ~ "15"
    stage_dir: Path                  # sandbox/outputs/artifacts/stage_XX/
    source_dir: Path                 # sandbox/source_artifacts/
    save_dir: Path                   # saves/{id}/workspace/
    test_mode: bool = False          # True 时跳过实际处理
    adapter_name: str = "codex"      # AI 适配器名称
    extra: dict = field(default_factory=dict)
```

### 3.2 通用输出文件字段约定

所有步骤输出的 JSON 文件必须包含以下顶层字段：

```json
{
  "schema_version": 1,
  "generated_at": "ISO8601时间戳",
  "source": "来源文件路径（相对项目根）",
  ...具体业务字段...
}
```

### 3.3 DesignEntity 标准结构

```python
{
    "entity_id": "ENT-001",           # 格式: ENT-NNN
    "label": "具体实体名称",           # 人类可读，非节点 ID
    "kind": "character|enemy|weapon|ability|room|resource|ui|system",
    "schema": "schema_type.v1",       # 对应 knowledge/schemas/ 下的 schema 文件名
    "source": "来源文件路径:行号",
    "source_selection_id": "SEL-XXX", # 对应的设计选择 ID
    "node_id": "design_node_id",      # 对应 DesignEngine 的节点 ID
    "dependencies": ["node_id_1"],    # 依赖的其他节点
    "purpose": "实体用途描述"
}
```

---

## 四、系统扩展点设计

### 4.1 新增品类模板

**位置**: `pipeline/step_01_gameplay_framework/data/genre_templates.json`  
**格式**: 新增顶层 key，值为 `{"core_loop": [...], "systems": [...]}`  
**生效范围**: LoopExtractor + SystemDeducer 自动读取

### 4.2 新增 Entity Schema 转换器

**位置**: `pipeline/step_03_program_requirements/helpers.py`  
**扩展点**: `EntityToRequirementConverter.SCHEMA_ROUTES` dict  
**步骤**: 添加 `"new_type": "描述文本"` 即可生效，GenericConverter 兜底

### 4.3 新增流水线步骤

1. 在 `pipeline/` 创建 `step_NN_name/` 目录
2. 实现 `plugin.py`（继承 StagePlugin）
3. 在 `pipeline/_registry.json` 注册
4. 在 `core/registry.py` STEP_SPECS 添加
5. 在 `pipeline/artifact_layer/registry.json` 声明制品依赖

---

## 五、性能约束

| 操作 | 目标时长 | 当前状态 |
|------|---------|---------|
| 单步骤处理（不含 AI） | < 3秒 | 未测量 |
| AI 接口调用（单次） | < 30秒 | 依赖网络 |
| 全流水线（无 AI）| < 30秒 | 未测量 |
| 文件读取（_load_templates） | < 100ms | 需缓存 |
