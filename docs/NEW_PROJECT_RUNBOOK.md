# 新项目启动与运行保姆级教程

本文说明当前 no-agent-runtime 新项目如何启动、运行、验证和排错。

当前项目的唯一正式入口是：

```powershell
python orchestrator.py
```

如果使用图形界面，双击：

```text
DevFlow.exe
```

图形界面仍然调用 `orchestrator.py`，只是把输入、确认、运行、验收放进一个窗口里。详细交互设计见：

```text
Docs/GUI_INTERACTION_DESIGN.md
```

不要再使用旧的 `*_crew.py`、`Shared/`、旧 agent 入口或旧运行时脚本。旧产物如果还要用，必须先作为当前项目自己的输入资料放进 `source_artifacts/`。

图形界面启动时会把当前工作区重置为空结构。真实项目状态保存在 `save/` 目录内；只有在“存档管理”中加载某个存档后，才会把该存档恢复为当前工作区。

## 1. 先理解这个项目在跑什么

这个项目现在跑的是一个确定性的 0-15 阶段流水线。`source_artifacts/` 和 `outputs/` 是当前运行沙盒，`save/<存档ID>/workspace/` 才是存档内的权威项目状态：

```text
source_artifacts/
  -> steps/
      -> outputs/artifacts/stage_XX/
          -> artifact layer review
              -> artifact layer validation
                  -> save/<存档ID>/workspace/
```

它不是直接启动一个游戏客户端，也不是启动旧 CrewAI agent。它做的是：

- 读取当前项目自己的源资料：`source_artifacts/`
- 按阶段导入或生成产物：`outputs/artifacts/stage_00` 到 `outputs/artifacts/stage_15`
- 给每个阶段补齐治理报告：
  - `artifact_index.json`
  - `reference_manifest.json`
  - `validation_report.json`
  - `artifact_layer_manifest.json`
  - `artifact_reviews.json`
  - `artifact_validation_layer.json`
- 最后由 stage 15 做迁移/运行时审计
- 每个保存、提交、运行阶段等事务都会同步到当前存档，并写入 `snapshots/` 与 `timeline.jsonl`

## 2. 第一次打开项目

打开 PowerShell，然后进入项目根目录。

当前目录是：

```powershell
cd <legacy-newdemotower>
```

如果后续你把项目移动到了新目录，就把上面的路径替换成新的项目根目录。

确认你站在项目根目录：

```powershell
Get-ChildItem
```

你应该能看到这些关键文件或目录：

```text
orchestrator.py
run_pipeline.py
requirements.txt
artifact_layer/
steps/
source_artifacts/
outputs/
tools/
knowledge/
design_desc/
```

## 3. 准备 Python 环境

先看 Python 是否可用：

```powershell
python --version
```

如果上面命令不可用，可以试：

```powershell
py -3 --version
```

当前项目主要读写 Markdown、JSON、ZIP 和阶段报告。正常运行项目不会污染全局 Python。

默认可以直接用当前 PowerShell 里的 Python 运行：

```powershell
python orchestrator.py --list
```

成功时会看到 `00` 到 `15` 的阶段清单。

只有在下面情况才建议使用虚拟环境：

- 你需要执行 `python -m pip install -r requirements.txt`
- 你不想让依赖安装到全局 Python
- 你希望多人或多机器复现同一套依赖环境

当前依赖文件是：

```text
requirements.txt
```

如果直接运行时报 `ModuleNotFoundError`，再创建虚拟环境：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果 PowerShell 提示不能执行脚本，先临时放开当前窗口的执行策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

这个设置只影响当前 PowerShell 窗口。

虚拟环境不是必须步骤。它只隔离 Python 依赖，不影响 Codex 是否能运行，也不会降低大模型缓存命中率。Codex 通常是全局命令，建议直接从项目根目录启动：

```powershell
cd <legacy-newdemotower>
codex
```

如果你已经进入虚拟环境，一般也仍然可以运行：

```powershell
codex
```

模型缓存命中率主要取决于提示词和上下文是否稳定，不取决于是否激活 Python venv。为了提升命中率，不要让 Codex 分析 `venv/`、`__pycache__/`、`outputs/` 这类大目录。

准备完成后，先让主入口列出所有阶段：

```powershell
python orchestrator.py --list
```

## 4. 一键跑完整流水线

### 4.1 图形界面方式

双击：

```text
<legacy-newdemotower>\DevFlow.exe
```

推荐操作者按界面流程推进：

```text
查看顶部健康度 -> 选择阶段 -> 阅读推荐动作 -> 填写人工输入 -> 勾选确认项 -> 保存草稿或提交到源资料库 -> 运行阶段 -> 查看产物验收
```

界面内可以执行：

```text
运行全部 0-15
运行选中步骤
运行选中范围
当前运行验收
打开运行产物
打开人工源资料
保存草稿
提交并运行本阶段
```

界面按钮使用中文表现，内部仍映射到 `orchestrator.py`、`outputs/` 和 `source_artifacts/`。

新版界面会显示每个阶段的处理状态：

```text
已运行通过
缺源资料
待运行
需处理
```

切换阶段时会自动载入该阶段草稿，并显示输入字数和确认进度。

### 4.2 命令行方式

最常用命令是：

```powershell
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
```

含义：

- `--from-step 0`：从第 0 阶段开始
- `--stop-step 15`：跑到第 15 阶段结束
- `--auto-approve`：自动通过每个阶段的人工确认门

成功时，每个阶段会打印类似结构：

```json
{
  "step": 0,
  "status": "success",
  "artifact_review": "success",
  "artifact_validation": "success",
  "artifacts_dir": "<legacy-newdemotower>\\outputs\\artifacts\\stage_00"
}
```

完整成功的判断标准：

- stage 00 到 stage 15 都出现 `status: success`
- 每个阶段都出现 `artifact_review: success`
- 每个阶段都出现 `artifact_validation: success`
- 命令最后退出，没有 `Step XX failed`

注意：每次运行某个阶段时，对应的 `outputs/artifacts/stage_XX/` 会被重建。`gate_log.yaml` 和 `outputs/checkpoints/` 会持续记录运行历史。

## 5. 不自动批准，手动逐步确认

如果你想每一步都手动确认，去掉 `--auto-approve`：

```powershell
python orchestrator.py --from-step 0 --stop-step 15
```

每个阶段都会问：

```text
Run step 00 (idea_intake)? [y/N]
```

输入：

```text
y
```

然后回车，才会继续跑该阶段。

如果直接回车或输入 `n`，当前阶段会停止。

## 6. 只跑某一个阶段

例如只跑 stage 3：

```powershell
python orchestrator.py --from-step 3 --stop-step 3 --auto-approve
```

常用单步命令：

```powershell
python orchestrator.py --from-step 0 --stop-step 0 --auto-approve
python orchestrator.py --from-step 1 --stop-step 1 --auto-approve
python orchestrator.py --from-step 2 --stop-step 2 --auto-approve
python orchestrator.py --from-step 3 --stop-step 3 --auto-approve
python orchestrator.py --from-step 15 --stop-step 15 --auto-approve
```

注意：单跑中后段时，上游阶段必须已经成功跑过，并且上游的 `artifact_validation_layer.json` 必须是 `success`。如果报依赖错误，先跑前置阶段或直接跑完整流水线。

## 7. 只跑一个范围

例如从 stage 7 跑到 stage 12：

```powershell
python orchestrator.py --from-step 7 --stop-step 12 --auto-approve
```

这适合在前面阶段已经成功、只想刷新中间阶段时使用。

依赖规则仍然生效。比如 stage 12 依赖 stage 10 和 stage 11，如果它们没有成功验证，stage 12 会在 preflight 阶段失败。

## 8. 兼容入口 run_pipeline.py

当前仍保留了一个兼容命令：

```powershell
python run_pipeline.py --list
```

只跑一个阶段：

```powershell
python run_pipeline.py --step 3 --auto-approve
```

跑一个范围：

```powershell
python run_pipeline.py --from-step 3 --to-step 5 --auto-approve
```

但日常建议优先使用：

```powershell
python orchestrator.py
```

原因是 `orchestrator.py` 是当前项目的正式统一入口。

## 9. 直接运行 step 模块

如果调试某个 step，也可以这样：

```powershell
python -m steps.step3_program_requirements
```

这个命令不会绕过治理层。它会自动转回 orchestrator，只跑对应阶段，并补齐 artifact review 和 artifact validation。

日常使用时仍建议写成：

```powershell
python orchestrator.py --from-step 3 --stop-step 3 --auto-approve
```

## 10. 跑完以后看哪里

所有阶段产物在：

```text
outputs/artifacts/
```

例如 stage 3：

```text
outputs/artifacts/stage_03/
```

每个普通阶段通常会有：

```text
README.md
artifact_index.json
reference_manifest.json
validation_report.json
artifact_layer_manifest.json
artifact_reviews.json
artifact_validation_layer.json
guidance/
imported/
upstream/
```

如果某个阶段当前没有源资料，会看到：

```text
MISSING_SOURCE_ARTIFACTS.md
```

这不是运行崩溃。它表示该阶段没有匹配到 `source_artifacts/` 里的输入资料，所以当前只生成了缺失声明和治理报告。

`reference_manifest.json` 是下游阶段读取上游产物的机器清单。它记录本阶段文件、人工源资料映射、上游文件引用、文件哈希和 artifact 依赖关系。`upstream/` 目录只保存 `UPSTREAM_REFERENCE.json` 引用记录，不复制上游阶段的整包文件。

最终审计在：

```text
outputs/artifacts/stage_15/migration_audit.json
outputs/artifacts/stage_15/migration_audit.md
```

运行检查点在：

```text
outputs/checkpoints/
```

全局依赖图在：

```text
artifact_layer/dependency_graph.json
outputs/dependency_graph.json
```

每次 preflight 结果在：

```text
outputs/artifact_layer/preflight_stage_XX.json
```

每次 gate 记录在：

```text
gate_log.yaml
```

## 11. 跑完后的验证命令

完整跑完后，做一次 Python 编译检查：

```powershell
python -m compileall orchestrator.py steps tools problem_resolver.py run_pipeline.py
```

编译通过后，再在界面中查看“当前运行验收”。

## 12. 当前 0-15 阶段说明

查看阶段列表：

```powershell
python orchestrator.py --list
```

阶段含义：

```text
00 idea_intake              初始想法导入
01 demo                     玩法框架导入
02 design_review            设计评审和冻结导入
03 program_requirements     程序需求导入
04 art_requirements         美术需求导入
05 program_review           程序需求评审导入
06 art_review               美术需求评审导入
07 design_to_plan           程序计划导入
08 art_plan                 美术计划导入
09 asset_alignment          资产对齐导入
10 dev_execution            程序开发执行导入
11 art_production           美术制作执行导入
12 integration_validation   集成验证导入
13 build_package            构建打包导入
14 delta_patch              差量补丁导入
15 migration_audit          迁移和运行时审计
```

当前项目已经有较完整源资料的阶段主要是 0-3。4-14 如果没有对应源资料，仍会成功生成缺失声明和治理报告，但不能把它当作真实业务内容已经完成。

## 13. 如何补充源资料

源资料只放在：

```text
source_artifacts/
```

不要再放到旧的 `Shared/`。

当前各阶段优先按源资料包内的稳定 ID 匹配源资料。目录名只是展示名，可以改短；只要包内 `package_manifest.json` 保留，阶段关系不会断。

每个源资料包建议包含：

```text
package_manifest.json
operator_submission.json
```

`package_manifest.json` 的关键字段：

```json
{
  "project": "程序自动开发流程工具",
  "project_id": "devflow",
  "package_id": "source:Concept",
  "package_type": "Concept",
  "source_id": "Concept",
  "source_ids": ["Concept"]
}
```

阶段需要的 source ID：

```text
stage 00: Concept
stage 01: GameplayFramework
stage 02: SubsystemDesign, AIDesignScript, Design, DevelopmentDesign
stage 03: ProgReq
stage 04: ArtReq
stage 05: ProgReview
stage 06: ArtReview
stage 07: Plans
stage 08: ArtPlans
stage 09: Alignment
stage 10: DevExecution
stage 11: ArtProduction
stage 12: Integration
stage 13: Build
stage 14: DeltaPatch
```

如果旧资料没有 `package_manifest.json`，系统会尝试从 `operator_submission.json`、标记文件和旧目录名推断，并在同步存档时补齐 manifest。目录名匹配只作为旧资料兼容兜底。

补完资料后，重新跑对应阶段。例如补了 stage 4 的美术需求：

```powershell
python orchestrator.py --from-step 4 --stop-step 4 --auto-approve
```

如果后续阶段依赖它，再从该阶段往后跑：

```powershell
python orchestrator.py --from-step 4 --stop-step 15 --auto-approve
```

## 14. 常见错误和处理

### 14.1 ModuleNotFoundError

常见原因是当前 Python 没装依赖。

先确认你在项目根目录：

```powershell
cd <legacy-newdemotower>
python --version
```

如果你愿意把依赖装到当前 Python：

```powershell
python -m pip install -r requirements.txt
```

如果你想隔离依赖，再使用虚拟环境：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 14.2 PowerShell 不允许激活 venv

处理：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

这个设置只影响当前 PowerShell 窗口。

### 14.3 Step XX was not approved

说明你没有使用 `--auto-approve`，并且在人工确认时没有输入 `y`。

处理：

```powershell
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
```

或者手动输入：

```text
y
```

### 14.4 Artifact preflight failed

常见原因：

- 上游阶段没跑
- 上游 `artifact_validation_layer.json` 不是 `success`
- `artifact_layer/registry.json` 里依赖关系有问题
- `knowledge/` 里缺少 registry 引用的知识文件

处理顺序：

```powershell
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
```

如果仍失败，看：

```text
outputs/artifact_layer/preflight_stage_XX.json
```

### 14.5 出现 MISSING_SOURCE_ARTIFACTS.md

这表示对应阶段没有匹配到源资料。

处理：

- 如果这个阶段本来就没有真实资料，可以接受这个结果。
- 如果你有真实资料，把目录放进 `source_artifacts/`，并保证目录名符合第 13 节的匹配规则。
- 然后重新跑对应阶段。

## 15. 日常开发推荐流程

每天开始前：

```powershell
cd <legacy-newdemotower>
python orchestrator.py --list
```

改了 step、artifact layer、knowledge 或 source artifact 后：

```powershell
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
python -m compileall orchestrator.py steps tools problem_resolver.py run_pipeline.py
```

只改了某一个阶段的源资料时：

```powershell
python orchestrator.py --from-step X --stop-step X --auto-approve
```

把 `X` 替换成阶段号，例如：

```powershell
python orchestrator.py --from-step 3 --stop-step 3 --auto-approve
```

如果单阶段后面还有依赖它的阶段，建议从该阶段跑到 15：

```powershell
python orchestrator.py --from-step X --stop-step 15 --auto-approve
```

## 16. 新项目的禁止事项

不要做这些事：

- 不要恢复旧 `*_crew.py` 作为运行入口
- 不要从 `Shared/` 读取当前项目资料
- 不要把旧 agent runtime 重新加回 Python 运行时代码
- 不要绕过 `orchestrator.py` 直接手写 outputs
- 不要删除 `artifact_layer/registry.json`
- 不要删除 `knowledge/` 中被 registry 引用的文件
- 不要把 `MISSING_SOURCE_ARTIFACTS.md` 当作真实业务完成内容

## 17. 最短可复制启动命令

如果环境已经准备好，直接复制下面几行即可：

```powershell
cd <legacy-newdemotower>
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
```

如果还想做编译检查，再运行：

```powershell
python -m compileall orchestrator.py steps tools problem_resolver.py run_pipeline.py
```

看到下面两个结果，说明当前项目启动和运行状态正常：

```text
"reports": 16
"failures": []
```

```text
no forbidden external agent runtime references found
```



