# Unity 实际项目开发能力实施计划

## 目标

把当前 DevFlow 从“开发计划产物链路”升级为“必须进入真实 Unity 工程执行代码开发”的正式流水线。

第一版只支持 Unity。用户必须先在项目设置中填写实际开发地址和 Unity Editor 地址，并自行创建 Unity 初始工程。DevFlow 不创建或伪造 Unity 工程，只在已存在 Unity 工程内按阶段 7 的开发计划执行 AI 代码开发。

## 不变规则

- 正式流水线必须以实际 Unity 项目开发为目标。
- 正式流水线启动前必须通过实际开发门禁。
- 门禁失败不得进入阶段 0，不得创建存档，不得写入 `gate_log.yaml`。
- 门禁失败允许写诊断报告，但诊断报告不是阶段产物。
- 第一版只支持 Unity。
- 阶段 10 只执行阶段 7 的开发计划，不重新制定计划。
- 阶段 10 不使用确定性模板生成真实项目代码，只允许 AI 修改 Unity C# 文件。
- 阶段 10 不得改写阶段 7 的任务范围。
- 阶段 10 必须按阶段 7 的执行拓扑运行。

## 实施顺序

### 01 项目设置改造

目标：让实际开发路径和 Unity Editor 路径成为用户主动填写项。

改动：

- `development_path` 默认值改为空。
- `editor_path` 默认值改为空。
- GUI 状态栏显示未设置状态。
- 项目设置弹窗允许保存空值。
- “打开实际开发目录”在路径为空时提示未设置。
- “用编辑器打开开发目录”在编辑器或开发路径为空时提示未设置。

验收：

- 新安装或清空设置后，不再自动使用父目录作为实际开发地址。
- 保存空路径不会报错。
- 空路径不能启动正式流水线。

### 02 Unity 门禁校验器

目标：在正式流水线启动前阻断不满足实际开发条件的运行。

新增能力：

- 读取 `project_settings.json`。
- 校验 `development_path` 非空且存在。
- 校验 `editor_path` 非空且存在。
- 校验编辑器疑似 Unity Editor。
- 校验实际开发地址包含 Unity 工程标记：
  - `Assets/`
  - `ProjectSettings/`
  - `Packages/manifest.json`
- 检测非 Unity 项目标记并报告暂不支持。
- 检测项目类型冲突并阻断。

输出：

- `outputs/preflight/actual_development_preflight.json`

门禁失败规则：

- 不进入阶段 0。
- 不创建存档。
- 不写 `gate_log.yaml`。
- GUI 显示阻断原因和修复建议。

验收：

- 未填写路径时，正式运行被阻断。
- 空目录被阻断，并提示用户自行创建 Unity 初始工程。
- 缺少 `Packages/manifest.json` 的目录被阻断。
- 非 Unity 工程被阻断。

### 03 Orchestrator 启动流程接入

目标：正式运行统一经过 Unity 门禁。

改动：

- `orchestrator.py` 在 `ensure_current_save()` 前执行门禁。
- 门禁通过后才允许创建或同步存档。
- 提供仅诊断模式，用于 GUI 检查设置，不启动流水线。
- 保留内部开发测试开关，但默认正式运行必须门禁。

验收：

- 门禁失败时 `save_index.json` 不新增存档。
- 门禁失败时 `outputs/artifacts/stage_00` 不生成。
- 门禁通过后才进入原 00-15 流程。

### 04 阶段 3 程序骨架规范补强

目标：阶段 3 正式定义 Unity 程序目录和落盘边界。

`program_structure_spec.md` 必须包含：

- `Allowed Roots`
  - `Assets/Scripts/`
  - `Assets/Config/`
  - `Assets/Tests/EditMode/`
  - `Assets/Tests/PlayMode/`
  - `Assets/Scenes/`
- `System Path Map`
  - 每个 `system_id` 的 `target_path`
- `Output File Rules`
  - C# 文件与 public 类型同名
  - Runtime 代码放入 `Assets/Scripts/<Module>/`
  - 配置放入 `Assets/Config/`
  - 测试放入 `Assets/Tests/...`
- `Path Binding Contract`
  - 阶段 7 必须绑定 `target_path` 和 `output_files`
  - 阶段 10 只能写入绑定路径

同时生成机器文件：

- `program_structure_spec.json`

验收：

- 每个程序系统都有目标目录。
- 所有目录都在 Unity 允许根目录内。
- 没有系统路径时阶段 3 阻断。

### 05 阶段 4 美术目录规范补强

目标：阶段 4 正式定义 Unity 资产目录和落盘边界。

`art_structure_spec.md` 必须包含：

- `Allowed Roots`
  - `Assets/Art/`
  - `Assets/UI/`
  - `Assets/VFX/`
  - `Assets/Audio/`
  - `Assets/Textures/`
- `Asset Path Map`
  - 每个 `asset_id` 的 `target_path`
  - 每个 `asset_id` 的 `output_files`
- `Source Export Separation`
  - 源文件和 Unity 可用导出文件分离
- `Path Binding Contract`
  - 阶段 8 必须绑定路径
  - 阶段 11 只能写入绑定路径

同时生成机器文件：

- `art_structure_spec.json`

验收：

- 每个资产需求都有目标路径。
- 资产路径不越出 Unity 项目。

### 06 阶段 7 开发计划契约补强

目标：让阶段 7 成为阶段 10 的唯一执行依据。

`program_task_breakdown.json` 必须包含：

```json
{
  "tasks": [
    {
      "task_id": "DEV-001",
      "requirement_id": "REQ-001",
      "phase": "core_playable",
      "target_path": "Assets/Scripts/Core/",
      "output_files": [
        "Assets/Scripts/Core/GameBootstrap.cs"
      ],
      "verification_commands": [],
      "package_changes": [],
      "source_refs": [],
      "acceptance": ""
    }
  ],
  "dependencies": [
    {
      "from": "DEV-001",
      "to": "DEV-002",
      "reason": "DEV-002 requires DEV-001 output."
    }
  ],
  "parallel_groups": [
    ["DEV-003", "DEV-004"]
  ]
}
```

规则：

- `target_path` 必须来自 `program_structure_spec.json`。
- `output_files` 必须落在允许根目录内。
- 并行组内任务不得修改同一文件。
- 包依赖变更必须写入 `package_changes`。
- 阶段 10 不能新增任务、路径或包依赖。

验收：

- 缺少 `target_path` 阻断。
- 缺少 `output_files` 阻断。
- 缺少执行拓扑阻断。
- 路径越界阻断。
- 并行文件冲突阻断。

### 07 阶段 9 资产与路径对齐补强

目标：在实际开发前检查程序路径、美术路径、资产引用和计划路径是否一致。

检查：

- 程序任务引用的资产是否有美术交付路径。
- 程序 `output_files` 是否在允许根目录。
- 美术 `output_files` 是否在允许根目录。
- 同一文件是否被多个并行任务写入。
- 包依赖变更是否只出现在授权任务中。

输出：

- `asset_alignment_matrix.json`
- `path_binding_validation.json`
- `parallel_conflict_report.json`

验收：

- 任何路径越界都阻断。
- 任何并行写同文件都阻断。
- 未绑定资产引用进入缺口报告。

### 08 阶段 10 实际代码开发前置校验

目标：阶段 10 在调用 AI 前做执行阻断检查。

检查：

- Unity 门禁仍然通过。
- 阶段 7 开发计划存在。
- 阶段 7 有执行拓扑。
- 所有任务有 `target_path` 和 `output_files`。
- 所有 `output_files` 在实际开发地址内。
- 所有 `output_files` 在 Unity 允许根目录内。
- AI 只能写 `output_files`。

阻断输出：

- `actual_development_blocked.json`

验收：

- 任何条件不满足时，不调用 AI。
- 不生成成功的 `devexecution.json`。
- 阻断信息指向设置、阶段 3、阶段 7 或阶段 9。

### 09 阶段 10 AI 实际代码开发执行器

目标：按阶段 7 的执行拓扑调用 AI 修改 Unity C# 文件。

执行规则：

- 按 `dependencies` 和 `parallel_groups` 执行。
- 每个任务只允许修改自己的 `output_files`。
- 不允许修改未授权文件。
- 不允许新增需求。
- 不允许重写阶段 7 计划。
- 需要新增包依赖时，必须来自 `package_changes`。

每个任务输出：

- `task_id`
- `status`
- `changed_files`
- `diff_summary`
- `commands`
- `verification_result`
- `blocked_reason`

阶段输出：

- `actual_development_report.json`
- `devexecution.json`
- `changed_files_manifest.json`
- `package_change_report.json`

验收：

- AI 修改文件越界时阶段失败。
- 任务失败时停止后续依赖任务。
- 成功任务可恢复，不重复执行。

### 10 Unity 验证执行

目标：阶段 10 或阶段 12 使用 Unity Editor 进行真实验证。

第一版要求：

- 必须有 Unity Editor 路径。
- 必须能启动 batchmode。
- 至少运行编译检查。
- 如存在 EditMode 测试，则运行 EditMode。
- 如存在 PlayMode 测试，则运行 PlayMode。

命令示例：

```text
Unity.exe -batchmode -quit -projectPath <development_path> -logFile <log_path>
Unity.exe -batchmode -quit -projectPath <development_path> -runTests -testPlatform EditMode -logFile <log_path>
```

输出：

- `unity_compile_report.json`
- `unity_test_report.json`
- `unity_editor_log.txt`

验收：

- 无 Unity Editor 路径时不能执行。
- 编译失败时阶段失败。
- 测试失败时阶段失败或进入修复队列。

### 11 阶段 12 集成验证调整

目标：阶段 12 不再只验证记录，而是验证真实 Unity 开发结果。

检查：

- 阶段 10 是否真实修改文件。
- 阶段 10 是否通过 Unity 编译。
- 阶段 10 是否未越界写文件。
- 阶段 11 美术制作是否与资产引用一致。
- 场景、配置、脚本路径是否存在。

输出：

- `integration_validation_report.json`
- `actual_project_file_audit.json`
- `unity_validation_summary.json`

验收：

- 没有真实文件改动时失败。
- 没有 Unity 验证结果时失败。
- 越界文件改动时失败。

### 12 阶段 13 构建调整

目标：构建阶段面向真实 Unity 项目。

第一版规则：

- 如果阶段 7 定义构建命令，则执行。
- 如果没有构建命令，则至少要求 Unity 编译和测试通过。
- 构建结果必须来自实际开发地址。

输出：

- `build_report.json`
- `build_artifact_manifest.json`
- `unity_build_log.txt`

验收：

- 构建命令失败时失败。
- 构建产物不存在时失败。
- 只生成记录但没有实际验证结果时失败。

### 13 阶段 14 补丁调整

目标：补丁记录真实 Unity 项目改动。

输出：

- `patch_manifest.json`
- `changed_files_manifest.json`
- `rollback_plan.md`

规则：

- 补丁必须列出实际开发地址内的变更文件。
- 回滚方案必须说明如何撤回实际项目改动。
- 不允许只记录流水线文档变化。

验收：

- 没有实际项目文件变更时失败。
- 补丁文件越界时失败。

### 14 GUI 状态与操作调整

目标：让用户清楚看到正式流水线是否可启动。

新增显示：

- 实际开发地址：未设置 / 已设置
- Unity Editor：未设置 / 已设置
- Unity 工程：未检测 / 已检测 / 冲突
- 正式流水线：可启动 / 阻断

新增操作：

- 检查实际开发门禁
- 打开门禁诊断报告
- 打开 Unity 工程
- 用 Unity Editor 打开工程

验收：

- 未设置路径时 GUI 不允许用户误以为可以完整运行。
- 门禁失败原因可直接查看。

### 15 测试策略调整

目标：测试必须覆盖真实 Unity 开发门禁，不保留 plan-only 通过假象。

测试类型：

- 单元测试：路径校验、Unity 标记识别、越界检测、拓扑校验。
- 集成测试：门禁失败不创建存档、不进入阶段 0。
- Unity 工程测试：在用户提供的测试 Unity 工程上跑完整 00-15。

禁止：

- 无 Unity 工程时跑出 `16/16` 成功。
- 用文档产物测试冒充实际开发测试。

## 首版完成标准

第一版完成时必须满足：

- 项目设置默认路径为空。
- 正式流水线启动前执行 Unity 门禁。
- 门禁失败只写诊断报告，不创建存档。
- 阶段 3 产出完整 Unity 程序骨架规范。
- 阶段 7 产出带路径、文件、依赖、并行组的开发计划。
- 阶段 10 调用 AI 修改真实 Unity C# 文件。
- 阶段 10 禁止越界写文件。
- 阶段 10 使用 Unity Editor 验证。
- 阶段 12-14 基于真实 Unity 项目结果验收。
- 没有实际 Unity 项目时不能显示完整通过。

