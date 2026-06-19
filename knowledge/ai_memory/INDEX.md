# AI 会话记忆索引

> 最后更新：2026-06-19（第二次更新）  
> 缓存状态：✓ 有效

---

## 上次会话摘要

**日期**：2026-06-19  
**ID**：2026-06-19-003  
**摘要**：实现流水线 UI 全部7个模块（VSCode 风格开发流水线界面）

**完成内容**：
- ✅ `core/ui/unity_config_dialog.py` — Unity 路径配置对话框
- ✅ `core/ui/pipeline_step_card.py` — 步骤状态卡片组件
- ✅ `core/ui/pipeline_panel.py` — 流水线主面板（左侧步骤树 + 右侧详情）
- ✅ `core/ui/bottom_panel.py` — 底部日志 + AI 对话面板
- ✅ 修改 `core/ui/app_window.py` — CommercialDesignApp 改为 tk.Frame
- ✅ `core/ui/main_window.py` — 主框架窗口（顶部标签 + PanedWindow 骨架）
- ✅ 修改 `core/ui/gui_app.py` — 入口切换到 MainWindow

**关键发现（纠正计划中的错误引用）**：
- `workbench.py` 是遗留 DevFlow 文件，引用了已删除的 `tools/actual_development_preflight.py`，不可用
- 实际预检：`core.runtime.preflight.run_actual_development_preflight`
- 实际停止：`core.runtime.control.request_stop`
- 实际执行：`core.main.run_range(from_step, stop_step, auto_approve, skip_preflight)`
- 步骤状态：`core.runtime.pipeline_state.load_pipeline_state`
- 步骤元数据：`core.registry.STEP_SPECS`
- 制品目录：`core.paths.ARTIFACTS_DIR / f"stage_{num:02d}"`

**下次优先任务**：
- [ ] 启动 `python core/ui/gui_app.py` 验证 UI（见 plan/pipeline_ui_plan.md 验证方式）
- [ ] 如有运行时错误，按错误修复

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
