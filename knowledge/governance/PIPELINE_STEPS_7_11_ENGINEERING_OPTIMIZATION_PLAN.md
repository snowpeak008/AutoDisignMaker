# 步骤 7-11 工程优化开发计划

## 目标

将步骤 7、8、9、10、11 从“整批大上下文生成/执行”优化为“索引驱动、单文件生成、确定性校验、可恢复 patch”的工程流水线。

核心目标：

- 降低 LLM 上下文超限概率。
- 降低单个计划失败导致整批失败的概率。
- 让每个计划、任务、资产协议都有明确路径绑定。
- 让 patch 模式只修复受影响文件，不重跑整阶段。
- 让执行阶段只按计划与对齐协议落盘，禁止临时发明目录。

## 总体架构

优化后的步骤 7-11 统一采用三层结构：

```text
索引层
→ 单文件计划/协议层
→ 执行状态层
```

索引层负责全局一致性：

- 计划 ID / 任务 ID
- 依赖关系
- 并行组
- 路径绑定
- 资产引用

单文件层负责局部细节：

- 每个 `PLAN-xxx.md`
- 每个 `ART-xxx.md`
- 每个资产对齐记录
- 每个执行报告

执行状态层负责恢复和 patch：

- 已完成项
- 失败项
- 变更文件
- 验证结果
- correction queue 路由

## 当前实现状态

已完成第一轮工程落地：

- 新增 `tools/pipeline_execution.py`，统一索引读写、Markdown 路径字段抽取、执行状态记录。
- 步骤 7 会在现有计划生成后写出 `program_plan_index.md`。
- 步骤 8 会在现有任务生成后写出 `art_plan_index.md`。
- 步骤 9 优先读取 `program_plan_index` / `art_plan_index` 和目录规范；索引不可用时回退读取整目录。
- 步骤 10 支持 `--plan PLAN-001`、`--resume`、`--patch correction_queue.md`，并写入 `DevExecution_* / execution_state.md`。
- 步骤 11 支持 `--task ART-001`、`--resume`、`--patch correction_queue.md`，并写入 `ArtProduction_* / execution_state.md`。

仍待后续完成：

- 步骤 7 尚未把 LLM 调用彻底拆成 `7A 索引生成 + 7B 单计划文件生成 + 7C 派生产物生成`，当前先兼容旧整批计划输出并追加索引。
- 步骤 8 尚未把复用建议、质量门禁和审计完全拆成单任务局部生成，当前先兼容旧整批任务输出并追加索引。
- 步骤 9 尚未实现 alignment patch 的受影响资产局部重算。
- 步骤 10 尚未实现变更文件越界检测和每计划独立 commit 的强制策略。
- 步骤 11 尚未实现 staging 目录和 Python 确定性归档。

## 步骤 7：程序开发计划生成优化

### 当前问题

当前步骤 7 一次性生成完整计划集合和所有计划文件正文，容易出现：

- 输出过长被截断。
- 某个计划格式错误导致整批失败。
- patch 时难以只修复单个计划。
- `target_path` / `output_files` 等路径字段容易遗漏。

### 目标设计

步骤 7 拆为三段：

```text
7A 生成 program_plan_index
7B 逐个生成 PLAN-xxx.md
7C 生成派生产物
```

### 7A：程序计划索引

产物：

```text
Shared/Plans_*/program_plan_index.md
```

索引字段：

```json
{
  "plans": [
    {
      "plan_id": "PLAN-001",
      "title": "玩家状态系统",
      "system_id": "SYS_PLAYER_STATE",
      "level": "T2",
      "dependencies": [],
      "target_path": "Source/Systems/PlayerState/",
      "output_files": [
        "Source/Systems/PlayerState/PlayerStateSystem.cs"
      ],
      "touched_paths": [
        "Source/Systems/PlayerState/"
      ],
      "art_asset_refs": []
    }
  ],
  "parallel_groups": [
    ["PLAN-001", "PLAN-003"]
  ]
}
```

规则：

- `target_path` 必须来自 `program_structure_spec.md`。
- `output_files` 必须落在允许根目录。
- 并行组不得包含互相依赖或触碰同一文件的计划。

### 7B：逐个生成计划文件

Python 按 `program_plan_index` 循环，每次只生成一个计划文件：

```text
Shared/Plans_*/PLAN-001.md
Shared/Plans_*/PLAN-002.md
```

每次传给 LLM 的上下文只包含：

- 当前 plan index 条目。
- 当前系统相关程序需求。
- `program_structure_spec.md` 摘要。
- 必要治理摘要。

### 7C：派生产物

由索引和单计划文件生成：

```text
开发顺序.md
parallel_groups.json
dev_environment.json
build_config.json
config_schema.json
ui_graph.json
```

其中能确定性生成的内容优先由 Python 生成，LLM 只处理需要设计判断的部分。

### 步骤 7 patch 模式

命令：

```bash
python design_to_plan_crew.py --patch Shared/Correction_xxx/correction_queue.md
```

修复范围：

```text
target_stage = progplan | plan | devplan
```

典型 `conflict_type`：

```text
plan_missing
plan_over_split
plan_under_split
dependency_error
parallel_group_conflict
path_binding_missing
path_binding_invalid
output_file_conflict
art_asset_ref_missing
config_schema_error
build_config_error
ui_graph_error
```

patch 行为：

- 复制最新 `Plans_*` 为新版本。
- 只重生成受影响的索引条目、计划文件或派生产物。
- 写入 `changelog.md`。
- 若发现需求缺失，转交步骤 3 patch。

## 步骤 8：美术制作计划生成优化

### 当前问题

当前步骤 8 一次性生成完整美术任务清单，再由 Python 渲染每个任务文件。风险包括：

- 大项目中任务清单过长。
- 单个任务失败影响整体审计。
- patch 难以定位到单个资产或任务。
- 复用建议和质量门禁不易局部更新。

### 目标设计

步骤 8 拆为三段：

```text
8A 生成 art_plan_index
8B 逐个生成 ART-xxx.md
8C 生成复用、质量、审计汇总
```

### 8A：美术任务索引

产物：

```text
Shared/ArtPlans_*/art_plan_index.md
```

索引字段：

```json
{
  "tasks": [
    {
      "task_id": "ART-001",
      "asset_id": "UI_HUD_HEALTH_BAR",
      "category": "ui",
      "level": "T1",
      "mode": "single",
      "dependencies": [],
      "target_path": "Assets/UI/hud/",
      "output_files": [
        "Assets/UI/hud/UI_HUD_HEALTH_BAR.png"
      ],
      "source_files": [
        "ArtSource/UI/UI_HUD_HEALTH_BAR.psd"
      ]
    }
  ]
}
```

规则：

- `target_path` 必须来自 `art_structure_spec.md`。
- `output_files` 必须是运行时可用导出文件。
- `source_files` 必须与 `output_files` 分离。

### 8B：逐个生成美术计划文件

每次只生成一个任务计划：

```text
Shared/ArtPlans_*/ART-001.md
Shared/ArtPlans_*/ART-002.md
```

上下文只包含：

- 当前 task index 条目。
- 对应资产需求。
- `art_structure_spec.md` 摘要。
- VisualDNA / ArtRules 摘要。

### 8C：汇总产物

```text
开发顺序.md
reuse_summary.md
quality_gates.md
audit_report.md
```

复用建议和质量门禁可以按任务局部生成，再汇总。

### 步骤 8 patch 模式

命令：

```bash
python art_plan_crew.py --patch Shared/Correction_xxx/correction_queue.md
```

修复范围：

```text
target_stage = artplan
```

典型 `conflict_type`：

```text
art_task_missing
art_task_duplicate
art_task_over_split
art_task_under_split
asset_path_missing
asset_path_invalid
source_export_mixed
output_file_missing
reuse_plan_error
quality_gate_error
dependency_error
```

patch 行为：

- 复制最新 `ArtPlans_*` 为新版本。
- 只重生成受影响 task 文件、索引条目或汇总文件。
- 如果需要新增 `asset_id` 或改变资产规格，转交步骤 4 patch。

## 步骤 9：资产对齐优化

### 当前问题

当前步骤 9 会递归读取程序计划目录和美术计划目录中的所有文件，然后整体交给 LLM 提取资产。问题是：

- 容易重新引入大上下文。
- 结构化字段本来可以由 Python 确定性读取。
- 缺口分析中很多规则不需要 LLM。
- 人工闸门只是提示，当前不会阻塞后续步骤。

### 目标设计

步骤 9 改为：

```text
9A 读取 program_plan_index 与 art_plan_index
9B Python 确定性生成基础对齐表
9C LLM 处理语义型冲突和策略建议
9D Python 冻结 AlignmentProtocol
```

### 9A：读取索引

输入：

```text
Shared/Plans_*/program_plan_index.md
Shared/ArtPlans_*/art_plan_index.md
Shared/Plans_*/program_structure_spec.md
Shared/ArtPlans_*/art_structure_spec.md
Docs/governance/AlignmentSchema.md
```

### 9B：确定性对齐

Python 直接检查：

- 程序 `art_asset_refs` 是否存在于美术 `asset_id`。
- 每个资产是否有 `target_path`。
- 每个资产是否有 `output_files`。
- `output_files` 是否落在允许目录。
- `frozen_plans` 中的 `plan_id/task_id` 是否存在。

### 9C：语义型策略建议

LLM 只处理：

- `stability_level` 建议。
- `capabilities` 建议。
- 资源驻留策略。
- 变体和依赖关系解释。
- 需要人工决策的冲突说明。

### 9D：输出协议

产物：

```text
Shared/Alignment_*/
├── program_assets.md
├── art_assets.md
├── gap_analysis.md
├── AlignmentProtocol.md
├── dependency_graph.md
├── frozen_plans/
└── changelog.md
```

### 步骤 9 patch 模式

命令：

```bash
python asset_alignment_crew.py --plans Shared/Plans_xxx --artplans Shared/ArtPlans_xxx --patch Shared/Correction_xxx/correction_queue.md
```

修复范围：

```text
target_stage = alignment
```

典型 `conflict_type`：

```text
missing_art_delivery
missing_program_ref
path_binding_missing
path_binding_invalid
asset_type_conflict
capability_conflict
stability_conflict
dependency_graph_error
frozen_plan_missing
```

patch 行为：

- 复制最新 `Alignment_*` 为新版本。
- 只重算受影响 `asset_uid`、`plan_id` 或 `task_id`。
- 如果是计划错误，转交步骤 7/8 patch。
- 如果是需求错误，转交步骤 3/4 patch。

## 步骤 10：程序开发执行优化

### 当前问题

当前步骤 10 仍通过 `开发顺序.md` 调度计划，并把较大的治理文本、计划正文和对齐协议一起塞进执行提示。问题是：

- 执行上下文可能膨胀。
- 状态恢复能力弱。
- 失败粒度不够细。
- 文件变更和计划 `output_files` 缺少强校验。
- 交互式 `input()` 会阻塞自动流水线。

### 目标设计

步骤 10 改为：

```text
10A 执行预检
10B 单计划执行
10C 单计划验证
10D 状态记录
10E Git 提交
```

### 10A：执行预检

读取：

```text
program_plan_index.md
AlignmentProtocol.md
program_structure_spec.md
```

检查：

- 每个 `plan_id` 文件存在。
- `target_path/output_files` 合法。
- 依赖计划已完成或可执行。
- 开发目录存在且可写。

### 10B：单计划执行

每次只加载：

- 一个 `PLAN-xxx.md`。
- 该计划索引条目。
- AlignmentProtocol 中相关资产子集。
- 必要治理摘要。

禁止加载整个计划目录。

### 10C：单计划验证

每个计划执行后检查：

- `output_files` 是否生成或修改。
- 是否越界修改非计划路径。
- 编译是否通过。
- 测试是否通过。
- 代码审查和治理审计是否通过。

### 10D：执行状态

产物：

```text
Shared/DevExecution_*/
├── execution_state.json
├── PLAN-001/
│   ├── prompt.md
│   ├── claude_output.md
│   ├── changed_files.json
│   ├── compile_report.md
│   ├── test_report.md
│   ├── review_report.md
│   └── execution_result.json
└── summary.md
```

### 10E：提交策略

建议每个计划一个 Git commit：

```text
PLAN-001: implement player state system
```

### 步骤 10 patch 模式

命令：

```bash
python dev_supervisor_crew.py --patch Shared/Correction_xxx/correction_queue.md
```

修复范围：

```text
target_stage = devexec
```

典型 `conflict_type`：

```text
compile_error
test_failure
path_violation
missing_output_file
unexpected_file_change
audit_violation
implementation_incomplete
```

patch 行为：

- 读取最新 `DevExecution_*`。
- 只重跑 `affected_plans`。
- 如果是计划错误，转交步骤 7 patch。
- 如果是对齐协议错误，转交步骤 9 patch。

## 步骤 11：美术制作执行优化

### 当前问题

当前步骤 11 通过关键词判断动画/特效，并让 Agent 参与归档路径决策。问题是：

- mode 判断不可靠。
- 工具输出路径与计划 `output_files` 没有强绑定。
- 归档路径不应由 Agent 决定。
- 执行状态不可细粒度恢复。
- AssetGenome 更新字段过少，和 AlignmentProtocol 绑定不足。

### 目标设计

步骤 11 改为：

```text
11A 执行预检
11B 单任务制作
11C staging 生成
11D Python 确定性归档
11E 质量检查与状态记录
```

### 11A：执行预检

读取：

```text
art_plan_index.md
AlignmentProtocol.md
art_structure_spec.md
```

检查：

- 每个 `task_id` 文件存在。
- `target_path/output_files/source_files` 合法。
- 输出目录可写。
- 资产 UID 在对齐协议中存在。

### 11B：单任务制作

每次只加载：

- 一个 `ART-xxx.md`。
- 当前任务索引条目。
- 对应 AlignmentProtocol asset。
- VisualDNA / ArtRules 摘要。

### 11C：staging 生成

生成文件先进入 staging：

```text
Shared/ArtProduction_*/ART-001/staging/
```

根据 `mode` 调用工具：

```text
single       → Image2Generator
spritesheet  → Image2Generator + SpriteSheetSlicer
dynamic/vfx  → SpriteAtlasPacker
```

禁止通过关键词判断类型，必须使用 `art_plan_index.mode`。

### 11D：确定性归档

Python 负责移动文件：

- 从 staging 移动到 `output_files`。
- 校验源文件和导出文件分离。
- 禁止 Agent 自行选择归档目录。

### 11E：执行状态

产物：

```text
Shared/ArtProduction_*/
├── execution_state.json
├── ART-001/
│   ├── prompt.md
│   ├── generation_output.md
│   ├── staging_files.json
│   ├── qa_report.md
│   ├── archive_report.json
│   └── execution_result.json
└── summary.md
```

AssetGenome 更新应至少包含：

```json
{
  "uid": "UI_HUD_HEALTH_BAR",
  "task_id": "ART-001",
  "output_files": [],
  "source_files": [],
  "alignment_protocol_version": "..."
}
```

### 步骤 11 patch 模式

命令：

```bash
python art_production_crew.py --patch Shared/Correction_xxx/correction_queue.md
```

修复范围：

```text
target_stage = artprod
```

典型 `conflict_type`：

```text
generation_failed
qa_failed
missing_output_file
wrong_dimensions
wrong_format
source_export_mixed
path_violation
style_drift
atlas_pack_failed
```

patch 行为：

- 读取最新 `ArtProduction_*`。
- 只重跑 `affected_tasks` 或 `affected_assets`。
- 如果是计划路径错误，转交步骤 8 patch。
- 如果是对齐错误，转交步骤 9 patch。
- 如果是需求规格错误，转交步骤 4 patch。

## Correction Queue 统一路由

建议统一字段：

```json
{
  "item_id": "PLAN_CORR_001",
  "selected": true,
  "target_stage": "progplan",
  "conflict_type": "path_binding_missing",
  "severity": "BLOCK",
  "affected_plans": ["PLAN-003"],
  "affected_tasks": [],
  "affected_assets": [],
  "affected_files": ["PLAN-003.md"],
  "detail": "...",
  "suggested_action": "..."
}
```

路由规则：

| target_stage | 阶段 |
|---|---|
| `progplan` / `plan` / `devplan` | 步骤 7 |
| `artplan` | 步骤 8 |
| `alignment` | 步骤 9 |
| `devexec` | 步骤 10 |
| `artprod` | 步骤 11 |

跨阶段退回规则：

- 需要新增或修改程序需求：退回步骤 3。
- 需要新增或修改美术需求：退回步骤 4。
- 只修改计划拆分、路径、依赖：步骤 7/8 patch。
- 只修改资产映射、协议、依赖图：步骤 9 patch。
- 只修执行结果：步骤 10/11 patch。

## 实施顺序

建议按以下顺序开发：

1. 步骤 7：实现 `program_plan_index` 和逐计划文件生成。
2. 步骤 8：实现 `art_plan_index` 和逐任务文件生成。
3. 步骤 9：改为索引驱动对齐，减少整目录上下文。
4. 步骤 10：实现单计划执行状态、路径变更校验、resume/patch。
5. 步骤 11：实现 staging、确定性归档、单任务状态、resume/patch。
6. 更新 `run_pipeline.py` 让它识别新索引、状态目录和 patch 路由。
7. 更新 `design_desc/08-12` 和 `PIPELINE.md`。

## 验收标准

- 步骤 7/8 不再要求 LLM 一次性输出所有计划正文。
- 步骤 9 不再把所有计划文件全文拼接给 LLM。
- 步骤 10/11 可以只执行单个计划/任务。
- 步骤 10/11 可以从状态文件恢复。
- patch 模式可以只修复受影响计划、任务或资产。
- 任意阶段不得生成 `target_path` / `output_files` 之外的文件。
- 所有新增结构化产物使用 JSON 或 JSON fenced Markdown。
