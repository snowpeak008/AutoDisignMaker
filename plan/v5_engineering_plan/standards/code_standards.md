# 代码规范

## 一、Python 代码风格

### 基础规则

| 规则 | 标准 |
|------|------|
| 行宽 | 最大 100 字符 |
| 格式化工具 | black --line-length=100 |
| 风格检查 | flake8 --max-line-length=100 --ignore=E203,W503 |
| 类型检查 | mypy --ignore-missing-imports |
| 导入排序 | isort（black 兼容模式） |

### 类型注解

**强制要求**（所有公共方法）:
```python
# 正确
def evaluate(self, parsed: dict[str, Any]) -> dict[str, Any]:
    ...

# 错误（缺少注解）
def evaluate(self, parsed):
    ...
```

**允许省略**（私有方法、测试文件内）:
```python
def _text(value):           # 模块级私有工具函数可省略
    return str(value or "").strip()
```

### Docstring 规范

**只写 one-line docstring**（说明"做什么"，不说"怎么做"）:
```python
def extract_l5_entities(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """从 parsed.selections 提取 L5实体；无时回退到合成实体。"""
```

**禁止**:
- 多行参数描述（Args/Returns/Raises 格式）
- 重复代码的注释（代码已经说明的不再注释）
- 历史变更记录（属于 git commit message）

---

## 二、模块命名规范

| 对象 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `EntityValidator`, `QuestionEngine` |
| 方法名 | snake_case | `evaluate()`, `_best_binding()` |
| 私有方法 | `_`前缀 | `_explicit_loop()` |
| 常量 | UPPER_SNAKE | `FUZZY_MATCH_MIN_SCORE`, `PLACEHOLDER_TOKENS` |
| 模块文件 | snake_case | `helpers.py`, `genre_templates.json` |
| 步骤目录 | `step_NN_slug/` | `step_02_design_review_freeze/` |

---

## 三、禁止事项

```
❌ 在 plugin.py 中写业务逻辑（只写编排代码）
❌ 在 helpers.py 中直接读/写文件（通过 parsed: dict 参数接收数据）
❌ 跨步骤直接调用类（step_03 不能 import step_02 的类，除纯函数）
❌ 在 core/ 以外写运行时核心逻辑
❌ 硬编码路径字符串（使用 core/paths.py 常量）
❌ 创建超过 400 行的单文件（必须拆分）
❌ 在 helpers.py 中加载超过一次的同一文件（应缓存或传参）
❌ 在 _text() 之外的地方处理 None/空字符串转换
```

---

## 四、plugin.py 模板（每步骤强制格式）

```python
from __future__ import annotations

from core.stage_plugin import StagePlugin
from core.context import StageContext, StageResult
from core.source.groups import SourceGroup
from core.source.importer import run_import_step
from core.engines.generation import apply_development_plan_outputs


class Plugin(StagePlugin):
    stage_id = "NN"  # 替换为实际步骤编号
    _source_groups = [
        SourceGroup("label", ("pattern_*",), "latest", True, ("SourceType",))
    ]

    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.test_mode:
            return StageResult(status="success", outputs={"stage_id": self.stage_id})
        report = run_import_step(int(self.stage_id), self._source_groups, context=ctx)
        result = apply_development_plan_outputs(int(self.stage_id), report)
        return StageResult(
            status=result.get("status", "success"),
            outputs=result,
        )
```

**允许扩展**:
- 添加 try/except 包裹整个 execute 主体，捕获意外异常并返回 `status="error"`
- 在 `apply_development_plan_outputs` 前后添加日志

**禁止**:
- 在 plugin.py 中直接调用 helpers.py 的类（应由 generation.py 编排）
- 在 plugin.py 中添加超过5行的业务判断

---

## 五、helpers.py 设计模式

### 处理类模式（Processor/Validator/Generator/Converter）

```python
class ConceptProcessor:
    """one-line docstring"""

    def build_profile(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """one-line docstring"""
        # 最多3个私有方法调用
        selections = [item for item in parsed.get("selections", []) if item]
        ...

    def _matching_items(self, selections, tokens, *, limit: int) -> list[dict]:
        """one-line docstring（私有方法也要有）"""
        ...
```

### 纯函数模式（跨步骤共享逻辑）

```python
def extract_l5_entities(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """one-line docstring"""
    # 纯函数：无副作用，只依赖参数
    ...
```

### 常量模式（可配置参数放在模块顶部）

```python
FUZZY_MATCH_MIN_SCORE = 0.4    # 可通过单元测试直接 mock
PLACEHOLDER_TOKENS = (...)     # 与实现分离，易于扩展
CORE_QUESTIONS_PATH = ...      # 路径作为模块常量，不硬编码在函数内
```
