# 测试策略

## 一、测试层级

```
core/tests/
├── unit/                    # 纯函数和类方法的隔离测试
│   └── test_step_XX_*.py    # 每步骤一个文件
├── integration/             # 跨模块/跨步骤的数据流测试
│   └── test_pipeline_*.py
└── fixtures/                # 共享测试数据
    ├── hades_design.json    # Hades 项目解析后数据
    ├── empty_roguelike.json # 空白 roguelike parsed 数据
    └── minimal_concept.json # 最小有效 concept 数据
```

---

## 二、单元测试规范

### 测试命名约定

```
test_{类名}_{方法名}_{场景描述}
```

示例:
```python
def test_question_engine_evaluate_with_no_selections_returns_zero_coverage():
def test_entity_validator_validate_with_103_nodes_computes_correct_rate():
def test_system_binder_bind_returns_unmatched_when_no_nodes():
```

### 覆盖率目标

| 模块 | 目标覆盖率 | 重点用例 |
|------|-----------|---------|
| `step_00/helpers.py` | ≥ 80% | 覆盖率计算、fallback 路径、空输入 |
| `step_01/helpers.py` | ≥ 80% | 显式循环解析、模板选择、系统去重 |
| `step_02/helpers.py` | ≥ 80% | L5实体提取、合成回退、环检测 |
| `step_03/helpers.py` | ≥ 75% | 转换路由、绑定三级策略、空系统图 |
| `step_04/helpers.py` | ≥ 75% | 资产类型映射、优先级、多资产生成 |
| `step_05/helpers.py` | ≥ 80% | 占位符检测、verdict 判定、分级计数 |

### 关键测试场景（每模块必须覆盖）

**step_00**:
```python
# 场景1: 无 selections → coverage = 0, fallback_used = True
# 场景2: 含核心循环选择 → CQ-005 answered = True
# 场景3: coverage < 0.4 → needs_ai_supplement 标志正确
# 场景4: questions_path 不存在 → self.questions = [], coverage = 0
```

**step_02**:
```python
# 场景1: 含 L5实体 selections → 提取真实实体，不走 _synthetic_entities
# 场景2: 无 L5实体 selections → 走 _synthetic_entities 回退
# 场景3: parsed 有 design_summary.node_count=103 → expected_total = 103
# 场景4: A→B→A 环路 → _cycles 返回非空列表
# 场景5: 无环图 → cycle_free = True
```

**step_03**:
```python
# 场景1: weapon 实体 → SCHEMA_ROUTES["weapon"] 路由正确
# 场景2: 未知 kind → "通用数据、行为和验收规则" 回退
# 场景3: dependency_id 精确匹配 → method="dependency_id", confidence=1.0
# 场景4: score < 0.4 → method="unmatched", system_id=""
# 场景5: 空 requirements → system_binding_rate = 0.0
```

---

## 三、集成测试规范

### Step 间数据流测试

```python
class TestPipelineDataFlow:
    def test_step00_output_is_valid_step01_input(self, tmp_path):
        """Step 00 的 design_extraction.json 必须能被 Step 01 正确消费。"""
        # 1. 运行 Step 00 生成 design_extraction.json
        # 2. 加载该文件
        # 3. 运行 LoopExtractor.extract(parsed)
        # 4. 断言 loop 非空，output_rate = 1.0

    def test_step02_entity_report_consumed_by_step03(self, parsed_with_l5_entities):
        """Step 02 生成的实体必须能被 Step 03 转换为需求。"""
        entities = extract_l5_entities(parsed_with_l5_entities)
        converter = EntityToRequirementConverter()
        reqs = converter.convert(parsed_with_l5_entities)
        assert len(reqs) == len(entities)
        assert all(r.get("requirement") for r in reqs)
```

### E2E 测试（基于 Hades 存档）

```python
class TestHadesE2E:
    @pytest.mark.slow
    def test_hades_full_pipeline_quality(self, hades_save_dir):
        """验证 Hades 存档全流水线指标。"""
        coverage = load_json(hades_save_dir / "stage_00" / "core_question_coverage_report.json")
        assert coverage["coverage_rate"] >= 0.40

        loop = load_json(hades_save_dir / "stage_01" / "core_loop.json")
        assert len(loop["loop"]) >= 4

        entity = load_json(hades_save_dir / "stage_02" / "entity_coverage_report.json")
        assert entity["entity_count"] >= 20

        prog_review = load_json(hades_save_dir / "stage_05" / "ProgReview_report.json")
        assert prog_review["verdict"] in ("PASS", "WARN")
```

---

## 四、测试数据管理

### fixtures/hades_design.json 结构

```json
{
  "selections": [
    {"item_type": "项目规模", "option": "indie", "id": "SEL-001", "source": "test:1"},
    {"item_type": "核心循环", "option": "进入 -> 战斗 -> 奖励 -> 构筑", "id": "SEL-002"},
    {"item_type": "L5实体", "option": "短剑", "purpose": "kind=weapon；schema=weapon.v1", "id": "SEL-010", "dependencies": ["weapon_node"]}
  ],
  "raw_text": "Hades roguelike action game",
  "source": "test/design.md",
  "design_summary": {"node_count": 103}
}
```

### Mock AI 调用

```python
@pytest.fixture
def mock_ai_adapter(monkeypatch):
    """替换 AI 调用为固定返回值，测试不依赖网络。"""
    def fake_call(prompt, context, fallback=None):
        return fallback or {}
    monkeypatch.setattr("core.adapters.codex_adapter.CodexAdapter.call", fake_call)
```

---

## 五、运行命令

```bash
# 仅单元测试（快速）
pytest core/tests/unit/ -v

# 全部测试（含集成）
pytest core/tests/ -v --tb=short

# 带覆盖率
pytest core/tests/ --cov=pipeline --cov-report=term-missing

# 跳过慢速 E2E 测试
pytest core/tests/ -v -m "not slow"

# 只运行特定步骤的测试
pytest core/tests/ -k "step_02" -v
```
