# 架构决策日志

> 只增不改。新决策追加在末尾，不修改已有条目。
> 格式沿用项目 knowledge/decisions/ 三段式风格。

---

## Decision 001 — 使用确定性流水线替代 Agent Runtime

Date: 2026-06-09

Decision: 整个工具围绕 0→15 单向确定性流水线运转，不使用 CrewAI、LangChain 等 Agent Runtime。

Reason: Agent Runtime 不确定性太高，无法满足每阶段产物的严格 JSON 验收规则。

---

## Decision 002 — orchestrator.py 作为唯一正式流水线入口

Date: 2026-06-09

Decision: 所有阶段通过 orchestrator.py 驱动，`pipeline.py` 和 `run_pipeline.py` 仅作兼容 shim 保留，不扩展。

Reason: 统一入口保证治理层（artifact_layer）完整执行，绕过入口会导致产物无法通过 preflight 验证。

---

## Decision 003 — 存档系统替代 git

Date: 2026-06-09

Decision: 项目使用内部存档系统（save/ 目录，save_manager.py）替代 git 进行版本控制。

Reason: 流水线产物、源资料、配置的快照需求与 git 的 diff 模型不匹配；存档系统支持时间线和完整工作区恢复。

---

## Decision 004 — source_artifacts/ 替代 Shared/ 作为人工输入源

Date: 2026-06-09

Decision: 操作者提交的源资料必须放入 source_artifacts/，并包含 package_manifest.json（含正确 source_id），Shared/ 目录严禁作为当前资料来源。

Reason: 旧 Shared/ 架构与当前 source_id 匹配机制不兼容；source_artifacts/ 有明确的封装和验证规范。

---

## Decision 005 — 美术资产双层验收

Date: 2026-06-09

Decision: 美术资产必须先写入美术暂存区，经规格检查（路径/格式/尺寸/命名）+ 审美评审两层验收后才能集成到 Unity Assets，API 原图永久保留不直接作为运行时资产。

Reason: 单层验收无法覆盖风格漂移、比例、材质等视觉质量问题，需要两层分离处理。

---

## Decision 006 — memory/ 使用单一编辑源同步三个 AI 入口文件

Date: 2026-06-17

Decision: CLAUDE.md / AGENTS.md / README.md 由 sync_entry.py 从 memory/AI_ENTRY.md 自动生成，用户只编辑 AI_ENTRY.md。

Reason: 三文件互相同步会造成循环触发和冲突，单一编辑源原则避免内容分歧。

---

## Decision 007 — 引入 UCOS 作为 DevFlow 的结构化认知层

Date: 2026-06-17

Decision: 在项目根目录新增 `ucos/`，作为 Identity、Knowledge、Capability、Execution、Output、Runtime Adapter 六层认知系统；旧 `memory/` 继续保留为过渡期人读入口，结构化数据迁移到 `ucos/knowledge/`。

Reason: 旧 `memory/` 只适合会话交接，不具备 schema 校验、分层检索、技能注册、反思、上下文预算和 Hook 生命周期管理。UCOS 提供可验证、可迁移、可自动同步的底层结构，同时不改变 DevFlow 正式流水线入口 `工程运行文件/orchestrator.py`。
