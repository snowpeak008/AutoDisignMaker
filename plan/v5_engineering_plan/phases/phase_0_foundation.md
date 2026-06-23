# Phase 0 — 基础设施（Week 1）

## 目标

建立开发基础，确保 PLAN-002 不复现，搭建测试和代码质量基础设施。

---

## 任务清单

### P0-T01 — 验证 PLAN-002 修复

**负责人**: 开发者  
**估时**: 4h  
**验证命令**:
```bash
python tools/validators/pipeline_quality.py --check plan-002
# 期望: entity_coverage_rate >= 0.38 (Hades 模板)
```

**判断条件**:
- 通过: `entity_coverage_rate >= 0.38` → 继续 Phase 1
- 失败: 立即检查 `core/design/export_adapter.py` 中 `_append_l5_design_entities` 的调用路径

---

### P0-T02 — 搭建 pytest 基础设施

**估时**: 3h

**文件结构**:
```
core/tests/
├── conftest.py              # 公共 fixtures（sample_parsed_dict, sample_entities, ...）
├── unit/
│   └── test_pipeline_optimization_helpers.py  # 已存在，扩展
└── integration/
    └── test_step_integration.py    # 全流水线集成测试
```

**conftest.py 关键 fixture**:
```python
@pytest.fixture
def parsed_with_l5_entities():
    return {
        "selections": [
            {"item_type": "L5实体", "option": "短剑", "purpose": "kind=weapon；schema=weapon.v1", "id": "SEL-001", "dependencies": ["weapon_node"]},
        ],
        "raw_text": "Hades roguelike",
        "source": "test/design.md"
    }

@pytest.fixture
def parsed_no_l5():
    return {
        "selections": [
            {"item_type": "核心循环", "option": "进入 -> 战斗 -> 奖励", "id": "SEL-001"}
        ],
        "raw_text": "roguelike action",
        "source": "test/concept.md"
    }
```

---

### P0-T03 — 配置 pre-commit hooks

**估时**: 2h

**.pre-commit-config.yaml**:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black
        args: [--line-length=100]
  - repo: https://github.com/PyCQA/flake8
    rev: 7.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=100, --ignore=E203,W503]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports]
        additional_dependencies: [types-PyYAML]
```

**安装**:
```bash
pip install pre-commit
pre-commit install
```

---

### P0-T04 — L5 实体录入规范文档

**估时**: 2h  
**输出文件**: `knowledge/governance/L5_ENTITY_GUIDE.md`

**核心内容**:
1. 在 DesignEngine 中打开项目
2. 导航到需要添加实体的设计节点（L4 决策层）
3. 点击"添加 L5 实体"
4. 填写: `label`（具体游戏对象名）、`kind`（weapon/character/ability/room/resource/ui）、`schema`
5. 至少为以下节点添加实体:
   - `weapon_design_node` → 主角武器列表（≥3个）
   - `enemy_design_node` → 敌人类型（≥3个）
   - `ability_design_node` → 技能/祝福（≥5个）
   - `room_design_node` → 房间类型（≥3个）
   - `resource_design_node` → 货币/资源（≥2个）

---

### P0-T05 — 创建步骤脚手架工具

**估时**: 3h  
**文件**: `tools/dev/scaffold_step.py`

```python
"""
用法: python tools/dev/scaffold_step.py --step 16 --name new_stage
生成: pipeline/step_16_new_stage/ 标准目录结构
"""
```

---

## Phase 0 验收标准

- [ ] `python tools/validators/pipeline_quality.py --check plan-002` 通过
- [ ] `pytest core/tests/` 无报错（至少10个测试用例通过）
- [ ] `pre-commit run --all-files` 无错误
- [ ] L5 实体录入规范文档已创建

## 风险

| 风险 | 概率 | 应对 |
|------|------|------|
| PLAN-002 验证失败 | 中 | 预留3天修复，检查 export_adapter._append_l5_design_entities |
| mypy 严格模式报错过多 | 高 | 先用 --ignore-missing-imports，后续逐步提升 |
