# AI 开发记忆系统 — 设计与开发计划

---

## 一、问题陈述

每次开启新的 AI 对话，AI 都要从零重新阅读整个项目。这带来三个实际问题：

1. **时间浪费** — 重新阅读几十个文件，大量 token 花在"理解项目结构"上
2. **风格漂移** — 不同会话里 AI 对代码风格的理解可能不一致，导致新代码与已有代码不统一
3. **决策遗失** — 上一次会话做出的架构决策、踩过的坑，下一次会话不知道

目标：建立一套**项目级持久化记忆系统**，让每次新会话能直接拿到上一次会话积累的知识，而不是从零开始。

---

## 二、核心思路

```
┌──────────────────────────────────────────────────────────────────┐
│                        记忆系统分层                               │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│  L1 项目理解  │  L2 代码惯例  │  L3 会话历史  │  L4 决策记录       │
│  (稳定，少变) │  (开发中积累) │  (每次更新)   │  (关键节点记录)    │
├──────────────┴──────────────┴──────────────┴────────────────────┤
│               CLAUDE.md 自动加载入口（顶部引用）                   │
└──────────────────────────────────────────────────────────────────┘
```

**关键机制**：Claude Code 每次进入项目时必读 `CLAUDE.md`。在 `CLAUDE.md` 顶部添加一个"AI记忆索引"章节，指向记忆文件目录。新会话加载 `CLAUDE.md` 时顺带得到上次的积累。

**缓存有效性**：每个记忆文件头部记录"源文件最后修改时间摘要"。如果对应源文件没变，记忆直接可信；如果源文件改了，记忆标记为"部分失效"，AI 重新阅读那些文件并更新记忆。

---

## 三、记忆文件结构

```
knowledge/ai_memory/                    ← 记忆系统根目录（在 knowledge/ 下，跟随 git）
├── INDEX.md                            ← 记忆总索引，CLAUDE.md 顶部引用此文件
│
├── project_understanding/              ← L1：项目理解缓存
│   ├── architecture.md                 ← 整体架构、8层职责、数据流
│   ├── key_files.md                    ← 关键文件作用一览（含行数和上次读取哈希）
│   └── freshness.json                  ← 源文件哈希快照，用于判断缓存是否过期
│
├── code_conventions/                   ← L2：代码惯例
│   ├── patterns.md                     ← 观察到的代码模式（类结构、错误处理、命名）
│   ├── anti_patterns.md                ← 禁止做的事（从 CLAUDE.md 禁止事项 + 实际踩坑）
│   └── style_guide.md                  ← 本项目实际使用的代码风格（缩进、注释规则等）
│
├── session_history/                    ← L3：会话历史
│   ├── index.json                      ← 会话列表 [{id, date, summary, changed_files}]
│   └── YYYY-MM-DD_NNN.md              ← 每次会话摘要（做了什么、为什么、留下了什么）
│
└── decisions/                          ← L4：决策记录
    ├── architecture.md                 ← 架构决策（为什么选这个方案而不是那个）
    ├── open_questions.md               ← 尚未解决的问题，下次会话需要继续的
    └── lessons_learned.md              ← 踩过的坑，后续不要重蹈
```

---

## 四、各层详细设计

### L1 — 项目理解缓存（project_understanding/）

**architecture.md** — 由 AI 第一次完整阅读项目后生成，内容包括：
- 各层目录的实际职责（比 CLAUDE.md 更精准，因为是读代码后得出的）
- 核心执行链：哪个函数调用哪个函数，主路径是什么
- 最重要的接口：StagePlugin、ModelAdapter、StageContext 的实际用法

**key_files.md** — 格式如下：
```markdown
## core/engines/generation.py
- 行数：3795
- 职责：所有16个阶段的业务输出逻辑，_stage0_outputs() ~ _stage15_outputs()
- 关键函数：apply_development_plan_outputs(), _parse_design_text()
- 上次读取：2026-06-19  源文件哈希：abc123
- 缓存状态：✓ 有效
```

**freshness.json** — 机器可读的哈希快照：
```json
{
  "generated_at": "2026-06-19T10:30:00",
  "files": {
    "core/engines/generation.py": {"sha256": "abc123", "size": 39128},
    "core/registry.py": {"sha256": "def456", "size": 2100}
  }
}
```

每次新会话启动时，AI 对比当前文件哈希与快照，判断哪些缓存还有效。

---

### L2 — 代码惯例（code_conventions/）

**patterns.md** — 从实际代码中提炼，例如：
```markdown
## StagePlugin 实现模式
每个步骤插件都是：
  stage_id = "NN"
  _source_groups = [SourceGroup(...)]
  def execute(ctx): test_mode → run_import_step → apply_development_plan_outputs

## 错误处理模式
不使用 try/except 包裹业务逻辑，而是在 StageResult 中返回 status="failed"
引擎层（generation.py）的函数全部返回 dict，由 execute() 转换为 StageResult

## 路径模式
所有路径常量在 core/paths.py 中定义，绝不在其他文件硬编码
```

**style_guide.md** — 实际观察到的风格规则：
```markdown
- 文件开头必须有 from __future__ import annotations
- 类属性用类型注解，不用 docstring 解释参数
- 函数不超过 50 行，否则拆分
- 中文注释用于业务说明，英文用于技术说明
- JSON 文件写入统一用 write_json()，读取用 read_json()
```

---

### L3 — 会话历史（session_history/）

每次会话结束时，由 AI 写入一条记录。格式：

```markdown
# 会话 2026-06-19-001

## 做了什么
- 完整阅读了项目，建立了 L1 项目理解缓存
- 分析了 GUI 卡顿原因：render() 全量重建 + cross_layer_rules.lint() 每次全量计算
- 制定了开发流水线 UI 计划（pipeline_ui_plan.md）
- 制定了 AI 记忆系统计划（ai_memory_system_plan.md）

## 关键发现
- core/engines/generation.py 是全项目最重的文件（3795行），16个阶段逻辑全在里面
- 默认 API 配置指向代理 vip.auto-code.net，模型是 gpt-5.5
- ucos/ 目录的大部分文件已经被删除（git status 中显示为 D）
- 步骤03+ 依赖 Unity 配置，没有配置时会产出 blocked 状态

## 修改的文件
（本次无代码修改，只做了规划）

## 下次会话应该继续
- 实现 pipeline_ui_plan.md 中的7个步骤
- 实现 ai_memory_system_plan.md 中的记忆系统
```

**index.json**：
```json
[
  {
    "id": "2026-06-19-001",
    "date": "2026-06-19",
    "summary": "项目初次完整阅读，制定两份开发计划",
    "changed_files": [],
    "next_tasks": ["pipeline UI 实现", "记忆系统实现"]
  }
]
```

---

### L4 — 决策记录（decisions/）

**architecture.md** — 每当做出重要架构选择时追加：
```markdown
## 2026-06-19：GUI 重构方式
决策：CommercialDesignApp 改为 tk.Frame，不弹子窗口，用标签切换
原因：用户明确要求"打开时全屏"，标签切换比子窗口更符合 VSCode 风格
否决方案：独立 Toplevel 子窗口（会失去焦点，用户体验差）
```

**open_questions.md** — 尚未解答的问题，下次会话优先处理：
```markdown
- [ ] AI 对话面板的 CodexCliBackend 在流水线模式下的系统 prompt 内容还未定义
- [ ] 记忆系统的"会话结束"时机如何触发（手动 vs 自动检测）
```

**lessons_learned.md** — 踩坑记录：
```markdown
## render() 全量重建导致卡顿
不要在每次状态变更后调用 self.render()，应该只更新受影响的 widget
```

---

## 五、CLAUDE.md 集成方式

在 `CLAUDE.md` 文件顶部（现有内容之前）插入一个新章节：

```markdown
## AI 会话记忆

> 本项目有持久化记忆系统。进入项目前请先读取记忆索引：
> **`knowledge/ai_memory/INDEX.md`**
>
> 索引文件描述了上次会话的状态、哪些文件已被理解、代码惯例摘要。
> 有效的缓存文件可以跳过重新阅读，直接使用记忆中的理解。
>
> 每次会话结束时，请更新 `knowledge/ai_memory/session_history/` 中的记录。
```

`INDEX.md` 本身要足够精简（100行以内），只列出：
- 上次会话日期和摘要（一句话）
- 缓存有效性状态（哪些 L1 文件还有效）
- L2 代码惯例最重要的3-5条（直接内联，不需要跳转）
- 下次会话的优先任务（来自 open_questions.md）

---

## 六、记忆更新工作流

### 自动触发（推荐）

AI 每次对话时遵守以下约定：

**会话开始时：**
1. 读取 `CLAUDE.md` → 看到记忆章节 → 读取 `INDEX.md`
2. 对比 `freshness.json` 与当前文件哈希
3. 有效的 L1 缓存 → 直接使用，不重新读文件
4. 失效的 L1 缓存 → 只重读那些改过的文件，更新对应缓存

**会话结束时（用户说"完成"/"结束"/"提交"时）：**
1. 写入 `session_history/YYYY-MM-DD_NNN.md`
2. 更新 `session_history/index.json`
3. 更新 `decisions/open_questions.md`（去掉已解决的，加入新发现的）
4. 如有代码修改 → 更新 `freshness.json` 中对应文件的哈希
5. 更新 `INDEX.md` 中的"上次会话"摘要

### 辅助工具脚本

新增 `tools/memory/update_freshness.py`：

```python
# 扫描项目所有 Python 文件，更新 freshness.json
# 用法：python tools/memory/update_freshness.py
# 作用：当有大量文件变动时，批量更新哈希快照
```

新增 `tools/memory/check_staleness.py`：

```python
# 对比 freshness.json 与当前文件，输出哪些记忆已过期
# 用法：python tools/memory/check_staleness.py
# 输出：{"stale": ["core/engines/generation.py"], "fresh": [...]}
```

---

## 七、文件命名规则

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 会话记录 | YYYY-MM-DD_NNN.md（NNN 为当日序号） | 2026-06-19_001.md |
| 架构图 | 固定名，直接覆盖更新 | architecture.md |
| 决策记录 | 固定名，追加内容 | architecture.md |
| 哈希快照 | 固定名，全量覆盖 | freshness.json |

---

## 八、与现有系统的关系

| 系统 | 位置 | 作用 | 本系统的关系 |
|------|------|------|--------------|
| CLAUDE.md | 项目根目录 | AI 必读的项目导读 | 顶部新增引用入口 |
| `ucos/knowledge/episodic/` | 项目内 | 游戏设计会话的片段记忆 | 独立，互不干扰 |
| Claude Code 自动记忆 | `~/.claude/projects/…/memory/` | 用户偏好、反馈记录 | 独立，本系统补充项目知识 |
| `knowledge/` | 项目内 | 设计数据、规则、schema | 本系统存放在其子目录 `knowledge/ai_memory/` |

---

## 九、实现步骤

1. **创建目录结构** — `knowledge/ai_memory/` 下建立所有子目录和占位文件
2. **更新 CLAUDE.md** — 顶部插入"AI 会话记忆"章节，引用 INDEX.md
3. **写入 L1 缓存** — 基于本次已阅读的内容，填充 architecture.md 和 key_files.md
4. **写入 L2 惯例** — 将本次观察到的代码模式写入 patterns.md 和 style_guide.md
5. **写入首条会话记录** — session_history/2026-06-19_001.md
6. **更新 freshness.json** — 记录当前所有已读文件的哈希
7. **添加工具脚本** — tools/memory/update_freshness.py 和 check_staleness.py
8. **初始化 INDEX.md** — 精简索引，供下次会话直接加载

---

## 十、验证方式

**新开一个 Claude Code 对话，不告诉它任何背景，验证：**

1. AI 读 CLAUDE.md 后主动提到"发现记忆系统，正在加载 INDEX.md"
2. AI 能说出上次会话做了什么（来自 session_history）
3. AI 能说出核心代码模式（来自 code_conventions）
4. 修改一个文件后，AI 能识别对应缓存已过期，重新读取那个文件
5. 两次会话写出的新代码风格一致（from __future__、路径用法、错误处理模式相同）
