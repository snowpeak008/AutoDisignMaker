# Step11 标准化 Bug 修复开发计划

## 一、设计目的

本计划目标不是做最小补丁，也不是只让 Step11 暂时跑过，而是把 Step11“程序开发执行”阶段按标准工程方式修正到一致、可恢复、可测试、可维护的状态。

当前 Step11 的核心问题不是单点异常，而是历史阶段迁移后留下了多处语义错配：

- Step11 主流程存在 Python 局部作用域遮蔽，导致正常执行路径直接崩溃。
- Step11 的历史执行记录读取仍使用旧存档目录 `save/`，而当前正式存档系统是 `saves/`。
- Step11 的辅助函数、恢复目录、事件名、run state、用户可见日志仍混用 `stage10` / `Stage 12`。
- 暂停恢复相关路径和状态字段会误导 UI、日志、后续排障和无人值守恢复。

修复后的目标是：

1. Step11 可以稳定进入真实开发执行分支。
2. Step11 的运行状态、恢复记录、日志、事件名全部表达为 Step11 / Development Execution。
3. 新数据写入标准 Step11 路径。
4. 历史错误路径保留读取兼容，避免用户已有中断状态丢失。
5. 存档历史读取只以 `core.save.manager` 为主路径 API，不再硬编码旧目录。
6. 有测试覆盖作用域遮蔽、存档读取、恢复目录兼容、soft stop 状态和用户文案。

## 二、修复原则

### 2.1 不做粗暴全局替换

不能全项目把 `Stage 12` 改成 `Stage 11`。

原因：

- 当前真正的 Step12 是 Art Production。
- Step13 后续校验中有些 `Stage 12` 文案确实指向美术生产阶段。
- 只有 Step11 开发执行路径中的误写文案才应修正。

### 2.2 新写标准路径，旧路径只读兼容

Step11 任务恢复记录标准写入：

```text
outputs/checkpoints/stage_11_resume_records/
```

旧路径只作为读取 fallback：

```text
outputs/checkpoints/stage_12_resume_records/
```

不再向旧路径写入新记录。

### 2.3 存档路径必须走 save_manager

当前正式存档根目录是：

```text
saves/
```

Step11 不应再写死：

```text
BASE_DIR / "save" / "save_index.json"
BASE_DIR / "save" / save_id / "workspace"
```

应改为：

```python
save_manager.current_save_id(BASE_DIR)
save_manager.workspace_dir(BASE_DIR, save_id)
```

旧 `save/` 目录如果要兼容，只允许在专门 helper 中 fallback 读取，不能作为主路径。

### 2.4 内部命名应与业务阶段一致

Step11 相关私有 helper 应统一为 `_stage11_*`，不要继续用 `_stage10_*`。

这不是单纯美化。函数名会影响排障效率、日志定位、测试命名和后续维护判断。

### 2.5 外部产物保持兼容

以下 Step11 产物名保持不变：

```text
devexecution.json
devexecution.md
devexecution_progress.json
development_execution_log.json
actual_development_report.json
actual_development_blocked.json
changed_files_manifest.json
package_change_report.json
DEV-*_execution.json
pause_resume_log.md
unattended_execution_summary.json
correction_queue.json
correction_queue.md
dependency_skip_report.json
repair_attempts.jsonl
save_sync_warning.json
```

原因：这些是 Stage11 对外契约，不能因为内部重命名破坏 UI、存档或下游读取。

## 三、当前问题清单

### BUG-001：Step11 主流程作用域遮蔽

位置：

```text
core/engines/generation.py::_stage11_outputs()
```

问题：

函数前半段读取：

```python
settings = load_project_settings(BASE_DIR)
```

函数后半段又局部导入：

```python
from core.runtime.preflight import load_project_settings
```

Python 会把 `load_project_settings` 判定为整个函数的局部变量，导致前半段读取时报：

```text
cannot access local variable 'load_project_settings' where it is not associated with a value
```

目标：

- 删除函数内部重复 import。
- 增加 AST 回归测试，禁止 Step11 再出现同类“先读取、后局部 import/赋值遮蔽模块级名称”的问题。

### BUG-002：Step11 历史记录读取使用旧 `save/`

位置：

```text
core/engines/generation.py::_previous_stage10_report()
core/engines/generation.py::_previous_records_by_task()
```

问题：

读取：

```python
BASE_DIR / "save" / "save_index.json"
BASE_DIR / "save" / save_id / "workspace"
```

当前标准路径是：

```text
saves/save_index.json
saves/<save_id>/workspace/
```

目标：

- 改为 `save_manager.current_save_id()` 和 `save_manager.workspace_dir()`。
- 新增 helper 封装“当前 save workspace 的 stage 目录”。
- 可选 fallback 读取旧 `save/`，但必须集中在 helper 里，并标记为 legacy。

### BUG-003：Step11 恢复目录误写为 Stage12

位置：

```python
def _stage10_resume_dir() -> Path:
    return BASE_DIR / "outputs" / "checkpoints" / "stage_12_resume_records"
```

问题：

Step11 的 DEV 任务记录被写入 `stage_12_resume_records`。

目标：

- 新写入 `stage_11_resume_records`。
- 读取时先读新目录，再读旧目录。
- 测试确认新记录不会再写入旧目录。

### BUG-004：Step11 run_state 和 stop report 阶段错配

问题点：

```python
unit_type="stage12_task"
```

```python
"stage": 10
```

事件名：

```python
event="stage10_soft_stopped"
```

目标：

- `unit_type` 改为 `stage11_task`。
- stop report `stage` 改为 `DEV_EXECUTION_STAGE`。
- event 统一使用 `stage11_*`。
- UI 读取 run_state 不应依赖旧 `stage12_task`，如有依赖则同步兼容。

### BUG-005：Step11 用户可见文案误写 Stage12

Step11 开发执行分支内的文案误写为 Stage12：

```text
Stage 12 stopped at a resumable task boundary.
Stage 12 is still executing.
Stage 12 must not fabricate development success.
No Unity project files were modified by Stage 12.
Reused existing Codex-generated outputs from the previous Stage 12 attempt.
```

目标：

- Step11 分支内全部改成 `Step 11` 或 `Development Execution`。
- 不改真正 Step12 Art Production 的文案。
- 不改 Step13 针对 Step12 艺术生产的合法提示。

## 四、目标架构

### 4.1 Step11 常量

在 `core/engines/generation.py` 中靠近阶段常量处新增或整理：

```python
DEV_EXECUTION_STAGE = 11
DEV_EXECUTION_STAGE_LABEL = "Step 11"
DEV_EXECUTION_STAGE_NAME = "Development Execution"
DEV_EXECUTION_TASK_UNIT_TYPE = "stage11_task"
DEV_EXECUTION_RESUME_DIR_NAME = "stage_11_resume_records"
LEGACY_DEV_EXECUTION_RESUME_DIR_NAMES = ("stage_12_resume_records",)
```

如果不想扩大常量区，也至少要在 Step11 helper 区域集中定义，不能散落字符串。

### 4.2 Step11 路径 helper

**checkpoint 根路径唯一标准**：使用 `stage_dir(DEV_EXECUTION_STAGE)` 作为基准，好处是测试时只需 monkeypatch `stage_dir` 即可隔离，不需要额外处理 `BASE_DIR`。禁止再出现 `BASE_DIR / "outputs" / "checkpoints"`。

新增 helper：

```python
def _stage11_resume_dir() -> Path:
    # checkpoints 与当前 stage 产物同根，测试时只需 monkeypatch stage_dir
    return stage_dir(DEV_EXECUTION_STAGE).parent.parent / "checkpoints" / "stage_11_resume_records"


def _stage11_legacy_resume_dirs() -> list[Path]:
    # 历史兼容只读，后续可移除
    base = stage_dir(DEV_EXECUTION_STAGE).parent.parent / "checkpoints"
    return [base / "stage_12_resume_records"]


def _stage11_resume_read_dirs() -> list[Path]:
    return [_stage11_resume_dir(), *_stage11_legacy_resume_dirs()]
```

当前存档 stage helper，直接复用已有 API（`save_manager.current_save_workspace_dir` 已在 `core/save/manager.py:529` 存在）：

```python
def _current_save_stage_dir(stage: int) -> Path | None:
    ws = save_manager.current_save_workspace_dir(BASE_DIR)
    if not ws:
        return None
    return ws / "outputs" / "artifacts" / f"stage_{stage:02d}"
```

旧目录兼容 helper（只读，有注释标明可移除）：

```python
def _legacy_save_stage_dir(stage: int) -> Path | None:
    # Legacy: 旧存档根目录为 save/，当前为 saves/，仅用于 fallback 读取，禁止写入
    index = read_json(BASE_DIR / "save" / "save_index.json", {})
    if not isinstance(index, dict):
        return None
    save_id = str(index.get("current_save_id") or "")
    if not save_id:
        return None
    return BASE_DIR / "save" / save_id / "workspace" / "outputs" / "artifacts" / f"stage_{stage:02d}"
```

要求：

- 主逻辑先用 `_current_save_stage_dir(DEV_EXECUTION_STAGE)`。
- `_legacy_save_stage_dir` 只用于读取，不用于写入，注释标明为历史兼容。
- 禁止在新代码里出现 `BASE_DIR / "outputs" / "checkpoints"`。

### 4.3 Step11 内部 helper 重命名

重命名：

```text
_previous_stage10_report              -> _previous_stage11_report
_stage10_resume_dir                   -> _stage11_resume_dir
_write_stage10_task_record            -> _write_stage11_task_record
_write_stage10_progress               -> _write_stage11_progress
_sync_stage10_checkpoint              -> _sync_stage11_checkpoint
_ordered_stage10_task_ids             -> _ordered_stage11_task_ids
_next_stage10_task_id                 -> _next_stage11_task_id
_write_stage10_stop_report            -> _write_stage11_stop_report
_stage10_active_execution_object_id   -> _stage11_active_execution_object_id
```

注意：

- 这些 helper 是内部私有函数，优先全量改调用点。
- 如果测试或其他模块直接 import 私有函数，需要同步更新测试。
- 不建议长期保留 `_stage10_*` alias，否则会继续制造误导。

### 4.4 Step11 输出契约

保持这些对外文件名不变：

```text
stage_11/devexecution.json
stage_11/development_execution_log.json
stage_11/DEV-001_execution.json
```

内部字段修正：

```json
{
  "stage": 11,
  "unit_type": "stage11_task",
  "task_record_source": "stage_11/DEV-*_execution.json"
}
```

如果某些历史记录已经写成：

```json
{
  "unit_type": "stage12_task"
}
```

读取方可以兼容展示，但新写入必须是 `stage11_task`。

## 五、详细实施步骤

### Phase 0：基线检查

执行：

```powershell
python -B -m pytest core\tests\unit\test_unattended_recovery.py -q
python -B -m py_compile core\engines\generation.py pipeline\step_11_dev_execution\plugin.py
```

目的：

- 确认当前测试基线。
- 如果已有 P0 删除 import 的本地改动，记录其 diff，避免误判。

### Phase 1：修复作用域遮蔽并加回归测试

文件：

```text
core/engines/generation.py
core/tests/unit/test_unattended_recovery.py
```

代码改动：

- 删除 `_stage11_outputs()` 内部的：

```python
from core.runtime.preflight import load_project_settings
```

测试：

新增 AST 测试：

```python
def test_stage11_has_no_local_import_shadowing_module_names():
    ...
```

测试规则：

- 只扫描 `_stage11_outputs()` 和 Step11 helper 区间。
- 找出模块级已导入名称。
- 如果函数内出现局部 import/赋值，并且同名读取发生在局部绑定之前，则失败。

验收：

- 当前 `load_project_settings` 问题会被测试捕获。
- 删除内部 import 后测试通过。

### Phase 2：标准化 Step11 helper 命名

文件：

```text
core/engines/generation.py
```

改动：

- 按 4.3 全量重命名 helper。
- 全量更新调用点。
- 不改变对外文件名。

检查命令：

```powershell
rg -n "_stage10_|stage10_" core\engines\generation.py
```

允许剩余：

- `_stage10_outputs()` 本身，因为 Step10 资产对齐阶段仍真实存在。
- Stage10 plan/topology 的业务引用，如果确实指 Step10 产物。

不允许剩余：

- Step11 执行路径中的 `_stage10_*` helper。
- Step11 soft stop event `stage10_*`。

### Phase 3：修复恢复目录，增加旧目录读取兼容

文件：

```text
core/engines/generation.py
core/tests/unit/test_unattended_recovery.py
```

改动：

- 新写入目录：

```text
outputs/checkpoints/stage_11_resume_records/
```

- 读取目录顺序：

```text
1. outputs/checkpoints/stage_11_resume_records/
2. outputs/checkpoints/stage_12_resume_records/  # legacy fallback
```

测试：

1. 写任务记录后，断言新目录存在且有 `DEV-001_execution.json`。
2. 断言旧目录不会被新写入创建。
3. 构造旧目录 `stage_12_resume_records/DEV-001_execution.json`，断言 `_previous_records_by_task()` 能读取。
4. 新旧目录都有同一任务时，新目录记录优先。

### Phase 4：修复当前存档历史读取路径，标准化记录合并优先级

文件：

```text
core/engines/generation.py
core/tests/unit/test_unattended_recovery.py
```

改动：

`_previous_stage11_report()` 和 `_previous_records_by_task()` 改用路径 helper，不再直接写 `BASE_DIR / "save"`。

**记录合并优先级**（active draft 是正在执行的事实源，正式 save workspace 可能因 per-group sync 而落后，不能无条件高优）：

```text
1. 当前 active stage_11/DEV-*_execution.json        ← 最高优先，当前运行事实
2. 当前 active stage_11_resume_records/             ← checkpoint 写入点
3. saves/<current_save_id>/workspace/stage_11/     ← 正式存档（可能落后）
4. stage_12_resume_records/                        ← legacy checkpoint（旧路径）
5. save/<save_id>/workspace/stage_11/              ← legacy 存档（旧目录名）
```

实现方式：抽出 `_merge_task_records(sources: list[Path]) -> dict[str, dict]`，按参数顺序表达优先级——**列表越靠前优先级越高，每个 `task_id` 首次命中即确定，不被后续来源覆盖**。调用时按五级优先级从高到低传入：

```python
_merge_task_records([
    stage_dir(DEV_EXECUTION_STAGE),               # 1. active stage 目录
    _stage11_resume_dir(),                         # 2. active checkpoint
    _current_save_stage_dir(DEV_EXECUTION_STAGE),  # 3. formal save workspace
    *_stage11_legacy_resume_dirs(),                # 4. legacy checkpoint
    _legacy_save_stage_dir(DEV_EXECUTION_STAGE),   # 5. legacy save 目录
])
```

同一优先级内如果出现同 `task_id` 的多条记录（理论上极少，例如同目录内有多个同名 json），以 `generated_at` 字段更新的为准作为 tiebreaker。禁止在调用点混用 `=` 和 `setdefault` 来隐式表达优先级。

测试：

1. 构造标准 `saves/<save_id>/workspace/outputs/artifacts/stage_11/devexecution.json`，断言 `_previous_stage11_report()` 能读取。
2. 构造 active stage 目录和 saves 存档同一任务但内容不同，断言 active stage 目录记录优先。
3. 构造新旧 checkpoint 目录都有任务，断言 `stage_11_resume_records` 优先于 `stage_12_resume_records`。
4. 不存在 current save 时，函数返回 active stage 和 checkpoint 记录，不抛异常。
5. 断言新逻辑通过 `_merge_task_records` 或等价 helper 表达优先级，不再在多个读取循环中混用 `=` 和 `setdefault`。

### Phase 5：修复 run_state、stop report、event 名

文件：

```text
core/engines/generation.py
core/runtime/control.py  # 仅当需要增加 schema 注释或兼容 helper
core/ui/pipeline_panel.py  # 仅当 UI 依赖 unit_type
core/tests/unit/test_unattended_recovery.py
```

改动：

- `unit_type="stage12_task"` 改为 `unit_type="stage11_task"`。
- `_write_stage11_stop_report()` 输出 `"stage": DEV_EXECUTION_STAGE`。
- `stage10_soft_stopped` 改为 `stage11_soft_stopped`。
- `stage10_*_checkpoint` 事件改为 `stage11_*_checkpoint`。
- `stage11_group_completed_with_review` 已正确，保留。

UI 检查：

- `PipelinePanel._append_pause_resume_summary()` 已按 stage 11/12 分别读 `pause_resume_log.md`，不依赖 `unit_type`。
- 如果其它 UI 后续展示 `run_state.unit_type`，应兼容旧 `stage12_task` 但标准显示 Step11。

测试：

1. 调用 `_write_stage11_progress()` 后读取 `run_state.json`。
2. 断言：

```json
{
  "current_step": 11,
  "unit_type": "stage11_task"
}
```

3. 调用 `_write_stage11_stop_report()` 后断言：

```json
{
  "stage": 11
}
```

### Phase 6：修复 Step11 用户可见文案，扩展至 Step13 误写

文件：

```text
core/engines/generation.py
```

**Step11 分支内**（`_stage11_outputs()` 及其 helper），只修改 Step11 执行路径内的误写文案：

```text
Stage 12 stopped at a resumable task boundary.     → Step 11 stopped at a resumable task boundary.
Stage 12 is still executing.                       → Step 11 is still executing.
Stage 12 must not fabricate development success.   → Step 11 must not fabricate development success.
No Unity project files were modified by Stage 12.  → No Unity project files were modified by Step 11.
Reused existing Codex-generated outputs from the previous Stage 12 attempt.
                                                   → Reused existing Codex-generated outputs from the previous Step 11 attempt.
```

**Step13 分支内**（`_stage13_outputs()`），以下三条读取的是 `DEV_EXECUTION_STAGE`（Step11）产物，语义错配，一并修正：

```text
Line 5781: "Stage 12 produced no real development records."
           → "Step 11 produced no real development records."

Line 5799: "Stage 12 did not record Unity batchmode validation."
           → "Step 11 did not record Unity batchmode validation."

Line 5826: "Stage 12/13 execution objects must be verified before integration."
           → "Step 11/12 execution objects must be verified before integration."
```

不改的 `Stage 12` 范围：Step12 Art Production 自身逻辑、Step13 中确实指向美术生产阶段的校验文案。

验收：

```powershell
rg -n "Stage 12" core\engines\generation.py
```

人工确认剩余 `Stage 12` 均属于 Step12 Art Production 或 Step13 针对美术生产的合法校验，不出现在开发执行（Step11）读取路径上。

### Phase 7：测试补强

新增或扩展测试文件：

```text
core/tests/unit/test_unattended_recovery.py
```

如果测试变得过长，可拆出：

```text
core/tests/unit/test_step11_execution_state.py
```

建议测试项：

1. `test_stage11_has_no_local_import_shadowing_module_names`
2. `test_stage11_task_records_write_to_stage11_resume_dir`
3. `test_stage11_previous_records_read_legacy_stage12_resume_dir`
4. `test_stage11_previous_records_prefer_stage11_resume_dir_over_legacy`
5. `test_stage11_previous_records_read_current_save_workspace_from_saves`
6. `test_stage11_run_state_uses_stage11_task_unit_type`
7. `test_stage11_stop_report_uses_stage_11`
8. `test_stage11_progress_text_does_not_claim_stage12_execution`

测试策略：

- 尽量测 helper，不真实调用外部 Codex/Unity。
- 用 `tmp_path` 和 monkeypatch 替换 `BASE_DIR`、`stage_dir()`、`save_manager.current_save_workspace_dir()`。
- 不依赖真实用户存档。
- 不访问网络。

### Phase 8：集成验证

执行：

```powershell
python -B -m pytest core\tests\unit\test_unattended_recovery.py -q
python -B -m pytest core\tests\unit\test_manual_style_confirmation.py -q
python -B -m pytest core\tests\integration\test_plugins.py -q
python -B -m pytest -q
python -B -m compileall -q core pipeline tools\validators\pipeline_quality.py tools\asset_production tools\config tools\design tools\save\repair_blank_save_progress.py
git diff --check
```

如果完整 `pytest -q` 失败：

- 先判断是否是本次 Step11 改动导致。
- 如果是现有环境缺少 Unity/Codex 外部依赖，不应把失败吞掉，要在最终报告中明确。

## 六、兼容迁移策略

### 6.1 Resume 记录兼容

读取顺序：

```text
stage_11_resume_records -> stage_12_resume_records
```

写入策略：

```text
只写 stage_11_resume_records
```

冲突策略：

- 同一 `task_id` 同时存在新旧记录时，新记录优先。
- legacy 记录只补充新记录中没有的任务。

### 6.2 Save 路径兼容

读取顺序：

```text
saves/<current_save_id>/workspace -> save/<current_save_id>/workspace
```

写入策略：

```text
只通过 save_manager 写入当前 saves/ 系统
```

注意：

- 不创建新的 `save/` 目录。
- 不把 legacy `save/` 迁移到 `saves/`，本计划只做读取兼容。

### 6.3 run_state 兼容

新写入：

```json
{
  "unit_type": "stage11_task"
}
```

旧数据兼容：

- UI 如果看到旧 `stage12_task` 且 `current_step == 11`，展示为 Step11 任务。
- 不需要主动迁移旧 `run_state.json`，下一次写入会覆盖。

## 七、风险与规避

### 风险 1：函数重命名漏改调用点

规避：

```powershell
rg -n "_stage10_" core\engines\generation.py
python -B -m py_compile core\engines\generation.py
```

并跑 Step11 相关测试。

### 风险 2：误伤真实 Step12 文案

规避：

- 不全局替换。
- 每个 `Stage 12` 改动都必须确认处于 `_stage11_outputs()` 或 Step11 helper。

### 风险 3：旧 resume 记录无法恢复

规避：

- 保留旧 `stage_12_resume_records` 读取。
- 新旧同任务冲突时新优先。
- 增加兼容测试。

### 风险 4：旧 `save/` 数据无法读取

规避：

- 主路径改 `saves/`。
- fallback 读取旧 `save/`。
- 只读兼容，不写旧路径。

### 风险 5：测试 monkeypatch BASE_DIR 后路径仍指真实目录

规避：

- 抽出 path helper 后测试 helper。
- monkeypatch `generation.BASE_DIR` 和必要的 `generation.stage_dir`。
- 不让测试写入真实 `drafts/`、`saves/`、`outputs/`。

## 八、验收标准

功能验收：

- Step11 不再因 `load_project_settings` 抛 `UnboundLocalError`。
- Step11 新任务记录写入 `stage_11_resume_records`。
- 旧 `stage_12_resume_records` 可被读取。
- 当前存档历史从 `saves/` 读取。
- `devexecution_stop_report.json.stage == 11`。
- `run_state.json.unit_type == "stage11_task"`。
- Step11 用户可见日志不再声称 Stage12 正在执行或停止。

测试验收：

- Step11 新增单测全部通过。
- 现有无人值守测试通过。
- 插件集成测试通过。
- 全量测试通过或明确记录与本次无关的环境型失败。

代码质量验收：

- 不新增硬编码 `BASE_DIR / "save"`。
- 不新增 Step11 执行路径里的 `stage10_*` 事件名。
- 不新增 Step11 执行路径里的 `stage_12_resume_records` 写入。
- 不新增函数内局部 import 遮蔽模块级名称。

## 九、建议提交拆分

如果开发时需要分提交，建议：

1. `fix: remove step11 local import shadowing`
2. `refactor: standardize step11 execution helper names`
3. `fix: use stage11 resume records with legacy fallback`
4. `fix: read step11 history from current saves workspace`
5. `test: cover step11 recovery paths and run state`

如果一次提交，也应在提交信息中明确：

```text
fix: standardize step11 execution recovery state
```

## 九补：代码复查补充（2026-06-29）

> 以下是对本文档所有技术细节的逐项代码核实，记录发现的修正点和额外风险。

### ✓ 总体：文档完全正确，无误判

4 个 bug 的位置、原因、影响均与代码一致。以下是复查中发现的额外细节：

---

### 补充 1：`_previous_records_by_task()` 读取顺序存在优先级 BUG

**当前代码（Line 3841-3861）**：

```python
for path in _stage10_resume_dir().glob("DEV-*_execution.json"):
    result[str(record.get("task_id"))] = record   # ← = 强覆盖

save_index = read_json(BASE_DIR / "save" / "save_index.json", {})
...
result.setdefault(str(record.get("task_id")), record)   # ← setdefault 不覆盖
```

问题：`=` 和 `setdefault` 混用，导致 checkpoint 目录（最后执行）意外具有最高优先级，而正式存档反而被 `setdefault` 保护不会覆盖前者。

**正确优先级**（active draft 是正在执行的事实源，正式 save workspace 可能因 per-group sync 而落后，不能无条件高优）：

```text
1. 当前 active stage_11/DEV-*_execution.json        ← 最高优先
2. 当前 active stage_11_resume_records/
3. saves/<current_save_id>/workspace/stage_11/     ← 正式存档（可能落后于 active）
4. stage_12_resume_records/                        ← legacy checkpoint
5. save/<save_id>/workspace/stage_11/              ← legacy 存档
```

**修复方式**：统一抽为 `_merge_task_records(sources)` 或等价 helper。按优先级从高到低读取，每个 `task_id` 首次命中即确定；如需要处理同一优先级内的冲突，再按 `generated_at` 或文件 mtime 决策。禁止在多个读取循环中混用 `=` 和 `setdefault` 来隐式表达优先级。

---

### 补充 2：`save_manager.current_save_workspace_dir()` 已存在，可直接使用

文档 4.2 节建议新增 `_current_save_stage_dir()`，其中需要调用：

```python
save_manager.current_save_id(BASE_DIR)
save_manager.workspace_dir(BASE_DIR, save_id)
```

但 `core/save/manager.py:529` 已有：

```python
def current_save_workspace_dir(project_root: Path) -> Path | None:
    save_id = current_save_id(project_root)
    if not save_id:
        return None
    ...
```

建议 `_current_save_stage_dir()` 直接调用 `save_manager.current_save_workspace_dir(BASE_DIR)`，不需要两步拆开。

---

### 补充 3：`stage10_soft_stopped` 出现 3 处，文档未完整列出

文档 Phase 5 提到需要修改 `stage10_soft_stopped`，实际代码中出现 3 处：

- Line 4799
- Line 5239
- Line 5408

三处都在 `_stage11_outputs()` 的软停止分支内，全部需要改为 `stage11_soft_stopped`。

---

### 补充 4：4.1 节常量建议无需全部新增

文档建议新增：

```python
DEV_EXECUTION_STAGE_LABEL = "Step 11"
DEV_EXECUTION_STAGE_NAME = "Development Execution"
DEV_EXECUTION_TASK_UNIT_TYPE = "stage11_task"
DEV_EXECUTION_RESUME_DIR_NAME = "stage_11_resume_records"
LEGACY_DEV_EXECUTION_RESUME_DIR_NAMES = ("stage_12_resume_records",)
```

经核查，`DEV_EXECUTION_STAGE = 11` 已在 Line 97 定义。新增 label/name/unit_type 常量是好实践，但如果代码修改量大，也可以内联字面量先完成功能修复，后续重构时再抽常量。不必因常量未抽取而阻塞 Phase 1-4 的修复。

---

### 补充 5：Phase 5 UI 兼容原则（不新增 UI 测试）

经核查 `pipeline_panel.py` 没有对 `unit_type` 字段的任何引用，因此"旧 `stage12_task` UI 不崩溃"没有明确测试对象，强加为测试用例是无效测试。

正确的处理方式：

- **验收**：新 `run_state` 写入 `stage11_task`，确认当前 UI 不读取 `unit_type`（已核查通过）
- **原则**：如未来 UI 新增 `unit_type` 展示，届时加 normalizer 兼容旧 `stage12_task`
- **不需要**：当前为此新增 UI 逻辑或测试

---

### 补充 6：`_stage10_resume_dir()` 路径还有第三个问题

文档已覆盖两个问题：
1. 目录名 `stage_12_resume_records` 错
2. 根目录路径问题（`BASE_DIR / "outputs"` 不是 draft 目录）

补充**第三个问题**：该路径在 `_write_stage10_task_record()` 里还会被 **直接写入**（Line 3821），但当前活动产物应该在 draft 下的 `stage_dir()` 管理范围内，而不是在 `BASE_DIR / "outputs"` 下。

修复时 `_stage11_resume_dir()` 的基础路径固定为 `stage_dir(DEV_EXECUTION_STAGE).parent.parent / "checkpoints" / "stage_11_resume_records"`；不再使用 `BASE_DIR / "outputs" / "checkpoints"`。旧 `stage_12_resume_records` 只作为同一 checkpoint 根下的只读 fallback。

---

### 修复验收补充

在文档八、验收标准基础上，额外增加：

- `_previous_records_by_task()` 按五级优先级合并：active stage > active stage_11 checkpoint > saves workspace > legacy checkpoint > legacy save
- 当前不新增 UI 旧 `stage12_task` 兼容测试；只确认现有 `pipeline_panel.py` 不读取 `unit_type`，未来如新增展示再补 normalizer 和测试
- `stage10_soft_stopped` 在整个 `_stage11_outputs()` 中完全消失（3 处全部替换）

---

## 十、非目标

本计划不处理：

- Step12 Art Production 的资产生成能力增强。
- Step13 对 Step11/12 correction queue 的更深层 UI 复核流程。
- 自动修复策略升级。
- Unity/Codex 外部执行质量优化。
- 历史 `save/` 到 `saves/` 的批量迁移脚本。

这些可以作为后续计划，但不应混进本次 Step11 标准化修复，避免扩大风险。
