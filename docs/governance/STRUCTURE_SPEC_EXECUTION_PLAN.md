# 目录规范绑定执行计划

## 目标

把目录结构从执行阶段的临时决定，前移为需求阶段的正式产物，并让后续计划、对齐和执行阶段只能绑定这些路径。

## 执行范围

1. 步骤 3 程序需求生成产出 `program_structure_spec.md`。
2. 步骤 4 美术需求生成产出 `art_structure_spec.md`。
3. 步骤 7 程序计划必须写明 `target_path` 与 `output_files`。
4. 步骤 8 美术计划必须写明 `target_path` 与 `output_files`。
5. 步骤 9 资产对齐检查计划路径是否符合目录规范，并检查程序资产引用是否有美术交付路径。
6. 步骤 10/11 执行阶段只允许按计划路径落盘，禁止临时发明目录。

## 产物契约

### program_structure_spec.md

程序目录规范必须包含：

- `Allowed Roots`：允许的程序、配置、测试、工具、文档根目录。
- `System Path Map`：每个 `system_id` 对应的 `target_path`。
- `Output File Rules`：源代码、配置、测试和生成文件命名规则。
- `Path Binding Contract`：后续计划必须绑定本规范路径。

### art_structure_spec.md

美术目录规范必须包含：

- `Allowed Roots`：允许的美术源文件、导出资源、UI、VFX、图集根目录。
- `Asset Path Map`：每个 `asset_id` 对应的 `target_path`、`output_files` 和源文件位置。
- `Source Export Separation`：源文件与引擎可用导出文件必须分离。
- `Path Binding Contract`：后续美术计划必须绑定本规范路径。

## 执行顺序

1. 在需求生成脚本中写出目录规范文件。
2. 在计划生成脚本中加载目录规范，并要求计划绑定路径字段。
3. 在计划落盘时复制目录规范到对应计划目录，方便步骤 9 只读计划输入即可校验。
4. 在资产对齐脚本中把路径合规性纳入缺口分析。
5. 在程序和美术执行脚本中把路径绑定规则注入执行提示。
6. 运行 Python 语法检查，确认脚本可解析。

## 非目标

- 不在步骤 2 预设 Unity、Godot 或任意固定项目结构。
- 不在执行阶段自动重排目录。
- 不回滚现有未提交修改。
