# AI 会话记忆索引

> 最后更新：2026-06-27
> 缓存状态：✓ 有效

---

## 上次会话摘要

**Date**: 2026-06-27
**ID**: 2026-06-27-003
**Summary**: Executed `ai_config_ui_redesign`: upgraded AI config to v3 `dev` / `image` / `completion` API categories and redesigned the unified AI config dialog into three tabs.

**Completed**:
- [x] Added v3 schema primitives in `core/config/ai_config_schema.py` and kept `core/config/ai_config.py` as the load/save/migration facade.
- [x] Migrated v2 Profile data into `dev`, `image`, and `completion` categories while preserving `get_active_profile()` compatibility.
- [x] Updated loader, validator, Step02 supplement selection, image-generation enablement, image API helper, migration tool, and config example for v3.
- [x] Rewrote `AIConfigUnifiedDialog` into `开发API` / `生图API` / `补全API` tabs with active-entry highlight, CLI read-only panels, API fields, custom JSON, and Codex path fields.
- [x] Updated README, AI config guide, AI_README, and AI config tests.

**Verification**:
- [x] Targeted AI config tests: 28 passed.
- [x] `python -B -m pytest -q`: 143 passed.
- [x] `PYTHONPYCACHEPREFIX=.cache\pycache python -B -m compileall core pipeline tools\validators\pipeline_quality.py tools\asset_production tools\config`: passed.
- [x] Targeted `py_compile`: passed.
- [x] `git diff --check`: passed with only the existing CRLF working-copy warning.

**Follow-up**:
- [ ] Manually click-test the redesigned AI config dialog: tabs, active highlight, local CLI read-only panel, Codex file fields, custom JSON validation, save/reopen.
- [ ] Keep `settings/ai_config.json`, old `settings/api_config.toml`, and `settings/ai_profiles.json` local and ignored.
- [ ] Continue excluding `plan/`, bug documents, and runtime drafts from commits.
- [ ] CC-Panes shared memory was skipped because all required environment variables were absent.

---

## 历史会话摘要

**Date**: 2026-06-27
**ID**: 2026-06-27-002
**Summary**: Executed `ui_improvement_v1`: moved AI visibility into the main-window bottom status bar, enhanced the unified AI config dialog, audited UI component usage, updated docs, and isolated tests from local ignored AI config.

**Completed**:
- [x] Added bottom status bar in `core/ui/main_window.py` for active AI Profile/adapter, DevFlow progress, and system state.
- [x] Wired status-bar AI click to unified AI config and progress click to the pipeline panel with first-incomplete-step selection.
- [x] Enhanced `core/ui/ai_config_unified_dialog.py` with active Profile highlight, detail validation status, async CLI checks, `应用`, save toast, and close cleanup.
- [x] Audited UI components: `bottom_panel.py` and `embedded_interview.py` are still referenced; `workbench.py` is retained as a deletion-audit candidate.
- [x] Updated `README.md`, `docs/AI_CONFIG_GUIDE.md`, and `AI_README.md` for the new status-bar entry.
- [x] Added test isolation in `core/tests/conftest.py` so local ignored `settings/ai_config.json` cannot pollute unit tests.

**Verification**:
- [x] `python -B -m py_compile core\ui\main_window.py core\ui\ai_config_unified_dialog.py core\tests\conftest.py`: passed.
- [x] Targeted local-config-polluted regression tests: 3 passed.
- [x] `python -B -m pytest -q`: 142 passed.
- [x] UI module import smoke test: passed.
- [x] `git diff --check`: passed with only the existing CRLF working-copy warning.

**Follow-up**:
- [ ] Manually spot-check the bottom status bar, AI config save/apply flow, and progress jump in the GUI.
- [ ] Keep `settings/ai_config.json`, old `settings/api_config.toml`, and `settings/ai_profiles.json` local and ignored.
- [ ] Continue excluding `plan/`, bug documents, and runtime drafts from commits.
- [ ] CC-Panes shared memory was skipped because all required environment variables were absent.

---

**Date**: 2026-06-27
**ID**: 2026-06-27-001
**Summary**: Executed `ai_config_optimization_v2`: unified AI config into `settings/ai_config.json`, bound Profile to Adapter/LLM/Image, added migration, validation, GUI, status indicator, tests, and docs.

**Completed**:
- [x] Added `core/config/ai_config.py`, `core/config/validator.py`, migration tooling, Profile-bound adapters, loader compatibility, unified AI config GUI, docs, and tests.
- [x] Updated Step02 supplement, Stage12 execution, and image generation to prefer active AI Profile.

**Verification**:
- [x] Targeted AI config/adapter tests: 27 passed.
- [x] Adapter/Step02/image/manual-gate related tests: 42 passed.
- [x] `python -B -m pytest -q`: 142 passed.
- [x] `PYTHONPYCACHEPREFIX=.cache\pycache python -B -m compileall ...`: passed.
- [x] `git diff --check`: passed with only the existing CRLF working-copy warning.

**Follow-up**:
- [ ] Manually spot-check the main-window AI status and unified AI config save/activate flow.
- [ ] Keep `settings/ai_config.json`, old `settings/api_config.toml`, and `settings/ai_profiles.json` local and ignored.
- [ ] Continue excluding `plan/`, bug documents, and runtime drafts from commits.
- [ ] CC-Panes shared memory was skipped because all required environment variables were absent.

---

**Date**: 2026-06-26
**ID**: 2026-06-26-006
**Summary**: Executed `ai_config_manager`: added named AI profiles, GUI configuration dialog, profile-first config loading, and profile-controlled image generation.

**Completed**:
- [x] Added `core/config/ai_profiles.py` for ignored `settings/ai_profiles.json`, active profile management, LLM/image config parsing, and secret masking.
- [x] Updated `core/config/loader.py` so active profiles override `llm` / `image` / `image2`, with fallback to old `api_config.toml` when profile config is absent or incomplete.
- [x] Added `core/ui/ai_config_dialog.py` and wired an `AI 配置` button into `core/ui/pipeline_panel.py`.
- [x] Changed image generation enablement to prefer the active profile image switch while preserving the legacy env-var fallback when no profile file exists.
- [x] Updated image tooling to use the configured image model instead of a hardcoded default.
- [x] Ignored `settings/ai_profiles.json` so local API keys are not committed.
- [x] Added regression tests for profile fallback, override, image2 mapping, image enablement, and default profile file creation.
- [x] Self-check fix: isolated the legacy `image2` fallback test from local `settings/ai_profiles.json` so future personal profiles cannot pollute test results.

**Verification**:
- [x] Targeted config/image tests: 15 passed.
- [x] `python -B -m py_compile ...`: passed.
- [x] `PYTHONPYCACHEPREFIX=.cache\pycache python -B -m compileall ...`: passed.
- [x] `python -B -m pytest -q`: 129 passed.
- [x] `git diff --check`: passed with only the existing CRLF working-copy warning.

**Follow-up**:
- [ ] Manually spot-check the GUI `AI 配置` dialog save/activate flow.
- [ ] Keep `settings/ai_profiles.json` local and ignored because it may contain API keys.
- [ ] This turn requested memory sync only; the code changes are not committed yet.
- [ ] Continue excluding `plan/`, bug documents, and runtime drafts from commits.
- [ ] CC-Panes shared memory was skipped because all required environment variables were absent.

---

**Date**: 2026-06-26
**ID**: 2026-06-26-005
**Summary**: Executed `template_2d_redesign/PLAN_FIXES.md`: fixed template replacement filenames, service count, Axiom Verge replacement, and concrete-node reference rules.

**Completed**:
- [x] Renamed 18 replacement template files so public `fileName` matches `template.id`.
- [x] Deleted `builtin_large_service_splatoon_3.json`; public `large_service` templates now total 5.
- [x] Replaced the duplicate 3A Hollow Knight slot with `builtin_3a_axiom_verge.json`, including metadata, notes, and entity ids.
- [x] Synced `template_index.json` with new file names, Axiom Verge metadata, and large-service ordering.
- [x] Updated `core/tests/unit/test_template_l5_expansion.py` to derive concrete nodes from `builtin_indie_hades_l5_complete.json`.
- [x] Added tests for removed old files, `fileName == id + .json`, and public scale counts: iaa=9 / indie=10 / midcore=3 / 3a=9 / large_service=5.

**Verification**:
- [x] All project template JSON parsed successfully.
- [x] Static audit: 36 public templates, no removed old replacement files, no public file/id mismatch.
- [x] `python -B -m pytest core\tests\unit\test_template_l5_expansion.py -q`: 3 passed.
- [x] D4 export from new `builtin_3a_axiom_verge.json` followed by Step00-08: all success.
- [x] Pipeline quality: 104 entities, requirement binding 1.0, placeholder rate 0, Step05 blocking 0.
- [x] `python -B -m pytest -q`: 122 passed.
- [x] `PYTHONPYCACHEPREFIX=.cache\pycache python -B -m compileall ...`: passed.
- [x] `git diff --check`: passed with only the existing CRLF working-copy warning.

**Follow-up**:
- [ ] This turn requested memory sync only; the code changes are not committed yet.
- [ ] Runtime validation draft `drafts\codex_template_2d_redesign_fixes_validation` should not be committed.
- [ ] `plan/` remains local execution material and should not be committed.
- [ ] CC-Panes shared memory was skipped because all required environment variables were absent.

---

**Date**: 2026-06-26
**ID**: 2026-06-26-004
**Summary**: Executed `template_2d_redesign`: rebuilt all 37 public templates as 2D L5 templates.

**Completed**:
- [x] All 37 public templates now set `profile.dimension = "2D"`; `template_index.json` mirrors `dimension = "2D"`.
- [x] Public template `qualityClaim` values are now `L5_complete_consistent`, with no public `L4_only_filled` entries.
- [x] Planned 3D/non-target replacements were rewritten as 2D reference games while keeping stable file names.
- [x] Every public template covers all 39 concrete nodes: 26 system_concrete nodes with 3 entities each and 13 content_concrete nodes with 2 entities each.
- [x] `builtin_indie_hades.json`, currently part of the public index, was also upgraded to 2D L5.
- [x] `core/tests/unit/test_template_l5_expansion.py` now validates public template count, index sync, 2D dimension, L5 claim, old 3D names, concrete coverage, and entity shape.

**Verification**:
- [x] All project template JSON parsed successfully.
- [x] Static public-template audit: 37 public entries, no `L4_only_filled`, no old 3D public names.
- [x] `python -B -m pytest core\tests\unit\test_template_l5_expansion.py -q`: 3 passed.
- [x] D4 export from the rebuilt Celeste template followed by Step00-08: all success.
- [x] Pipeline quality for the validation draft: 104 entities, requirement binding 1.0, placeholder rate 0, Step05 blocking 0.
- [x] `python -B -m pytest -q`: 122 passed.
- [x] `PYTHONPYCACHEPREFIX=.cache\pycache python -B -m compileall ...`: passed.
- [x] `git diff --check`: passed with only the existing CRLF working-copy warning.

**Follow-up**:
- [ ] Optional GUI spot-check of the template list to confirm renamed public entries display as expected.
- [ ] Validation draft `drafts\codex_template_2d_redesign_validation` is runtime output and should not be committed.
- [ ] Continue excluding `plan/` and bug documents from commits.
- [ ] CC-Panes shared memory was skipped because all required environment variables were absent.

---

**日期**：2026-06-26
**ID**：2026-06-26-003
**摘要**：执行 `directory_cleanup_analysis`：目录清理、存档进度总数修复与 plan 忽略规则统一

**完成内容**：
- ✅ 删除临时验证存档 `save_20260626_080638_065042` 及其关联 draft
- ✅ 剩余正式存档进度显示更新为 `9/18`
- ✅ 删除旧 plan 目录，保留最近 3 个计划目录和本轮分析文件
- ✅ 删除根目录旧 `.pytest_cache/` 和 legacy `sandbox/outputs/`
- ✅ `.gitignore` 改为统一忽略 `plan/`
- ✅ `core/save/manager.py`、`core/ui/save_manager_dialog.py` 的存档进度总数改为动态 `max_step_number()+1`
- ✅ `knowledge/ucos/scripts` 中旧 `pipeline_progress.total=16` 改为动态总步数

**自查修复**：
- ✅ 发现 `.gitignore` 实际未统一忽略 `plan/`，已修复
- ✅ 搜索发现 ucos 初始化/迁移脚本仍会写入旧 16 步进度，已修复
- ✅ 自检生成的 `core/__pycache__` 已路径校验后删除
- ✅ pytest 临时目录未强删：当前 63 个都未超过 7 天，继续依赖现有 7 天自动清理策略

**验证**：
- ✅ 关联回归测试：9 passed
- ✅ `python -B -m pytest -q`：121 passed
- ✅ `PYTHONPYCACHEPREFIX=.cache\pycache python -B -m compileall ...`：通过
- ✅ `python -B -m flake8 ... --select=F`：通过
- ✅ 旧 16 步进度字面量搜索无命中
- ✅ `.pytest_cache`、`sandbox/outputs`、源树 `__pycache__` 均不存在

**后续关注**：
- [ ] pytest `sandbox/pytest_*` 目录仍有 63 个，未超过 7 天，后续等 Windows 锁释放或自动清理
- [ ] drafts 仍有 42 个，当前都在 7 天内；后续可单独做自动清理策略
- [ ] 提交前确认 `plan/directory_cleanup_analysis.md` 和剩余 plan 目录不进入暂存区
- [ ] CC-Panes 共享记忆池本次因环境变量缺失未写入

---

**日期**：2026-06-26
**ID**：2026-06-26-002
**摘要**：执行 `manual_style_confirmation`：Step07/08 美术风格生成与人工确认门禁

**完成内容**：
- ✅ 新增 `pipeline/step_07_art_style_generation/`，输出风格候选、确定性 PNG 预览和生成日志
- ✅ 新增 `pipeline/step_08_art_style_confirmation/`，支持 `waiting_confirmation` 人工门禁、自动跳过门禁和已有确认复用
- ✅ 原 Step07-15 后移为 Step09-17，同步 core registry、pipeline registry、artifact layer registry、dependency graph 和 README
- ✅ CLI 新增 `--skip-all-gates` / `--skip-gate-08`，`run_range()` 使用动态 `max_step_number()`
- ✅ GUI 增加风格确认对话框、跳过人工确认选项和等待确认后的续跑/重新生成流程
- ✅ 修复 Step08 重跑时 `run_import_step()` 重置阶段目录导致 `style_confirmation.json` 被删除的问题
- ✅ 更新 AI 入口文档和 `knowledge/ai_memory/project_understanding` 中旧的 16 阶段/旧阶段号记忆

**验证**：
- ✅ 新增/关联回归测试：9 passed；新增人工确认测试：6 passed
- ✅ `python -B -m pytest -q`：120 passed
- ✅ 真实流水线 Step00-08：全部 success（使用 `--skip-all-gates` 验证自动通过路径）

**后续关注**：
- [ ] GUI 需要人工点选 Step08 对话框做一次视觉/交互验收
- [ ] 提交前确认 `plan/manual_style_confirmation/`、其他 `plan/` 临时目录、bug 文档和 `settings/api_config.toml` 不进入暂存区
- [ ] CC-Panes 共享记忆池本次因环境变量缺失未写入

---

**日期**：2026-06-26
**ID**：2026-06-26-001
**摘要**：执行 `universal_genre_coverage`：通用品类覆盖与 Step02 liveops 元数据过滤

**完成内容**：
- ✅ Step00 `_genre_key()` 改为有序规则推断，避免宽泛 shooter/puzzle/arena 抢先命中具体品类
- ✅ Step00 为计划列出的 17 个市场品类补齐 `GENRE_DEFAULT_EVIDENCE`
- ✅ Step02 governance node 过滤改为项目元数据感知：文档/帮助节点始终排除，liveops-only 节点只在明确买断/离线/单次发布项目中排除
- ✅ Step02 项目分类只读取 profile、project metadata、商业模式/运营模式 selections，避免 raw text 中节点 ID 污染分类
- ✅ 同步保留上一轮未提交修复：documentation 需求过滤、存档管理对话框文案/import 清理及相关回归测试

**验证**：
- ✅ 关联回归测试：3 passed
- ✅ `python -B -m pytest -q`：114 passed
- ✅ Hades 与 Stardew Valley 临时验证存档 Step00-08 全部 success

**后续关注**：
- [ ] Stage05 warning_count 当前为 1，属于非阻断 warning；如需归零可单独治理 L4-derived requirement 启发式
- [ ] 提交前确认 `plan/universal_genre_coverage/`、其他 `plan/` 临时目录、bug 文档和 `settings/api_config.toml` 不进入暂存区
- [ ] CC-Panes 共享记忆池本次因环境变量缺失未写入

---

**日期**：2026-06-25
**ID**：2026-06-25-002
**摘要**：执行 `hades_l5_step0008_opt` v2：Step00-08 质量优化

**完成内容**：
- ✅ PLAN-B：Step04 资产识别补充英文 environment 关键词，支持 `room` / `level` / `chamber` / `dungeon` / `tileset`
- ✅ PLAN-C：Step07 任务分类移除 `schema=...` 元数据干扰，并跳过 `documentation_*` 治理需求
- ✅ PLAN-A：Step02 `missing_entities` 优先输出真实 expected node_id，不再只给 `UNMAPPED-NODE-xxx`
- ✅ PLAN-A 补强：Step02 supplement request 接收 `missing_node_ids`，fallback 能按真实缺失 node_id 生成有限补全实体
- ✅ PLAN-B 补强：Step04 优先消费 Stage02 冻结/补全后的实体，补全 room/scene 能级联生成 environment 资产
- ✅ PLAN-D：Step00 `roguelike_action` 补充 CQ-011 运行时流程 genre evidence
- ✅ 新增回归测试覆盖英文 environment 资产、documentation 过滤、真实缺失节点追踪和 CQ-011 evidence

**自查修复**：
- ✅ black 格式化后重新跑全量测试和静态检查
- ✅ 真实配置重跑 Step00-08：`drafts\20260625_122737_33376`，步骤 00-08 全部 success
- ✅ 质量指标：question coverage 1.0，Step02 entity coverage 0.8447，asset_count 132，environment 4，Stage06 PASS，Step07 documentation 5

**验证**：
- ✅ 关联回归测试：75 passed
- ✅ `python -m pytest -q`：111 passed
- ✅ black / flake8 / `py_compile`：本轮触碰文件通过
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py tools\asset_production`：通过
- ✅ `git diff --check`：通过（仅 CRLF 工作区提示）

**后续关注**：
- [ ] 若后续要求 Step02 覆盖率接近 1.0，可继续扩展 missing-node fallback 上限或补齐源模板 L5 实体；本轮计划目标已达成
- [ ] 提交前确认 `plan/hades_l5_step0008_opt/`、其他 `plan/` 临时目录和 `settings/api_config.toml` 不进入暂存区
- [ ] CC-Panes 共享记忆池本次因环境变量缺失未写入

---

**日期**：2026-06-25
**ID**：2026-06-25-001
**摘要**：集中缓存目录与 Step05 绑定质量优化

**完成内容**：
- ✅ `.cache/pycache`、`.cache/pytest`、`.cache/mypy` 成为 Python/pytest/mypy 缓存集中目录
- ✅ `sitecustomize.py`、`core/__init__.py`、GUI 入口和 `conftest.py` 自动设置 pycache 前缀
- ✅ Step00 全量重跑时清理同一 active save 关联 sibling draft 的旧 `outputs/artifacts`
- ✅ Stage02 freeze contract 写入 `entities`、`systems`、`entity_stats`，Stage03 自动补齐需求系统绑定
- ✅ Step02 supplement 记录触发原因，并按未映射节点优先级补齐 `expected_kind`
- ✅ 新增/扩展测试覆盖缓存集中化、draft 清理、Step03 绑定和 supplement 触发诊断

**自查修复**：
- ✅ 清理源树分散 `__pycache__`，保留 `.cache/` 作为唯一缓存落点
- ✅ 修复 `core/ui/workbench.py` 中外部运行前同步/清理逻辑的局部结构问题
- ✅ 确认 `plan/cache_centralization/`、`plan/step05_optimization/` 仍为本地执行材料，不进入暂存区

**验证**：
- ✅ `python -m pytest -q`：105 passed
- ✅ 目标 Step05/L5 回归：64 passed
- ✅ black / flake8 / 目标 mypy / `py_compile`：通过
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py tools\asset_production`：通过
- ✅ `git diff --check`：通过（仅 CRLF 工作区提示）

**后续关注**：
- [ ] 直接对 `core/engines/generation.py` 跑全量 mypy 仍有既有历史弱类型问题，后续可独立治理
- [ ] 后续 Python 工具运行继续保持 `PYTHONPYCACHEPREFIX=.cache/pycache`
- [ ] 提交前确认 bug 文档、`plan/` 临时执行目录和 `settings/api_config.toml` 不进入暂存区
- [ ] CC-Panes 共享记忆池本次因环境变量缺失未写入

---

**日期**：2026-06-24
**ID**：2026-06-24-006
**摘要**：修复 Codex sandbox、图片配置与 pytest basetemp 清理

**完成内容**：
- ✅ Step02 Codex sandbox 从非法 `none` 改为 `read-only`，兼容 Codex CLI 0.141.0
- ✅ `image2` / `image` / `llm` API 配置支持继承回退，旧图片工具改用 `core.config.loader`
- ✅ Stage09/Stage11 输出 `generated_images_manifest.json`，真实图片生成改为显式环境变量开启
- ✅ pytest 旧 basetemp 自动清理，只删除超过 7 天的严格时间戳目录
- ✅ `.gitignore` 补充本地报告类文档忽略规则，继续避免 bug 文档和临时计划入库
- ✅ 新增/更新回归测试覆盖 sandbox、图片配置、manifest 和 pytest 清理

**自查修复**：
- ✅ 修正只有 `[llm]` 配置时图片模型误继承文本模型的边界，默认使用 `gpt-image-2`
- ✅ 修复旧 `Image2Generator` 导入不存在的 `tools.config_loader`
- ✅ 确认 `settings/api_config.toml` 仅本地读取，不输出、不提交

**验证**：
- ✅ `python -m pytest -q`：97 passed
- ✅ black / flake8 / mypy / `py_compile`：通过
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py tools\asset_production`：通过
- ✅ `git diff --check`：通过（仅 CRLF 工作区提示）

**后续关注**：
- [ ] 需要实图验收时设置 `AUTODESIGNMAKER_ENABLE_IMAGE_GENERATION=1`
- [ ] 提交前确认 bug 文档、`plan/` 临时执行目录和 `settings/api_config.toml` 不进入暂存区
- [ ] CC-Panes 共享记忆池本次因环境变量缺失未写入

---

**日期**：2026-06-24
**ID**：2026-06-24-005
**摘要**：修复 pytest 临时目录与 draft 生命周期管理

**完成内容**：
- ✅ pytest 默认 basetemp 改为 `sandbox/pytest_<timestamp>`，cache 改为 `sandbox/pytest_cache`，避免 Windows Temp / `.pytest_cache` 权限问题
- ✅ 默认 pytest 收集范围限定为 `core/tests`，避免开发工具脚本误收集
- ✅ Hades 质量测试删除冗余断言，并提取模板节点数常量；任务标题长度 magic number 提取为常量
- ✅ 新增 draft 生命周期策略：启动时保留最近未关联 drafts，删除存档时清关联 draft，step0 重跑清当前 artifacts
- ✅ `draft_meta.json` 写入 `linked_save_id`，同时兼容旧 `linked_archive_path`
- ✅ `.gitignore` 防止 pytest 遗留缓存与临时 plan 入库

**自查修复**：
- ✅ 修复 `conftest.py` docstring 中 Windows 路径说明触发的 `W605 invalid escape sequence`
- ✅ 清理 `core/main.py`、`core/ui/workbench.py` 中 flake8 暴露的未使用 import/变量
- ✅ 历史 `drafts/` 一次性删除未执行，需用户明确确认

**验证**：
- ✅ `python -m pytest -q`：90 passed
- ✅ `python -m pytest core\tests\unit\test_draft_archive_paths.py core\tests\unit\test_core_paths.py -q`：11 passed
- ✅ `python -m pytest core\tests\unit\test_core_paths.py -q --basetemp=sandbox\pytest_tmp_explicit`：4 passed
- ✅ flake8 / mypy / `py_compile -W error::SyntaxWarning`：通过
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ `git diff --check`：通过（仅 CRLF 工作区提示）

**后续关注**：
- [ ] 历史 `drafts/` 清理属于不可逆用户数据删除，执行前必须再次确认
- [ ] 提交前确认 bug 文档和 `plan/` 临时执行目录不进入暂存区
- [ ] CC-Panes 共享记忆池本次因环境变量缺失未写入

---

**日期**：2026-06-24
**ID**：2026-06-24-004
**摘要**：执行 `hades_quality_optimization`：Hades 质量优化与标准化沉淀

**完成内容**：
- ✅ Hades partial 模板从 39/103 节点扩展到 103/103 节点，超过计划 80+ 覆盖目标
- ✅ Step07 程序任务标题清理，并新增 `category` / `priority`
- ✅ Step08 美术任务透传/生成 `asset_type` / `category` / `priority` / `complexity`
- ✅ 修复 Codex CLI Windows shim：优先 `codex.cmd` / `codex.exe`，避免 PowerShell `.ps1` 执行策略阻断
- ✅ 建立 `knowledge/governance/quality_standards/` 标准体系，共 17 个标准、模板、手册和指标文档

**自查修复**：
- ✅ 发现裸 `codex` 在 PowerShell 下会命中被拦截的 `codex.ps1`，已在 executor 中避开
- ✅ 任务标题清理后只剩泛词时使用 fallback，避免输出“资源”这类弱标题

**验证**：
- ✅ `python -m pytest core\tests -q`：87 passed（仅 `.pytest_cache` 写入权限 warning）
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ 内置模板 JSON 解析通过，Hades partial 覆盖 103 节点
- ✅ `codex.cmd --version`：`codex-cli 0.141.0`
- ✅ `git diff --check`：通过（仅 CRLF 工作区提示）

**后续关注**：
- [ ] GUI 重新载入/导出 Hades partial 后运行 Step02-09，验证新 draft 质量指标
- [ ] 提交前确认 `plan/hades_quality_optimization/` 和根目录临时评分报告不进入暂存区

---

**日期**：2026-06-24
**ID**：2026-06-24-003
**摘要**：执行 `template_l5_expansion`：内置模板 L5 实体覆盖扩展

**完成内容**：
- ✅ Phase 1 partial 模板补到 39 节点 complete 标准，并对齐 `elden_ring` 既有 complete 实体结构质量
- ✅ Phase 2 的 8 个 Indie 模板补齐 P0 16 核心节点实体
- ✅ Phase 3 的 7 个 3A 模板补齐 P0 16 核心节点实体
- ✅ Phase 4 的服务型、Midcore 和 IAA 超休闲模板补齐 P0 16 核心节点实体
- ✅ 新增 `test_template_l5_expansion.py` 覆盖 complete/P0 覆盖率与实体 schema 结构质量

**自查修复**：
- ✅ 修正旧有 `elden_ring` 曲线采样点不足、循环步骤不足和缺失 `supplement_basis` 的结构问题
- ✅ 临时批处理脚本执行后已删除，未留下开发过程工具

**验证**：
- ✅ `python -m pytest core\tests -q`：82 passed（仅 `.pytest_cache` 写入权限 warning）
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ 新增测试 black/flake8/mypy：通过
- ✅ 内置模板 JSON 解析通过；排除基础参考 `builtin_indie_hades.json` 后，8 个 complete、30 个 P0，缺失列表为空

**后续关注**：
- [ ] 提交前继续确认 `plan/template_l5_expansion/` 不进入暂存区
- [ ] GUI 载入模板后抽样检查 Step02 实体覆盖报告是否显示预期等级

---

**日期**：2026-06-24
**ID**：2026-06-24-002
**摘要**：提交范围纠正：本地 bug 文档和临时开发计划不入库

**完成内容**：
- ✅ 从上一笔提交中移除 `bug收集文档*.md`、`bug优化文档*.md` 和 `plan/l5_entity_ai_supplement/`
- ✅ `.gitignore` 增加小范围规则，防止本地 bug 文档和临时开发计划再次被误加
- ✅ `knowledge/ai_memory/code_conventions/anti_patterns.md` 补充提交禁令
- ✅ 记住提交前必须检查 `git status --short` 和 `git diff --cached --name-only`

**自查修复**：
- ✅ bug 文档只作为本地审查输入读取和处理，不提交到 git
- ✅ 临时开发执行计划只作为本地任务材料使用，不提交到 git

**验证**：
- ✅ 更新项目记忆并运行 `python tools\memory\update_freshness.py`
- ✅ 使用 amend 修正上一笔提交，不追加无意义修正提交

**后续关注**：
- [ ] 后续提交前确认暂存区不包含本地 bug 文档和临时执行计划
- [ ] 真实 Codex CLI 环境中仍需跑 Step02，确认 stdout JSON 能被 `_parse_response()` 接收

---

**日期**：2026-06-24
**ID**：2026-06-24-001
**摘要**：修复 `bug收集文档7.md` 第七轮 BUG-024/025：AI 补全适配器连通性

**完成内容**：
- ✅ BUG-024：`ModelTask` 增加 `sandbox` 字段，默认仍为 `workspace-write`
- ✅ BUG-024：`run_codex_exec()` 使用 `task.sandbox`，Step02 supplement 显式传 `sandbox="none"`
- ✅ BUG-025：`ClaudeCodeModelAdapter.generate()` 改用 `task.timeout_seconds`，不再硬编码 600 秒
- ✅ 新增适配器回归测试覆盖 Codex sandbox 和 Claude 超时透传

**验证**：
- ✅ `python -m pytest core\tests -q`：80 passed（仅 `.pytest_cache` 写入权限 warning）
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ 本次触碰文件 black/flake8/mypy：通过

---

**日期**：2026-06-23
**ID**：2026-06-23-012
**摘要**：修复 `bug收集文档6.md` 第六轮 BUG-023：无效 adapter 不再击穿 Step02

**完成内容**：
- ✅ BUG-023：`_call_ai()` 继续让 `ValueError/ImportError` 暴露，保留底层配置错误可见性
- ✅ `supplement()` 捕获 adapter 配置错误并降级到本地 fallback 实体，Step02 不再崩溃
- ✅ `SupplementResult.error` 与 `entity_coverage_report.json.ai_supplement.error` 记录 `unknown adapter` 等原因
- ✅ 补充分层回归测试：底层抛错、业务入口 fallback、`_stage2_outputs()` 无效 adapter 不崩溃

**验证**：
- ✅ `python -m pytest core\tests -q`：76 passed（仅 `.pytest_cache` 写入权限 warning）
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ 本次触碰文件 black/flake8/mypy：通过

---

**日期**：2026-06-23
**ID**：2026-06-23-011
**摘要**：修复 `bug收集文档5.md` 第五轮 5 个 L5 AI 补全问题

**完成内容**：
- ✅ BUG-018：adapter 配置错误直接抛出，不再被 `_call_ai()` 静默降级
- ✅ BUG-019：Step01 暴露公开 `pick_genre_template_key()`，Step02 不再导入私有 `_pick_template_key`
- ✅ BUG-020：AI adapter 实例化移到重试循环外，避免重复创建
- ✅ BUG-021：缺失 `pipeline_adapter` 时默认 `none`，Step02 AI 补全默认关闭
- ✅ BUG-022：旧缓存缺少 `supplement_basis` 时仍可命中

**验证**：
- ✅ `python -m pytest core\tests -q`：74 passed（仅 `.pytest_cache` 写入权限 warning）
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过
- ✅ 新增补全模块 black/flake8/mypy：通过

---

**日期**：2026-06-23
**ID**：2026-06-23-010
**摘要**：执行 `plan/l5_entity_ai_supplement`：Step02 L5 实体 AI 补全、缓存、降级与测试

**完成内容**：
- ✅ Step02 支持 `status=approximate` 概略实体解析和 `should_supplement()` 触发判断
- ✅ 新增 `EntitySupplementAdapter`，支持 AI 调用、缓存、失败降级和实体合并
- ✅ 新增补全提示词与多品类降级实体库
- ✅ `generation.py` Step02 接入补全适配器，`pipeline_adapter=none` 可关闭
- ✅ 新增 19 个 L5 supplement 单元/集成测试

**验证**：
- ✅ `python -m pytest core\tests -q`：66 passed（仅 `.pytest_cache` 写入权限 warning）
- ✅ `python -m compileall core pipeline tools\validators\pipeline_quality.py`：通过

---

**日期**：2026-06-23
**ID**：2026-06-23-009
**摘要**：溯源 `范本：Hades` 自动化开发 Step05 阻断：源包仍是 `未命名游戏设计项目` 空白状态

**完成内容**：
- ✅ 确认 Step05 `BLOCKED` 来自占位符质量门禁，不是评审代码异常
- ✅ 追溯到 `source_artifacts/devflow_Concept_v2` / `devflow_Design_v2`，确认导出源包不是 Hades
- ✅ 对比失败 draft 时间和 `范本：Hades` 存档创建时间，确认流水线早于 Hades 存档创建
- ✅ 记录排错经验：Step05 placeholder 阻断应向上检查导出源包和 Stage00/02/03 产物

**验证**：
- ✅ `stage_05/intelligent_review_report.json`：`verdict=BLOCKED`，阻断项为 `placeholder_rate`
- ✅ `stage_03/program_requirements_contract.json`：4 条需求全部包含 `未命名游戏设计项目`
- ✅ `source_artifacts/.../concept.md` / `design.md`：标题仍为 `未命名游戏设计项目`

---

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
