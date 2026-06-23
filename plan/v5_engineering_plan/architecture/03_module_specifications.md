# 模块规格说明

## 一、Step 00 — helpers.py 模块规格

### ConceptProcessor

```python
class ConceptProcessor:
    """解析 concept.md 中的设计选择，构建结构化项目 Profile。"""

    def build_profile(self, parsed: dict) -> dict:
        """
        输入: parsed = read_json(design_extraction.json)
        输出: {
            "project_positioning": {"label": str, "source": str, "confidence": str},
            "core_loop": {"label": str, "source": str, "confidence": str},
            "key_constraints": [{"label": str, "source": str}],
            "selected_item_count": int,
            "fallback_used": bool
        }
        """

    def _first_matching(self, selections, tokens) -> dict:
        """在 selections 中找第一条包含任意 token 的条目。"""

    def _matching_items(self, selections, tokens, *, limit) -> list[dict]:
        """返回前 limit 条包含任意 token 的条目。"""

    def _fallback_loop(self, raw_text: str) -> str:
        """当无显式循环选择时，从 raw_text 推断通用循环描述。"""
```

### QuestionEngine

```python
class QuestionEngine:
    """从 data/core_questions.json 加载问题库，评估设计数据的回答率。"""

    def __init__(self, questions_path: Path = CORE_QUESTIONS_PATH):
        """加载问题列表；questions_path 不存在时 self.questions = []。"""

    def evaluate(self, parsed: dict) -> dict:
        """
        输出: {
            "total_questions": int,     # 应为 15
            "answered_questions": int,
            "unanswered_questions": int,
            "coverage_rate": float,     # answered / total
            "target_coverage_rate": 0.4,
            "questions": [{"id", "domain", "question", "answered", "evidence": []}]
        }
        """

    def _evidence_for(self, question, selections, raw_text) -> list[dict]:
        """通过 item_types 和 keywords 匹配 evidence 条目。"""
```

**data/core_questions.json 结构**:

```json
[
  {
    "id": "CQ-001",
    "domain": "project",
    "question": "项目的产品定位是什么？",
    "item_types": ["项目定位", "项目规模", "商业模式"],
    "keywords": ["indie", "aa", "aaa", "定位", "规模"]
  },
  {
    "id": "CQ-005",
    "domain": "core",
    "question": "核心循环是否明确？",
    "item_types": ["核心循环"],
    "keywords": ["循环", "loop", "核心玩法", "->", "→"]
  }
]
```

---

## 二、Step 01 — helpers.py 模块规格

### LoopExtractor

```python
class LoopExtractor:
    """从 design_extraction 中提取核心游戏循环节点列表。"""

    def extract(self, parsed: dict) -> dict:
        """
        输出: {
            "loop": ["节点1", "节点2", ...],      # 至少4个节点
            "template_key": "roguelike_action|fps|puzzle|generic",
            "source_kind": "explicit|template_fallback",
            "output_rate": 1.0
        }
        source_kind="explicit" 意味着从用户选择中找到了"核心循环"条目。
        """

    def _explicit_loop(self, selections: list) -> list[str]:
        """查找 item_type="核心循环" 的选择，解析 "A->B->C" 格式。"""
```

### SystemDeducer

```python
class SystemDeducer:
    """基于设计选择和品类模板推导游戏系统列表。"""

    def deduce(self, parsed: dict, system_graph: dict) -> dict:
        """
        输出: {
            "systems": [{"id", "name", "responsibility", "source", "confidence"}],
            "system_count": int,       # 3 <= count <= 8
            "definition_rate": float,  # >= 1.0 时 count >= 5
            "template_key": str
        }
        """

    def _systems_from_graph(self, system_graph: dict) -> list[dict]:
        """从 system_graph.nodes 提取已命名系统（confidence="explicit"）。"""

    def _systems_from_template(self, template, *, existing_names) -> list[dict]:
        """从品类模板补充缺失系统（confidence="fallback"）。"""
```

**data/genre_templates.json 结构**:

```json
{
  "roguelike_action": {
    "core_loop": ["进入房间", "战斗清场", "选择奖励", "升级构筑", "挑战首领"],
    "systems": [
      {"id": "SYS-COMBAT", "name": "即时战斗系统", "responsibility": "处理攻击受击移动与战斗反馈"},
      {"id": "SYS-ROOM",   "name": "房间推进系统", "responsibility": "组织房间遭遇出口和选择"},
      {"id": "SYS-REWARD", "name": "奖励选择系统", "responsibility": "清场后提供祝福资源成长"},
      {"id": "SYS-BUILD",  "name": "构筑成长系统", "responsibility": "累计武器技能组合效果"},
      {"id": "SYS-META",   "name": "局外成长系统", "responsibility": "失败后沉淀永久资源解锁"},
      {"id": "SYS-BOSS",   "name": "首领挑战系统", "responsibility": "阶段性高压战斗和进度检查"}
    ]
  },
  "fps": { ... },
  "puzzle": { ... },
  "generic": { ... }
}
```

---

## 三、Step 02 — helpers.py 模块规格

### extract_l5_entities（模块级函数）

```python
def extract_l5_entities(parsed: dict) -> list[dict]:
    """
    优先从 parsed.selections 中找 item_type="L5实体" 的条目。
    如果没有，回退到 _synthetic_entities(parsed)。
    返回: DesignEntity 字典列表（见 data_contracts.md 3.3节）
    """
```

### EntityValidator

```python
class EntityValidator:
    def validate(self, parsed: dict) -> dict:
        """
        输出: {
            "entities": [...],
            "entity_count": int,
            "concrete_node_count": int,     # 期望总节点数（来自 design_summary 或推断）
            "covered_concrete_nodes": int,  # 有 node_id 的唯一节点数
            "entity_coverage_rate": float,  # covered / total
            "target_coverage_rate": 0.8,
            "missing_entities": [{"node_id": "UNMAPPED-NODE-XXX", "reason": "..."}],
            "invalid_entities": [{"entity_id", "label", "reason"}]
        }
        """
```

**关键**: `_expected_node_count` 优先从 `parsed.design_summary.node_count` 读取期望总数，而非从实体自身推算。

### GraphGenerator

```python
class GraphGenerator:
    def generate(self, system_graph: dict, entity_report: dict) -> dict:
        """
        合并系统节点和实体节点，生成统一依赖图。
        输出: {"nodes": [...], "edges": [...], "cycles": [...], "cycle_free": bool}
        """

    def _cycles(self, node_ids: list[str], edges: list[dict]) -> list[list[str]]:
        """DFS 环路检测，返回每个环的节点路径列表。"""
```

### PhaseClassifier

```python
class PhaseClassifier:
    def classify(self, entity_report: dict) -> dict:
        """
        按实体 label/kind/schema 关键词将实体分配到开发阶段。
        输出: {
            "phases": {
                "core_playable": [...],
                "progression": [...],
                "economy": [...],
                "content_ops": [...],
                "social": [...],
                "launch_ops": []   # 注: 当前无关键词映射到此阶段
            }
        }
        """
```

---

## 四、Step 03 — helpers.py 模块规格

### EntityToRequirementConverter

```python
class EntityToRequirementConverter:
    SCHEMA_ROUTES = {
        "character": "角色行为、状态和交互",
        "enemy":     "敌人行为、攻击模式和生成条件",
        "weapon":    "武器输入、命中、伤害和反馈",
        "ability":   "技能触发、效果、冷却和组合规则",
        "room":      "房间生成、遭遇配置和出口规则",
        "resource":  "资源产出、消耗、存储和展示",
        "ui":        "界面状态、输入反馈和信息层级",
    }  # 扩展时直接添加新 key

    def convert(self, parsed: dict) -> list[dict]:
        """
        对 extract_l5_entities(parsed) 的每个实体生成一条需求。
        输出: ProgramRequirement 字典列表（见 data_contracts.md）
        """
```

### SystemBinder

```python
class SystemBinder:
    FUZZY_MATCH_MIN_SCORE = 0.4  # SequenceMatcher.ratio() 阈值

    def bind(self, requirements: list[dict], system_graph: dict) -> list[dict]:
        """
        三级绑定策略:
        1. dependency_id: requirement.dependencies 与 system node_id 精确匹配
        2. design_node_dependency: dependencies 存在但不在系统节点中（保守绑定）
        3. fuzzy_name: SequenceMatcher 模糊匹配，score >= 0.4
        4. unmatched: system_id="", confidence=0.0
        """
```

---

## 五、Step 04 — helpers.py 模块规格

### EntityToAssetConverter

```python
class EntityToAssetConverter:
    def convert(self, parsed: dict) -> list[dict]:
        """
        对 extract_l5_entities(parsed) 的每个实体生成一条资产需求。
        asset_type 由 entity.kind/schema/label 关键词决定。
        输出: ArtAsset 字典列表（见 data_contracts.md）
        """

    def _asset_type_for(self, entity: dict) -> str:
        """ui > effect > environment > audio > config > art_asset（按优先级）"""

    def _priority_for(self, asset_type: str) -> str:
        """ui/effect/art_asset → P0；其他 → P1"""

    def _complexity_for(self, asset_type: str) -> str:
        """ui/config → s；effect/environment → m；其他 → xs"""
```

---

## 六、Step 05 — helpers.py 模块规格

### PlaceholderDetector

```python
PLACEHOLDER_TOKENS = ("待定义", "待完善", "placeholder", "TODO", "{{", "}}", "<待", "未命名")

class PlaceholderDetector:
    def detect(self, text: str) -> list[str]:
        """返回 text 中出现的所有占位符 token 列表。空列表 = 无占位符。"""
```

### IntelligentReviewer

```python
class IntelligentReviewer:
    """统一的程序/美术评审器。"""

    def review_program(self, requirements: list[dict]) -> dict:
        """
        检查项:
        - 空列表 → BLOCKER
        - 无 source_refs → CRITICAL
        - 无 system_ids → WARNING
        - 含占位符 token → CRITICAL
        - 缺 inputs/outputs/dependencies 字段 → INFO
        - 无 acceptance → CRITICAL

        输出: {
            "verdict": "PASS|WARN|FAIL|BLOCKED",
            "issues": [...],
            "severity_counts": {"BLOCKER":0, "CRITICAL":0, "WARNING":0, "INFO":0},
            "blocker_count": int,
            "critical_count": int,
            "requires_action_count": int,   # blocker + critical
            "blocking_issue_count": int,    # 仅 blocker
            "warning_count": int
        }
        """

    def review_art(self, assets: list[dict]) -> dict:
        """
        检查项:
        - 空列表 → BLOCKER
        - 无 source → CRITICAL
        - 缺 asset_type/purpose/priority → WARNING
        - purpose 含占位符 → CRITICAL
        """
```

**verdict 判定规则**:

| 条件 | verdict |
|------|---------|
| blocker_count > 0 | BLOCKED |
| critical_count > 0 | FAIL |
| warning_count > 0 | WARN |
| 其他 | PASS |
