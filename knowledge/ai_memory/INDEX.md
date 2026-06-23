# AI 会话记忆索引

> 最后更新：2026-06-23
> 缓存状态：✓ 有效

---

## 上次会话摘要

**日期**：2026-06-23
**ID**：2026-06-23-009
**摘要**：溯源 `范本：Hades` 自动化开发 Step05 阻断：源包仍是 `未命名游戏设计项目` 空白状态

**完成内容**：
- ✅ 确认 Step05 `BLOCKED` 来自占位符质量门禁，不是评审代码异常
- ✅ 追溯到 `source_artifacts/devflow_Concept_v2` / `devflow_Design_v2`，确认导出源包不是 Hades
- ✅ 对比失败 draft 时间和 `范本：Hades` 存档创建时间，确认流水线早于 Hades 存档创建
- ✅ 记录排错经验：Step05 placeholder 阻断应向上检查导出源包和 Stage00/02/03 产物

**自查修复**：
- ✅ 已检查失败 draft 的 `source_artifacts`、`stage_00`、`stage_02`、`stage_03`、`stage_05` 产物
- ✅ 本轮仅做溯源和记忆记录，没有修改运行时代码

**验证**：
- ✅ `stage_05/intelligent_review_report.json`：`verdict=BLOCKED`，阻断项为 `placeholder_rate`
- ✅ `stage_03/program_requirements_contract.json`：4 条需求全部包含 `未命名游戏设计项目`
- ✅ `source_artifacts/.../concept.md` / `design.md`：标题仍为 `未命名游戏设计项目`

**后续关注**：
- [ ] 重新运行自动化开发前，先确认导出的 `concept.md/design.md` 包含 Hades 内容
- [ ] 增加导出前置校验，提前拦截 `未命名游戏设计项目` 和过低实体覆盖率源包

---

## 历史会话摘要

**日期**：2026-06-23
**ID**：2026-06-23-008
**摘要**：修复 `bug收集文档4.md` 第四轮 3 个问题：Step00 新品类 inference、Step04 roguelike_action 键名兼容、CQ-013/014 证据入口

**完成内容**：
- ✅ BUG-015：Step00 `_genre_key` 补充 `strategy/rpg/moba`，并为三类补齐 CQ-005~CQ-012 genre evidence
- ✅ BUG-016：Step04 支持 `roguelike_action` 市场库键名，同时保留 `roguelike.json` 别名兼容
- ✅ BUG-017：CQ-013/CQ-014 增加实际 L4 字段和关键词入口
- ✅ 补充 strategy/rpg/moba、CQ-013/014、roguelike_action 市场库回归测试

**验证**：
- ✅ `python -m pytest core\tests -q`：47 passed（仅 `.pytest_cache` 写入权限 warning）
- ✅ 本次改动范围 `black --check` / `flake8` / `mypy --explicit-package-bases`：通过
- ✅ Step 00-06 端到端通过

---

**日期**：2026-06-23
**ID**：2026-06-23-007
**摘要**：修复 `bug收集文档3.md` 第三轮 5 个问题：阶段误判、模板缓存污染、市场库读取、资产阶段和 warning verdict

**完成内容**：
- ✅ BUG-010：Step02 移除宽泛 `"build"`，避免 `build_system_decision` 被误分到 `launch_ops`
- ✅ BUG-011：Step01 模板缓存按文件签名刷新，并在 pytest fixture 中清理缓存
- ✅ BUG-012：Step04 roguelike/fps/puzzle 都优先读取本地 market_data 库
- ✅ BUG-013：Step04 资产阶段分类补齐 `progression/social/launch_ops`
- ✅ BUG-014：Step05 有 warning 时 `_verdict` 返回 `WARN`

**验证**：
- ✅ `python -m pytest core\tests -q`：44 passed
- ✅ Step 00-06 端到端通过

---

**日期**：2026-06-23
**ID**：2026-06-23-006
**摘要**：执行 `plan/v5_engineering_plan`：Step00-05 能力增强、Phase0 基础设施、多品类模板验证和质量门禁

**完成内容**：
- ✅ Step00 Hades 稀疏 Concept 通过 `genre_inference` 透明补证据，coverage 提升到 0.8667
- ✅ Step01 增加 strategy/rpg/moba 模板、模板缓存、显式 loop 分隔符增强和 system_layer 前缀清洗
- ✅ Step02 L5 连续编号、kind 推断和 launch_ops 分类增强；保留无可信分母 coverage=0 的 BUG-007 修复
- ✅ Step03 多需求生成、扩展 schema routes、中文/英文语义绑定和需求密度统计
- ✅ Step04 多资产生成、P0 resolution、roguelike 本地 market_data 参考库
- ✅ Step05 verdict、placeholder BLOCKER、内容深度聚合告警、资产类型覆盖和 L1 配置绑定豁免

**验证**：
- ✅ `python -m pytest core\tests -q`：39 passed
- ✅ Step 00-06 端到端通过

---

**日期**：2026-06-23
**ID**：2026-06-23-005
**摘要**：修复 `bug优化文档.md` 第二轮 3 个问题：覆盖率最终回退、模板重复读取、requires_action_count 漏计 BLOCKER

**完成内容**：
- ✅ BUG-007：Step02 `_expected_node_count` 最终 fallback 不再返回 covered node count，避免无可信分母时假报 1.0
- ✅ BUG-008：Step01 `LoopExtractor` / `SystemDeducer` 每次只读取一次 `genre_templates.json`
- ✅ BUG-009：Step05 `requires_action_count` 现在统计 BLOCKER + CRITICAL
- ✅ 新增无 expected total 的真实 L5 entity 场景测试，以及 BLOCKER action count 测试

**验证**：
- ✅ `python -m pytest core\tests -q`：34 passed
- ✅ D4 → Step 00-06 端到端通过

---

**日期**：2026-06-23
**ID**：2026-06-23-004
**摘要**：修复 `bug收集文档.md` 中列出的 6 个 pipeline optimization 回归问题，并补充测试

**完成内容**：
- ✅ BUG-001：修复 `export_adapter.py` 中 `coreLoops` 默认值缺失导致的 `None.get()` 崩溃
- ✅ BUG-002：Step02 entity coverage 改用真实分母，优先 `design_summary.node_count`，不再无条件 1.0
- ✅ BUG-003：Step01 `SystemDeducer` 系统数量明确截断到最多 8 个
- ✅ BUG-004：Step03 模糊匹配阈值从 0.18 提升到 0.4，并取消无依据 `phase:*` 伪绑定
- ✅ BUG-005：Step02 环路报告不再重复闭合节点
- ✅ BUG-006：Step05/06 评审报告分离 BLOCKER 与 CRITICAL，`blocking_issue_count` 只统计 BLOCKER

**验证**：
- ✅ `python -m pytest core\tests -q`：32 passed
- ✅ D4 → Step 00-06 端到端通过

---

**日期**：2026-06-23
**ID**：2026-06-23-003
**摘要**：完成 pipeline_optimization 收尾：跨进程 D4 源包发现、无 L5 实体本地补全、资产字段完整性与最终端到端自检

**完成内容**：
- ✅ `core/source/finder.py` 新增 source root 回退：当前 draft → 最新历史 draft → legacy `sandbox/source_artifacts/`
- ✅ `core/engines/generation.py` 与导入器使用一致的源包发现顺序，修复 D4 与 Step 00-06 分进程执行失败
- ✅ Step 02 在无显式 `L5实体` 时合成最多 47 个可追踪本地实体
- ✅ Step 04 selection/entity 资产补齐 `priority` 与 `complexity`
- ✅ 新增跨 draft source fallback、无 L5 实体合成、asset complexity 测试

**验证**：
- ✅ `python -m pytest core\tests -q`：26 passed
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ D4 → Step 00-06 端到端通过

---

**日期**：2026-06-23
**ID**：2026-06-23-002
**摘要**：继续完成开发计划收尾：质量工具修复、根目录设计蓝图归档、最终自检

**完成内容**：
- ✅ `tools/validators/pipeline_quality.py` 支持 `--artifacts-dir`，并在新进程 draft 为空时回退到最近有 stage 00-06 质量产物的 draft
- ✅ 新增测试覆盖质量指标工具的显式 artifacts 根目录采集
- ✅ 清理 `core/design/export_adapter.py` 中不可达旧代码和未使用导出常量
- ✅ 清理 `core/engines/generation.py` 中已被 `LoopExtractor` 替代的 `_core_loop_steps()`
- ✅ 根目录 `design_plan/` 旧蓝图文件已归档到 `plan/pipeline_optimization/design_plan_archive/`
- ✅ 更新 `plan/pipeline_optimization/README.md` 和 `plan/status_snapshot_2026-06-23.md` 记录实际状态

**验证**：
- ✅ `python -m pytest core\tests -q`：24 passed
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ Hades 00-06 代码级回归达到目标指标

---

**日期**：2026-06-23
**ID**：2026-06-23-001
**摘要**：完成 D4 designEntities 导出与步骤00-06质量优化基础设施

**完成内容**：
- ✅ D4 `devflow_Design_v2/attachments/design.md` 将 `designEntities` 序列化为可解析的 `L5实体` 条目
- ✅ Step 00-06 新增实体驱动输出、质量报告、资产转换、分级评审
- ✅ 新增 `tools/validators/pipeline_quality.py` 初版质量指标采集工具
- ✅ 新增存档系统二期 ADR：draft 为唯一运行写入点，正式存档为显式归档结果

**验证**：
- ✅ `python -m pytest core\tests -q`：23 passed
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ Hades 00-06 同进程代码级回归达到目标指标

---

**日期**：2026-06-21
**ID**：2026-06-21-003
**摘要**：按 ADR 0001/0002 完成 per-session drafts 路径与正式存档去快照化

**完成内容**：
- ✅ `core/paths.py` 新增 `drafts/{timestamp}_{pid}/` 会话草稿根，`SANDBOX_DIR` 仅作为兼容别名指向当前 draft
- ✅ `core/save/manager.py` 改为从 draft 同步 active 文件，正式存档 `saves/{save_id}/` 只保留 `manifest.json` 和 `workspace/`
- ✅ 快照、事务 file map、timeline 只写入当前 draft，不再进入正式存档
- ✅ 兼容读取旧 `save_manifest.json`，同步时迁移为 `manifest.json`

**后续关注**：
- [ ] 执行对象存储仍通过正式存档 workspace 读写；本轮已形成 ADR 草案，待评审后实施

---

**日期**：2026-06-21
**ID**：2026-06-21-001  
**摘要**：存档管理完善 + 流水线 AI 适配器可选 + Skill 库集成 + 项目配置 UI 重设计

**完成内容**：
- ✅ 存档管理：新建存档自动保存设计、默认项目名、重命名功能、删除打开按钮
- ✅ AI 适配器可选：Claude Code CLI / Codex CLI / OpenAI，项目配置界面下拉切换
- ✅ Skill 库：从官方拉取 frontend-design + imagegen，注入流水线步骤 04/08/09/11
- ✅ 项目配置 UI 卡片化重设计

**下次优先任务**：
- [ ] 验证 AI 适配器切换（codex vs claude）
- [ ] 验证 skill_guidance.md 写入步骤输出目录

**完成内容**：
- ✅ `ucos/` → `knowledge/ucos/`，`core/paths.py` 加 sys.path 免改导入
- ✅ 新建 `core/design/ai_ucos_bridge.py`：AI 访谈每轮写入 ucos（对话/决策/路由/设计生成）
- ✅ `artifact_layer/` → `pipeline/artifact_layer/`
- ✅ 清理：删除 `_archive/`、根目录 `ai_runtime/`、`.claude/` 残留、`plan/`

**关键发现**：
- ucos 之前完全孤立无入口调用，现已通过 `ai_ucos_bridge` 联通
- `ai_runtime/` 根目录是旧版遗留，实际写入路径为 `sandbox/workspace/ai_runtime/`

**下次优先任务**：
- [ ] 验证 AI 访谈 → ucos 写入是否正常
- [ ] 考虑将 ucos context_builder 读取结果注入 AI 访谈 prompt（闭环）

**完成内容**：
- ✅ 修复执行对象保存全链路（6个 Bug，包括 force_cancel 解决残留冲突）
- ✅ 新增 `core/ui/save_manager_dialog.py`：独立存档管理对话框
- ✅ 存档过滤：只显示含 design_project 的存档槽，屏蔽流水线存档
- ✅ `core/ui/unity_config_dialog.py` 重构为 `ProjectConfigDialog`（多引擎）
- ✅ `core/runtime/preflight.py` 按引擎分支检查
- ✅ 清理垃圾存档，工作区置空

**关键发现**：
- 历史实现中 `runtime_root` = `sandbox/workspace`，存档在 `sandbox/workspace/saves/`，与流水线共享；2026-06-21-003 后运行根已改为 `drafts/{session_id}/`
- `save_20260609_*` 等是流水线存档，不含 design_project 数据，需过滤

**Git commit**：`77be8bd`

**下次优先任务**：
- [ ] 验证保存/加载流程端到端正常
- [ ] 验证引擎切换后 preflight 检查变化符合预期

---

## L1 项目理解缓存状态

| 文件 | 缓存状态 | 上次读取 |
|------|----------|----------|
| architecture.md | ✓ 有效 | 2026-06-19 |
| key_files.md | ✓ 有效 | 2026-06-19 |
| freshness.json | ✓ 有效 | 2026-06-19 |

**架构精要**（详见 project_understanding/architecture.md）：
- 8 层职责分工：步骤插件层 / 运行骨架层 / 知识层 / 配置层 / 工具层 / 认知层 / 注册表层 / 沙盒层
- 核心执行链：main.py::run_range() → plugin.execute() → run_import_step() → apply_development_plan_outputs() → artifact review/validation → save/manager.py::retry_sync()
- 三大引擎：generation.py（16阶段业务逻辑）、DesignEngine（游戏设计决策）、CodexCliBackend（AI后端）

---

## L2 代码惯例速查

**必须遵守的5条规则**（详见 code_conventions/patterns.md）：

1. **路径管理**：所有路径常量在 `core/paths.py` 定义，禁止其他文件硬编码路径字符串
2. **StagePlugin 模式**：stage_id + _source_groups + execute(ctx) → run_import_step() → apply_development_plan_outputs()
3. **错误处理**：返回 StageResult(status="failed")，不用 try/except 包业务逻辑
4. **文件头**：所有 .py 文件开头必须有 `from __future__ import annotations`
5. **主题统一**：GUI 组件颜色从 `core/ui/theme.py::COLORS` 取，字体从 `FONT_*` 取

**禁止事项**（详见 code_conventions/anti_patterns.md）：
- ❌ 在 core/ 以外写运行时核心逻辑
- ❌ 直接 import steps.* 或 design_tool.*（已删除）
- ❌ 在 tools/ 根目录放 .py 文件（必须放子目录）
- ❌ 创建超过 400 行的单一功能文件（必须拆分）

---

## L4 待办决策

**待解决问题**（详见 decisions/open_questions.md）：
- AI 对话面板在"流水线模式"下的系统 prompt 内容
- 记忆系统会话结束时机触发方式（手动 vs 自动检测）

**最新架构决策**（详见 decisions/architecture.md）：
- 2026-06-19：GUI 重构采用标签切换方式，CommercialDesignApp 改为 tk.Frame

---

## 如何使用本记忆系统

1. **会话开始时**：读取本文件 + project_understanding/key_files.md，检查缓存有效性
2. **缓存有效**：直接使用记忆中的理解，不重新读对应文件
3. **缓存失效**：对比 freshness.json，只重读改过的文件，更新对应记忆
4. **会话结束时**：写入新的 session_history/YYYY-MM-DD_NNN.md，更新本索引
