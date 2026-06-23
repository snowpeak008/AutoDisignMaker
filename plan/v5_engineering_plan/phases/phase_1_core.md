# Phase 1 — 核心模块（Weeks 2-4）

## 目标

完成 Step 00/01/02 的完整业务逻辑实现，使 entity_coverage ≥ 70%，问答覆盖率 ≥ 55%。

---

## Week 2 — Step 00 创意收集增强

### 目标
- 问答覆盖率从 40% 提升到 ≥ 55%
- concept_profile.json 包含有意义的项目定位和循环信息

### 任务

| 编号 | 任务 | 估时 | 输出 |
|------|------|------|------|
| W2-T01 | 审查 `data/core_questions.json`，补充 CQ-005~012 的 `item_types` 和 `keywords` | 3h | 更新后的 JSON |
| W2-T02 | 扩展 `QuestionEngine._evidence_for`：增加 raw_text 多关键词匹配策略 | 3h | 覆盖率提升 |
| W2-T03 | 在 `_fallback_loop` 中补充更多品类关键词（strategy/rpg/moba/tower_defense） | 2h | 通用性提升 |
| W2-T04 | 单元测试：5 个 QuestionEngine 用例，5 个 ConceptProcessor 用例 | 3h | tests/ |
| W2-T05 | 验收：运行 Hades 存档，检查 coverage_rate ≥ 0.55 | 1h | 指标确认 |

### 关键改动点

**`data/core_questions.json` 补充 item_types**:
```json
{
  "id": "CQ-005",
  "domain": "core",
  "question": "核心循环是否明确？",
  "item_types": ["核心循环", "core_loop", "主循环", "玩法循环"],
  "keywords": ["循环", "loop", "->", "→", "进入", "战斗", "奖励", "升级"]
},
{
  "id": "CQ-008",
  "domain": "systems",
  "question": "顶层系统拆分是否明确？",
  "item_types": ["system_layer", "玩法系统", "系统图"],
  "keywords": ["系统", "system", "模块", "战斗系统", "经济系统"]
}
```

**Week 2 验收标准**:
- [ ] Hades 存档 Step 00 运行后 `coverage_rate >= 0.55`
- [ ] CQ-005（核心循环）、CQ-008（系统拆分）至少有一条 evidence
- [ ] 新增单元测试全部通过

---

## Week 3 — Step 01 玩法框架增强

### 目标
- core_loop source_kind 尽量为 "explicit"
- system_definitions 系统名称规范化（去除 "system_layer：" 前缀）

### 任务

| 编号 | 任务 | 估时 | 输出 |
|------|------|------|------|
| W3-T01 | 修复 `_systems_from_graph`：清理 name 中的 "system_layer：" 前缀 | 1h | 规范化系统名 |
| W3-T02 | 扩展 `_pick_template_key`：增加 strategy/rpg/moba 品类识别 | 2h | 品类覆盖提升 |
| W3-T03 | 完善 `data/genre_templates.json` — 补充 strategy/rpg 模板 | 4h | 2个新品类 |
| W3-T04 | 在 `LoopExtractor._explicit_loop` 中增加 "→"、"→ " 的更多分隔符处理 | 1h | 解析健壮性 |
| W3-T05 | 缓存 `_load_templates()`（修复 BUG-008）| 1h | 性能提升 |
| W3-T06 | 单元测试：3个品类各2个用例 | 3h | tests/ |

### 关键改动点

**系统名称规范化**:
```python
def _systems_from_graph(self, system_graph):
    for node in system_graph.get("nodes", []):
        name = _text(node.get("name"))
        # 清理导出格式中的前缀
        name = re.sub(r'^system_layer[：:]\s*', '', name)
        name = re.sub(r'^system[：:]\s*', '', name)
```

**Week 3 验收标准**:
- [ ] system_definitions.json 中系统名不含 "system_layer：" 前缀
- [ ] 新增 strategy 和 rpg 品类模板并通过测试
- [ ] 加载模板只读一次磁盘

---

## Week 4 — Step 02 设计冻结增强

### 目标
- entity_coverage 从 45.6% 提升到 ≥ 70%（依赖用户填写 L5 实体）
- invalid_entities 降低到 0
- GraphGenerator 输出有意义的系统-实体关系图

### 任务

| 编号 | 任务 | 估时 | 输出 |
|------|------|------|------|
| W4-T01 | 完善 `_entity_kind_for`：增加 weapon/enemy/item 关键词映射 | 2h | 实体分类准确性 |
| W4-T02 | 修复 `launch_ops` 阶段永远为空的问题（PhaseClassifier 补充关键词） | 2h | 6个阶段均有数据 |
| W4-T03 | 为 `_synthetic_entities` 生成的实体添加更精细的 `kind` 推断 | 3h | 合成实体质量 |
| W4-T04 | `entity_id` 序号连续化（基于 L5实体计数，非全 selection 计数） | 2h | ENT-001 起连续 |
| W4-T05 | 单元测试：EntityValidator 5个、GraphGenerator 4个 | 4h | tests/ |

**entity_id 连续化**（修复 BUG-007 的副作用）:
```python
# extract_l5_entities: 只对 L5实体 计数
l5_index = 0
for item in parsed.get("selections", []):
    if _text(_field(item, "item_type")) != "L5实体":
        continue
    l5_index += 1
    # entity_id = f"ENT-{l5_index:03d}"
```

**Week 4 验收标准**:
- [ ] entity_id 从 ENT-001 连续编号（无跳号）
- [ ] `launch_ops` 阶段在适当项目下有数据
- [ ] 若用户填写了 ≥40 个 L5 实体，entity_coverage ≥ 0.75

---

## Phase 1 里程碑检查

**运行评估**:
```bash
python tools/validators/pipeline_quality.py --run-full --save-id <当前存档ID>
```

**期望结果**:
- [ ] Step 00 coverage_rate ≥ 0.55
- [ ] Step 01 system_count ≥ 5，系统名规范
- [ ] Step 02 entity_count ≥ 40（需用户填写 L5 实体）
- [ ] 整体评分 ≥ 62/100
