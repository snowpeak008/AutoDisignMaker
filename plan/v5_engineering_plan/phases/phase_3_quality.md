# Phase 3 — 质量提升（Weeks 8-9）

## 目标

评审逻辑增强，所有代码通过质量检查，综合质量达到 ≥ 70/100。

---

## Week 8 — 评审增强

### 任务

| 编号 | 任务 | 估时 |
|------|------|------|
| W8-T01 | 为 `IntelligentReviewer.review_program` 增加内容深度检查（需求文本长度/关键词密度）| 4h |
| W8-T02 | 增加 placeholder_rate BLOCKER 阈值（>50% 占位符 → BLOCKED）| 2h |
| W8-T03 | 为 `review_art` 增加资产类型覆盖检查（缺少 effect/ui/scene 中任意一类 → CRITICAL）| 3h |
| W8-T04 | 端到端测试：旧占位符需求 → 应返回 BLOCKED；新实体驱动需求 → 应返回 PASS | 3h |
| W8-T05 | 修复 BUG-009：`requires_action_count = blocker_count + critical_count` | 1h |

### 内容深度检查规范

```python
def _check_requirement_depth(self, requirement: dict) -> None:
    """检查需求是否具有足够的业务深度。"""
    text = _text(requirement.get("requirement", ""))
    
    # 深度不足的信号: 过短或只包含实体 ID
    if len(text) < 15:
        self._add_issue("WARNING", ..., "需求文本过短，可能缺乏业务细节")
    
    # L4 决策格式的需求（来自合成实体）仍应标记
    if "：Hades 范本反推" in text or "项目配置" in text:
        self._add_issue("WARNING", ..., "需求来自 L4 设计决策，建议补充 L5 实体以生成更具体的需求")
```

---

## Week 9 — 集成与代码质量

### 任务

| 编号 | 任务 | 估时 |
|------|------|------|
| W9-T01 | 全流水线端到端测试（Hades + 1个空白 roguelike）| 6h |
| W9-T02 | mypy 修复：消除所有 `error` 级别报错 | 4h |
| W9-T03 | flake8 修复：消除所有警告 | 2h |
| W9-T04 | 性能分析：识别 >1秒 的热点，加缓存或延迟加载 | 3h |
| W9-T05 | 代码审查：所有 helpers.py 公共方法添加 one-line docstring | 3h |
| W9-T06 | 更新 `knowledge/ai_memory/INDEX.md` 和会话记录 | 1h |

### 代码质量检查命令

```bash
# 类型检查
mypy pipeline/step_00_idea_intake/helpers.py \
     pipeline/step_01_gameplay_framework/helpers.py \
     pipeline/step_02_design_review_freeze/helpers.py \
     pipeline/step_03_program_requirements/helpers.py \
     pipeline/step_04_art_requirements/helpers.py \
     pipeline/step_05_program_review/helpers.py \
     --ignore-missing-imports

# 风格检查
flake8 pipeline/step_*/helpers.py --max-line-length=100 --ignore=E203,W503

# 格式化
black pipeline/step_*/helpers.py --line-length=100 --check

# 单元测试
pytest core/tests/ -v --tb=short
```

---

## Phase 3 验收标准

- [ ] `mypy` 无 error 级别报错
- [ ] `flake8` 无警告
- [ ] `pytest` 通过率 100%，覆盖率 ≥ 75%
- [ ] 综合质量 ≥ 70/100（Hades 存档）
- [ ] BUG-009 修复验证：`requires_action_count` = blocker + critical
