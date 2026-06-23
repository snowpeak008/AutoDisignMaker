# Step 05/06 — 评审 实施指南

## 现状评估

| 指标 | 当前值（Hades）| 目标 |
|------|--------------|------|
| ProgReview verdict | PASS | PASS |
| ArtReview verdict | PASS | PASS |
| WARNING 数 | 4 | 0 |
| BLOCKER 数 | 0 | 0 |
| CRITICAL 数 | 0 | 0 |
| 内容深度检查 | 未实现 | 实现 |

---

## 评审逻辑架构

### 职责分离

```
PlaceholderDetector     → 文本占位符检测（与评审器解耦）
IntelligentReviewer     → 整合各类检查，生成结构化报告
  ├── review_program()  → 程序需求评审（调用6个检查方法）
  └── review_art()      → 美术需求评审（调用4个检查方法）
```

### verdict 判定规则（已修复 BUG-006）

```python
"blocker_count": blocker_count,
"critical_count": critical_count,
"requires_action_count": blocker_count + critical_count,  # BUG-009 修复
"blocking_issue_count": blocker_count,
```

---

## 程序评审检查项（Phase 3 增强）

### 现有检查项

| 检查项 | 触发条件 | 级别 |
|--------|---------|------|
| 无 requirements | requirements = [] | BLOCKER |
| 无 source_refs | source_refs 为空 | CRITICAL |
| 无 system_ids | system_ids = [] | WARNING |
| 含占位符 token | 检测到 PLACEHOLDER_TOKENS | CRITICAL |
| 缺 inputs/outputs/deps 字段 | 字段不存在 | INFO |
| 无 acceptance | acceptance 为空 | CRITICAL |

### Phase 3 新增检查项

```python
def _check_requirement_depth(self, issues, stage, artifact, req_id, requirement):
    """检查需求文本是否具有业务深度（而非纯 L4 决策格式）。"""
    text = _text(requirement.get("requirement", ""))
    
    # L4 决策格式的需求（信息价值低）
    if "范本反推" in text or "项目配置" in text or "设计决策节点" in text:
        issues.append(self._issue(
            "WARNING", stage, artifact, req_id,
            "Requirement appears to be derived from L4 design decision rather than L5 entity.",
            "Fill in L5 entities in DesignEngine to generate implementation-level requirements."
        ))
    
    # 过短的需求
    if len(text.strip()) < 15:
        issues.append(self._issue(
            "WARNING", stage, artifact, req_id,
            "Requirement text is too short to describe meaningful behavior.",
            "Expand the requirement to include data structure, behavior, and acceptance path."
        ))
```

---

## 美术评审检查项（Phase 3 增强）

### 现有检查项

| 检查项 | 触发条件 | 级别 |
|--------|---------|------|
| 无 assets | assets = [] | BLOCKER |
| 无 source | source 为空 | CRITICAL |
| 缺 asset_type/purpose/priority | 字段为空 | WARNING |
| purpose 含占位符 | 检测到 PLACEHOLDER_TOKENS | CRITICAL |

### Phase 3 新增检查项

```python
def _check_asset_type_coverage(self, issues, stage, artifact, assets):
    """检查资产类型是否覆盖核心类型（ui/effect 必须存在）。"""
    types_present = {a.get("asset_type") for a in assets}
    required_types = {"ui", "effect"}
    for missing_type in required_types - types_present:
        issues.append(self._issue(
            "CRITICAL", stage, artifact, "asset_types",
            f"No assets of type '{missing_type}' found.",
            f"Generate {missing_type} assets by adding relevant L5 entities."
        ))

def _check_p0_asset_count(self, issues, stage, artifact, assets):
    """检查 P0 资产数量是否足够。"""
    p0_count = sum(1 for a in assets if a.get("priority") == "P0")
    if p0_count == 0:
        issues.append(self._issue(
            "WARNING", stage, artifact, "p0_assets",
            "No P0 priority assets defined.",
            "Mark critical-path assets (character/weapon/core-ui) as P0."
        ))
```

---

## 当前4条 WARNING 分析

来自 REQ-001 ~ REQ-004（对应 selections 中无 dependencies 的合成实体）：
```
REQ-001: 项目规模：indie       → system_ids = [], unmatched
REQ-002: 商业模式：buyout      → system_ids = [], unmatched
REQ-003: 平台范围：multi_platform → system_ids = [], unmatched
REQ-004: 地区范围：global      → system_ids = [], unmatched
```

**根本原因**: 这4条实体的 `dependencies = []`，且关键词无法匹配任何系统。属于 L1 项目配置，不是游戏机制需求，不应触发系统绑定警告。

**Phase 3 修复方向**: 为 "项目配置" 类需求（`trace_kind = "selection"` 且 `phase = "core_playable"`）豁免系统绑定检查。

---

## 实施检查清单

- [ ] Phase 3: 实现 `_check_requirement_depth()` 并集成到 `review_program`
- [ ] Phase 3: 实现 `_check_asset_type_coverage()` 和 `_check_p0_asset_count()`
- [ ] Phase 3: 修复 BUG-009（`requires_action_count = blocker + critical`）
- [ ] Phase 3: 为 L1 项目配置类需求豁免系统绑定 WARNING
- [ ] 验证修复后 Hades 存档 warnings = 0
