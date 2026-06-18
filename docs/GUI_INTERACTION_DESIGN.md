# 程序自动开发流程工具交互设计

本文描述 `DevFlow.exe` 的人机协作设计。界面以中文作为操作者表现层，英文命令、目录前缀、JSON 字段只作为内部映射和程序执行依据保留。

## 设计目标

这个程序不是命令启动器，而是 0-15 阶段的人机协作工作台。

目标是让操作者在界面中完成：

- 输入玩法想法或导入文档。
- 逐步确认玩法框架、设计冻结、程序需求、美术需求、评审、计划、执行、验证、构建、补丁和最终审计。
- 把人工确认后的内容写入 `source_artifacts/`。
- 调用正式入口 `orchestrator.py` 运行阶段。
- 查看每个阶段的产物、缺失项、产物复核、产物层校验和最终审计。

## 运行入口

双击：

```text
DevFlow.exe
```

程序位于：

```text
<legacy-newdemotower>\DevFlow.exe
```

GUI 调用的正式流水线入口仍然是：

```text
orchestrator.py
```

GUI 不调用旧 `*_crew.py`，不读取 `Shared/`。

## 主界面结构

```text
顶部工具栏
  项目健康度：通过、缺源资料、待运行、需处理、源资料数量
  分组操作：阶段运行 / 检查验收 / 打开目录

左侧阶段列表
  00-15 阶段、处理状态、阶段校验、源资料数量、缺失项数量
  处理状态包括：已通过、缺源资料、待运行、需处理

右侧当前阶段摘要
  当前阶段、处理状态、阶段校验、源资料、缺失数量、推荐下一步动作

右侧阶段概览
  当前阶段目标、操作者动作、必须确认的问题、源资料匹配规则、会生成的人工源资料包、当前阶段摘要

右侧人工输入
  草稿状态、输入字数、确认进度、确认清单、人工说明、文档附件、保存草稿、提交到源资料库、提交并运行

右侧产物验收
  产物校验、产物复核、产物层校验、工作台运行证明、导入源、缺失组、候选源资料、当前运行验收摘要

运行日志
  实时显示 orchestrator 输出
  标题、成功、失败输出做基础颜色区分
```

## 中文表现和内部映射

界面不直接把内部英文键当作操作者选项展示。代码中保留以下映射层：

```text
success -> 通过
failed -> 失败
missing -> 未生成
Concept -> 初始玩法资料包
GameplayFramework -> 玩法框架资料包
ProgReq -> 程序需求资料包
ArtReq -> 美术需求资料包
DevExecution -> 程序执行记录资料包
DeltaPatch -> 差量补丁资料包
```

内部英文仍会出现在目录名、命令名、JSON 字段和原始运行日志中，因为这些内容是流水线匹配、验证和自动化执行的稳定接口。

## 工作流

每个阶段按这个顺序推进：

```text
1. 选择阶段
2. 阅读阶段说明
3. 填写人工输入或添加文档附件
4. 勾选确认项
5. 必要时点击“保存草稿”
6. 点击“提交本阶段人工输入到源资料库”
7. 点击“运行选中步骤”或“提交并运行本阶段”
8. 运行成功后查看产物验收
9. 如果有缺失或失败，修改输入后再次提交和运行
10. 验收通过后进入下一阶段
```

## 阶段交互要求

源资料关系以包内稳定 ID 为准，目录名只用于展示和人工辨认。新生成的资料包会写入 `package_manifest.json`，其中 `source_id` 是阶段读取契约；目录可以改短或改名。

| 阶段 | 操作者输入 | 生成源资料 ID |
|---|---|---|
| 00 初始想法输入 | 玩法文字或设计文档、核心目标、核心循环、保留限制 | `Concept` |
| 01 玩法框架确认 | 核心循环、系统边界、子系统队列 | `GameplayFramework` |
| 02 设计评审冻结 | 子系统确认、AI 理解脚本、冻结设计、开发系统设计 | `SubsystemDesign`、`AIDesignScript`、`Design`、`DevelopmentDesign` |
| 03 程序需求确认 | 系统、实体、契约、验收标准 | `ProgReq` |
| 04 美术需求确认 | 原画、UI、特效、资产规格、风格限制 | `ArtReq` |
| 05 程序需求评审 | 阻断项、警告项、通过/失败结论 | `ProgReview` |
| 06 美术需求评审 | 风格漂移、规格缺口、通过/失败结论 | `ArtReview` |
| 07 程序开发计划 | 开发任务、依赖、目标文件、验收方式 | `Plans` |
| 08 美术制作计划 | 资产任务、优先级、规格、复用策略 | `ArtPlans` |
| 09 资产契约对齐 | 程序引用、美术输出、冲突裁决 | `Alignment` |
| 10 程序开发执行 | 完成模块、失败项、编译和审查结论 | `DevExecution` |
| 11 美术制作执行 | 完成资产、质量问题、风格偏差 | `ArtProduction` |
| 12 集成验证 | 集成通过项、失败项、回退策略 | `Integration` |
| 13 构建打包 | 版本、平台、构建产物、运行检查 | `Build` |
| 14 差量补丁 | 补丁内容、哈希、回滚和发布说明 | `DeltaPatch` |
| 15 最终审计 | 全流程审计确认 | `source_artifacts/operator_reviews/stage_15_*` |

## 验收规则

每个阶段运行后必须满足：

```text
validation_report.json: status=success, valid=true
artifact_reviews.json: status=success
artifact_validation_layer.json: status=success
artifact_layer_manifest.json: artifacts/tasks 非空
stage 00-14: artifact_index.json 和 reference_manifest.json 存在
stage 15: migration_audit.json 存在
all stages: reference_manifest.json 存在
missing_groups 为空
```

界面中的“当前运行验收”会汇总这些条件，并额外要求存在本工作台成功运行日志；迁移或导入产物只能显示为“导入待运行”。

## 打包方式

开发者可以重新打包：

```powershell
cd <legacy-newdemotower>
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

构建脚本会把 PyInstaller 安装到项目内的 `.build_tools/`，避免安装到全局 Python。

最终 exe：

```text
DevFlow.exe
```


