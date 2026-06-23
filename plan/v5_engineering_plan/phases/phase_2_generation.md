# Phase 2 — 智能生成（Weeks 5-7）

## 目标

Step 03/04 从合成实体驱动升级为真实 L5 实体驱动，提升需求和资产的业务价值。

---

## Week 5 — AI 适配器强化

### 目标
为高覆盖率问答补全和循环提取提供稳定的 AI 集成基础。

### 任务

| 编号 | 任务 | 估时 |
|------|------|------|
| W5-T01 | 审查 `core/adapters/codex_adapter.py`：确认重试逻辑（3次指数退避）| 2h |
| W5-T02 | 为 Step 00 问答补全添加 AI 触发条件（coverage < 0.4 时自动调用）| 3h |
| W5-T03 | 为 Step 01 循环提取添加 AI 触发条件（source_kind = template_fallback 时可选调用）| 3h |
| W5-T04 | 集成测试：Mock AI 调用，验证回退链路 | 3h |

### AI 触发逻辑规范

```python
# Step 00 中的 AI 触发
coverage = question_engine.evaluate(parsed)["coverage_rate"]
if coverage < 0.40 and ctx.adapter_name != "none":
    adapter = get_adapter(ctx.adapter_name)
    supplemented = adapter.run_guided_interview(
        questions=unanswered_questions,
        context=current_answers,
        fallback=genre_default_answers
    )
    # 合并 supplemented 到 parsed 并重新 evaluate
```

### Week 5 验收标准
- [ ] AI 调用失败时，流水线不中断，使用品类模板回退
- [ ] 回退路径被单元测试覆盖
- [ ] `adapter_name = "none"` 时跳过 AI 调用（离线模式）

---

## Week 6 — Step 03 需求质量提升

### 目标
- 需求从"实现 L4 决策"升级为"实现具体游戏机制"
- 为真实 L5 实体（weapon/character/ability）生成多条针对性需求

### 任务

| 编号 | 任务 | 估时 |
|------|------|------|
| W6-T01 | 扩展 `SCHEMA_ROUTES`：补充 scene/config/audio 路由 | 2h |
| W6-T02 | 为 weapon/character/ability 实体实现多需求生成（每个3条以上）| 5h |
| W6-T03 | 增强 `build_requirement_quality_report`：增加需求密度分析（每系统平均需求数）| 2h |
| W6-T04 | 优化模糊匹配：对中文实体名增加字符串 tokenization | 3h |
| W6-T05 | 单元测试：每种 kind 各2个转换用例 | 4h |

### 多需求生成规范

当实体 kind 为以下类型时，每个实体生成多条需求：

```python
MULTI_REQUIREMENT_KINDS = {
    "weapon": [
        "输入响应与命中判定",
        "伤害计算与状态效果",
        "动画反馈与音效触发",
    ],
    "character": [
        "属性数据结构与初始化",
        "状态机与行为驱动",
        "受击/死亡/复活逻辑",
    ],
    "ability": [
        "触发条件与冷却管理",
        "效果执行与目标选取",
        "视觉反馈与 UI 更新",
    ],
    "room": [
        "生成规则与遭遇配置",
        "出口逻辑与路径选择",
    ],
}
```

### Week 6 验收标准
- [ ] 当有真实 L5 实体时，weapon/ability 实体各产生 ≥3 条需求
- [ ] 需求文本包含具体的游戏机制词汇（不再是"实现 L4 决策"）
- [ ] system_binding_rate ≥ 90%

---

## Week 7 — Step 04 资产质量提升

### 目标
- 资产从通用分类升级为精细分类
- 添加分辨率和格式规格

### 任务

| 编号 | 任务 | 估时 |
|------|------|------|
| W7-T01 | 为 weapon/character/ability 实体生成多条资产（原画/动画/特效/图标）| 5h |
| W7-T02 | 为 P0 资产自动填写 `resolution` 字段规范值 | 2h |
| W7-T03 | 补充 `knowledge/market_data/roguelike.json` 参考库 | 4h |
| W7-T04 | 完善 `MarketResearchSkill`：支持从参考库读取而非仅 fallback | 3h |
| W7-T05 | 单元测试：6个资产转换用例 | 3h |

### 多资产生成规范

```python
MULTI_ASSET_KINDS = {
    "character": ["character_art", "animation_set", "ui_avatar"],
    "weapon":    ["weapon_art", "attack_vfx", "icon"],
    "ability":   ["cast_vfx", "hit_vfx", "icon"],
    "room":      ["scene_art", "tileset", "ambient_audio"],
    "enemy":     ["enemy_art", "attack_vfx", "death_vfx"],
}
```

### Week 7 验收标准
- [ ] 当有 ≥20 个真实 L5 实体时，总资产数 ≥ 80
- [ ] P0 资产均有 `resolution` 字段
- [ ] MarketResearchSkill 优先读取参考库，参考库缺失时才用 fallback

---

## Phase 2 里程碑

- [ ] 综合质量 ≥ 65/100（在用户填写 ≥30 个 L5 实体的前提下）
- [ ] Step 03 需求质量明显高于当前（business 价值可读）
- [ ] Step 04 资产数量 ≥ 80（有真实实体时）
