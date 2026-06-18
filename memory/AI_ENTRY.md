# DevFlow — AI 会话入口

> ★ 这是唯一编辑源。修改本文件后运行 `python sync_entry.py`，
> CLAUDE.md / AGENTS.md / README.md 将自动同步。

---

## 项目速览

**DevFlow** 是一个面向独立游戏开发者的「程序自动开发流程工具」，把游戏开发拆分为 16 个确定性阶段（Stage 0–15），通过 AI 辅助完成设计、美术、代码和构建的全链路工作。当前目标引擎为 Unity，AI 模型为 GPT-5.5，运行平台为 Windows。

核心入口：双击 `DevFlow.exe` 启动 GUI 工作台；命令行用 `orchestrator.py`（严禁绕过它直接操作产物目录）。

---

## 启动前必读（按优先级）

1. `HANDOFF.md` — 全景交接文档（架构、模块状态、当前存档进度、禁止事项）
2. `memory/active-task.md` — 当前任务状态 + 阻断项 + 下一步行动
3. `memory/decisions.md` — 已批准架构决策（不可逆）
4. `memory/known-issues.md` — 已知问题追踪
5. `CONTEXT.md` — 项目术语权威定义（深入调试时读）

---

## 记忆文件夹说明

```
memory/
├── AI_ENTRY.md        ← ★ 唯一编辑源（本文件）
├── active-task.md     ← 当前任务/存档/阻断（高频覆写）
├── decisions.md       ← 架构决策日志（只增不改）
└── known-issues.md    ← 问题追踪（追加 + 标记状态）
```

每次工作结束前更新 `active-task.md`，下次会话直接定位状态。
架构决策记入 `decisions.md`，不要修改已有条目，只追加。

---

## UCOS 认知层入口

`ucos/` 已按 `UCOS开发计划.md` 落地为结构化认知层：

- 初始化：`python ucos/scripts/ucos_init.py --domain devflow`
- 校验：`python ucos/scripts/ucos_validate.py`
- 迁移预览：`python ucos/scripts/ucos_migrate.py --source memory --dry-run`
- 会话启动摘要：`python ucos/scripts/ucos_sync.py --event session_start --print-summary`
- 会话结束 Hook：`python ucos/scripts/ucos_sync.py --event session_end`

`sync_entry.py` 已变为兼容空壳，实际同步逻辑在 `ucos/scripts/ucos_sync.py`。
`.claude/settings.json` 已指向 UCOS 的 PostToolUse / Stop Hook。

---

## Skills 库

`.claude/skills/` — 标准操作 Skill（检查阶段状态、运行流水线、调试验收错误等）

---

## 禁止事项（速查）

- ❌ 不要恢复 `*_crew.py` 作为运行入口
- ❌ 不要从 `Shared/` 读取当前项目资料
- ❌ 不要把旧 Agent Runtime（LangChain/CrewAI）加回代码
- ❌ 不要绕过 `orchestrator.py` 直接手写 `outputs/` 目录
- ❌ 不要删除 `artifact_layer/registry.json`
- ❌ 不要删除 `knowledge/` 中被 registry 引用的文件
- ❌ 不要在阶段 10/11 执行期间新增需求或重新制定计划
- ❌ 不要修改 `config.toml` 中的 model 或 base_url（除非用户明确要求）
- ❌ 不要手动编辑 CLAUDE.md / AGENTS.md / README.md（由 sync_entry.py 生成）

---

## 关键路径速查

| 用途 | 路径 |
|------|------|
| 正式流水线入口 | `工程运行文件\orchestrator.py` |
| GUI 源码 | `工程运行文件\gui_app.py` |
| 存档索引 | `工程运行文件\save\save_index.json` |
| 产物依赖注册表 | `工程运行文件\artifact_layer\registry.json` |
| 模型配置 | `工程运行文件\config.toml` |
| 16 阶段实现 | `工程运行文件\steps\` |
