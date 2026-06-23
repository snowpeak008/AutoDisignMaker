# 数据契约规范

## 一、通用规范

所有步骤输出的 JSON 文件必须包含以下字段：

```json
{
  "schema_version": 1,
  "generated_at": "2026-06-23T19:04:00",
  "source": "相对项目根的来源文件路径"
}
```

---

## 二、核心数据类型定义

### DesignEntity（设计实体）

```json
{
  "entity_id": "ENT-001",
  "label": "短剑",
  "kind": "weapon",
  "schema": "inferred.weapon.v1",
  "source": "design.md:42",
  "source_selection_id": "SEL-010",
  "node_id": "weapon_design_node",
  "dependencies": ["weapon_design_node"],
  "purpose": "kind=weapon；schema=weapon.v1"
}
```

**kind 合法值**: `weapon|character|enemy|ability|room|resource|ui|scene|system|config|audio|design_selection`

---

### ProgramRequirement（程序需求）

```json
{
  "id": "REQ-001",
  "requirement": "实现 L5实体"短剑"的武器输入、命中、伤害和反馈。",
  "entity_id": "ENT-001",
  "entity_label": "短剑",
  "entity_kind": "weapon",
  "entity_schema": "inferred.weapon.v1",
  "selection_id": "SEL-010",
  "source_refs": ["design.md:42"],
  "phase": "core_playable",
  "system_ids": ["SYS-COMBAT"],
  "system_binding": {
    "system_id": "SYS-COMBAT",
    "confidence": 1.0,
    "method": "dependency_id"
  },
  "inputs": ["entity_definition", "weapon_design_node"],
  "outputs": ["inferred_weapon_v1/短剑.asset"],
  "dependencies": ["weapon_design_node"],
  "acceptance": "实体"短剑"有可执行数据结构、运行时行为和至少一条验证路径。",
  "trace_kind": "design_entity"
}
```

**system_binding.method 合法值**: `dependency_id|design_node_dependency|fuzzy_name|unmatched`  
**phase 合法值**: `core_playable|progression|economy|content_ops|social|launch_ops`

---

### ArtAsset（美术资产）

```json
{
  "asset_id": "ASSET-001",
  "name": "短剑_攻击特效",
  "asset_type": "effect",
  "source": "design.md:42",
  "source_entity_id": "ENT-001",
  "source_node_id": "weapon_design_node",
  "purpose": "为实体"短剑"提供动作、命中、奖励或状态变化特效。",
  "dependencies": ["weapon_design_node"],
  "unlocks": ["program_requirements", "art_production"],
  "priority": "P0",
  "complexity": "m",
  "required_for_phase": "core_playable",
  "status": "requirement_defined",
  "trace_kind": "design_entity"
}
```

**asset_type 合法值**: `ui|effect|environment|audio|config|art_asset|animation`  
**priority 合法值**: `P0|P1|P2|P3`  
**complexity 合法值**: `xs|s|m|l|xl`

---

### ReviewIssue（评审问题）

```json
{
  "severity": "WARNING",
  "stage": "stage_03",
  "artifact": "program_requirements_contract.json",
  "field": "REQ-001",
  "reason": "Requirement is not bound to a system.",
  "suggestion": "Bind by dependency id or fuzzy system match."
}
```

**severity 合法值**: `BLOCKER|CRITICAL|WARNING|INFO`

---

### ReviewReport（评审报告）

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "scope": "program_requirements",
  "issues": [...],
  "severity_counts": {"BLOCKER": 0, "CRITICAL": 0, "WARNING": 4, "INFO": 0},
  "blocker_count": 0,
  "critical_count": 0,
  "requires_action_count": 0,
  "blocking_issue_count": 0,
  "warning_count": 4
}
```

---

## 三、步骤输出文件清单

| 步骤 | 文件 | 关键字段 |
|------|------|---------|
| 00 | `design_extraction.json` | selections, raw_text |
| 00 | `concept_profile.json` | project_positioning, core_loop |
| 00 | `core_question_coverage_report.json` | coverage_rate, questions |
| 01 | `core_loop.json` | loop, source_kind, output_rate |
| 01 | `system_definitions.json` | systems, system_count |
| 01 | `system_relation_graph.json` | nodes, edges, cycle_free |
| 02 | `entity_coverage_report.json` | entities, entity_coverage_rate |
| 02 | `entity_dependency_graph.json` | nodes, edges, cycle_free |
| 02 | `entity_phase_classification.json` | phases |
| 03 | `program_requirements_contract.json` | requirements |
| 03 | `requirement_quality_report.json` | binding_rate, placeholder_rate |
| 04 | `asset_registry.json` | assets, asset_count |
| 05 | `ProgReview_report.json` | verdict, issues |
| 06 | `ArtReview_report.json` | verdict, issues |

---

## 四、字段演化规范

### 新增字段

- 在对应步骤的 `helpers.py` 处理类中添加
- 为新字段提供默认值（不得破坏下游消费）
- 在本文档对应表格中更新

### 废弃字段

- 保留旧字段至少2个完整迭代周期
- 在字段值上添加 `_deprecated_` 前缀作为标记
- 彻底删除前确认无下游消费

### 版本变更

- `schema_version` 仅在破坏性变更时递增（如字段重命名、类型变更）
- 新增字段不需要递增版本
