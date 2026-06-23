# 数据流与数据契约

## 一、步骤间数据传递规范

### 原则

1. **文件为界**: 步骤间通过 `sandbox/outputs/artifacts/stage_XX/` 下的 JSON/MD 文件传递数据，不允许直接调用上游步骤的 Python 类
2. **Schema 验证**: 每个步骤在读取上游数据时，必须验证文件存在且关键字段非空；验证失败应 raise `DataInheritanceError`，而非静默返回空值
3. **向前兼容**: 字段新增时添加默认值，不删除现有字段（由下游步骤依赖）

---

## 二、完整数据流映射

### Step 00 → Step 01

**写出文件**: `sandbox/outputs/artifacts/stage_00/design_extraction.json`

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "source": "...concept.md",
  "project_name": "string",
  "genre": "string",
  "selections": [
    {
      "item_type": "核心循环|系统图|...",
      "option": "选项文本",
      "purpose": "用途描述",
      "label": "可读标签",
      "source": "文件:行号",
      "id": "SEL-XXX"
    }
  ],
  "raw_text": "原始 MD 全文"
}
```

**消费方**: `LoopExtractor.extract(parsed)` — `parsed` 即此文件内容

---

### Step 01 → Step 02

**写出文件**: `sandbox/outputs/artifacts/stage_01/system_definitions.json`

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "source": "...framework.md",
  "template_key": "roguelike_action|fps|puzzle|generic",
  "systems": [
    {
      "id": "SYS-COMBAT",
      "name": "即时战斗系统",
      "responsibility": "处理攻击、受击、移动与战斗反馈",
      "source": "genre_template|explicit",
      "confidence": "fallback|explicit"
    }
  ],
  "system_count": 7,
  "definition_rate": 1.0
}
```

**消费方**: `GraphGenerator.generate(system_graph, entity_report)` — `system_graph` 来自此文件或 `system_relation_graph.json`

---

### Step 02 → Step 03 + Step 04

**写出文件**: `sandbox/outputs/artifacts/stage_02/entity_coverage_report.json`

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "source": "...design.md",
  "entities": [
    {
      "entity_id": "ENT-001",
      "label": "武器: 短剑",
      "kind": "weapon",
      "schema": "inferred.weapon.v1|explicit.weapon.v2",
      "source": "文件:行号",
      "source_selection_id": "SEL-XXX",
      "node_id": "weapon_design_node",
      "dependencies": [],
      "purpose": "...",
      "inference": {"mode": "local_selection_fallback|l5_explicit", "reason": "..."}
    }
  ],
  "entity_count": 47,
  "concrete_node_count": 103,
  "covered_concrete_nodes": 47,
  "entity_coverage_rate": 0.4563
}
```

**消费方**:
- `extract_l5_entities(parsed)` — 直接传入此文件内容（step_03, step_04 共用）
- 注意: `extract_l5_entities` 接受 `parsed` 即 `design.md` 解析结果，不是此 JSON

---

### Step 03 → Step 05

**写出文件**: `sandbox/outputs/artifacts/stage_03/program_requirements_contract.json`

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "valid": true,
  "source": "...design.md",
  "requirements": [
    {
      "id": "REQ-001",
      "requirement": "实现并验证...",
      "entity_id": "ENT-001",
      "entity_label": "武器: 短剑",
      "entity_kind": "weapon",
      "entity_schema": "inferred.weapon.v1",
      "selection_id": "SEL-XXX",
      "source_refs": ["文件:行号"],
      "phase": "core_playable|progression|economy|content_ops",
      "system_ids": ["SYS-COMBAT"],
      "system_binding": {
        "system_id": "SYS-COMBAT",
        "confidence": 1.0,
        "method": "dependency_id|fuzzy_name|unmatched"
      },
      "inputs": ["entity_definition", "design_node_id"],
      "outputs": ["schema_type/label.asset"],
      "dependencies": ["design_node_id"],
      "acceptance": "可验证的验收标准描述",
      "trace_kind": "design_entity|selection"
    }
  ]
}
```

---

### Step 04 → Step 06

**写出文件**: `sandbox/outputs/artifacts/stage_04/asset_registry.json`

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "assets": [
    {
      "asset_id": "ASSET-001",
      "name": "资产名称",
      "asset_type": "ui|effect|environment|audio|config|art_asset",
      "source": "文件:行号",
      "source_entity_id": "ENT-001",
      "source_node_id": "design_node_id",
      "purpose": "用途描述",
      "dependencies": ["design_node_id"],
      "unlocks": ["program_requirements", "art_production"],
      "priority": "P0|P1|P2|P3",
      "complexity": "xs|s|m|l|xl",
      "required_for_phase": "core_playable|progression|economy|content_ops",
      "status": "requirement_defined",
      "trace_kind": "design_entity|selection"
    }
  ],
  "asset_count": 50
}
```

---

## 三、跨步骤字段依赖矩阵

| 字段 | 生产步骤 | 消费步骤 | 消费方式 |
|------|---------|---------|---------|
| `selections[].item_type` | Step 00 | Step 01,02,03,04 | 关键词匹配 |
| `selections[].id (SEL-XXX)` | Step 00 | Step 02,03,04 | entity_id 构建 |
| `systems[].id (SYS-XXX)` | Step 01 | Step 03 | system_binding |
| `entities[].node_id` | Step 02 | Step 03,04 | dependency 匹配 |
| `entities[].kind` | Step 02 | Step 03,04 | 路由/分类 |
| `requirements[].system_ids` | Step 03 | Step 05 | binding_rate 计算 |
| `assets[].priority` | Step 04 | Step 06 | 规格检查 |

---

## 四、错误传播规则

| 错误类型 | 处理策略 | 示例 |
|---------|---------|------|
| 上游文件缺失 | 使用品类模板兜底，在输出中记录 `fallback_used: true` | Step 01 读不到 design_extraction.json |
| 字段为空/null | `_text(value)` 统一返回 `""` 而非 crash | entity.label 为 null |
| Schema 类型不匹配 | 记录 invalid_entities，跳过该实体 | entity.kind 不在已知列表中 |
| AI 调用失败 | 重试3次后使用离线回退，流水线继续 | Codex API 超时 |
| 覆盖率低于阈值 | 记录警告，继续执行（不 BLOCK） | entity_coverage < 0.8 |

---

## 五、Hades 模板专项数据流分析

### 当前状态（55/100 得分下的数据流）

```
export_adapter.py
  → design.md 含有 47 条 L4 设计决策文本（无 L5 实体）
  
extract_l5_entities(parsed)
  → 未找到 item_type="L5实体" 的选择
  → 回退到 _synthetic_entities()
  → 生成47个 inference.mode="local_selection_fallback" 的合成实体
  
EntityValidator.validate()
  → entity_coverage_rate = 47/103 = 0.4563
  → 未达目标0.8
```

### 目标状态（75/100 时的数据流）

```
用户在 DesignEngine 填写 L5 实体（武器/角色/技能/房间）
  → design.md 中出现 "- L5实体: [名称]" 格式行
  
extract_l5_entities(parsed)
  → 找到 item_type="L5实体" 的选择
  → 生成真实 L5 实体（kind=weapon/character/ability/room）
  → entity_coverage_rate ≥ 0.80
  
EntityToRequirementConverter.convert()
  → 每个 weapon 实体 → 3条具体需求（命中/伤害/反馈）
  → 每个 character 实体 → 4条具体需求（属性/状态/输入/成长）
  → 需求质量从"实现 L4 决策" 提升到"实现具体游戏机制"
```
