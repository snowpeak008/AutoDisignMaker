# Bug 收集文档（第三轮）

**扫描时间**: 2026-06-23  
**范围**: 本轮新增/修改的全部文件

---

## BUG-010 — 中等 | "build" 关键词导致阶段分类错误

**文件**: `pipeline/step_02_design_review_freeze/helpers.py:337`  
**函数**: `PhaseClassifier._phase_for`

```python
if any(token in text for token in (
    "release", "launch", "analytics", "telemetry",
    "build",    # ← 问题所在
    "运营", "发布", "上线", "埋点", "数据分析",
)):
    return "launch_ops"
```

`"build"` 是英文中性词，会匹配 Hades 项目中 `build_system_decision`（构筑成长系统）的标签，导致该实体被错误分类为 `launch_ops`（发布运营阶段），而正确分类应为 `core_playable`。

**修复**: 移除 `"build"` 关键词，或改为更精确的词组：`"release_build"`, `"build_pipeline"`。

---

## BUG-011 — 中等 | `@lru_cache` 导致测试间缓存污染

**文件**: `pipeline/step_01_gameplay_framework/helpers.py:39`

```python
@lru_cache(maxsize=1)
def _load_templates() -> dict[str, Any]:
    payload = read_json(GENRE_TEMPLATES_PATH, {})
    return payload if isinstance(payload, dict) else {}
```

`lru_cache` 挂在模块级函数上，整个 pytest 进程共享同一份缓存。问题：

1. 若 `genre_templates.json` 在首次调用时不存在（返回 `{}`），后续补充文件后仍返回 `{}`，缓存不会刷新。
2. 测试无法通过 `monkeypatch` 替换模板数据，因为缓存拦截在 `read_json` 调用之前。

**修复**: 将缓存移到调用方（调用时只取一次），或在 `conftest.py` 中添加 `_load_templates.cache_clear()` fixture：

```python
@pytest.fixture(autouse=True)
def clear_template_cache():
    from pipeline.step_01_gameplay_framework.helpers import _load_templates
    _load_templates.cache_clear()
    yield
    _load_templates.cache_clear()
```

---

## BUG-012 — 低 | `MarketResearchSkill` 只对 roguelike 读取市场库

**文件**: `pipeline/step_04_art_requirements/helpers.py:172`  
**函数**: `MarketResearchSkill.local_fallback`

```python
if any(token in raw_text for token in ("hades", "rogue", "肉鸽")):
    library = self._library_reference("roguelike")   # ✅ 读库
    if library:
        return library
    ...
elif any(token in raw_text for token in ("puzzle", "解谜")):
    references = [...]                                # ❌ 不读库，直接硬编码
    style = "clean_puzzle_readability"
else:
    references = [...]                                # ❌ 不读库
```

如果 `knowledge/market_data/fps.json` 或 `puzzle.json` 存在，fps 和 puzzle 品类的游戏也不会使用这些库，永远走硬编码 fallback。

**修复**: 对每个品类都先尝试读库，库缺失时再 fallback：

```python
for key in ("roguelike", "fps", "puzzle"):
    if any(token in raw_text for token in genre_tokens[key]):
        library = self._library_reference(key)
        if library:
            return library
        break
```

---

## BUG-013 — 低 | `EntityToAssetConverter._phase_for` 只覆盖3个阶段

**文件**: `pipeline/step_04_art_requirements/helpers.py:155`  
**函数**: `EntityToAssetConverter._phase_for`

```python
def _phase_for(self, entity):
    ...
    if any(token in text for token in ("currency", "resource", "economy", "资源")):
        return "economy"
    if any(token in text for token in ("room", "enemy", "content", "房间", "敌人")):
        return "content_ops"
    return "core_playable"  # ← 所有其他情况都落这里
```

与 `PhaseClassifier._phase_for`（step_02，6个阶段）不一致：`progression`、`social`、`launch_ops` 阶段永远不会出现在 `asset.required_for_phase` 字段中。

**修复**: 与 step_02 的分类逻辑对齐，补全 progression/social/launch_ops 的关键词判断。

---

## BUG-014 — 低 | `_verdict` 阈值过宽，1-15 个警告仍返回 "PASS"

**文件**: `pipeline/step_05_program_review/helpers.py:345`  
**函数**: `IntelligentReviewer._verdict`

```python
def _verdict(self, blocker_count, critical_count, warning_count) -> str:
    if blocker_count:
        return "BLOCKED"
    if critical_count:
        return "FAIL"
    if warning_count > 15:    # ← 1-15 个警告不改变 verdict
        return "WARN"
    return "PASS"
```

当 `warning_count` 为 1-15 时，verdict 仍返回 `"PASS"`。这与质量门禁文档的描述不一致（"PASS+warns → 80分"暗示有警告应是 WARN 状态）。调用方看到 PASS 但 `warning_count > 0` 时容易产生误判。

**修复**: 改为 `if warning_count > 0: return "WARN"`，或在调用方明确检查 `warning_count` 而不只看 verdict。

---

## 汇总

| ID | 严重程度 | 文件 | 问题简述 |
|----|---------|------|---------|
| BUG-010 | 中等 | `step_02/helpers.py:337` | `"build"` 关键词误判 `launch_ops` |
| BUG-011 | 中等 | `step_01/helpers.py:39` | `@lru_cache` 导致测试间缓存污染 |
| BUG-012 | 低 | `step_04/helpers.py:172` | fps/puzzle 不读市场库，只用硬编码 |
| BUG-013 | 低 | `step_04/helpers.py:155` | 资产阶段只覆盖3/6个阶段 |
| BUG-014 | 低 | `step_05/helpers.py:345` | 1-15 警告仍返回 PASS，verdict 不精确 |
