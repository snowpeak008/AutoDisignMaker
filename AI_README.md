# AutoDesignMaker — AI 项目导读

> 本文件是所有 AI 助手的**通用入口**。  
> 无论你是 Claude / Codex / DeepSeek / 豆包 / 任何 AI，请先读完本文件。

---

## AI 会话记忆

> **本项目有持久化记忆系统。进入项目前请先读取记忆索引：**  
> **📖 `knowledge/ai_memory/INDEX.md`**
>
> 索引文件描述了上次会话的状态、哪些文件已被理解、代码惯例摘要。  
> 有效的缓存文件可以跳过重新阅读，直接使用记忆中的理解。
>
> **每次会话结束时**，请更新 `knowledge/ai_memory/session_history/` 中的记录，  
> 并运行 `python tools/memory/update_freshness.py` 更新文件哈希缓存。

---

## 一、项目是什么

AutoDesignMaker 是一个**游戏设计文档自动生成流水线**。  
输入：游戏创意包（source_artifacts/）  
输出：经过18个阶段（Step00-17）逐步加工的完整游戏设计文档集
启动：双击 `AutoDesignMaker.exe` 或运行 `python gui_app.py`

---

## 二、根目录文件说明

| 文件 | 作用 |
|------|------|
| `AutoDesignMaker.exe` | 启动器，双击启动GUI，不含依赖 |
| `gui_app.py` | 3行Python包装器，`python gui_app.py` 入口 |
| `requirements.txt` | Python依赖清单，`pip install -r requirements.txt` |
| `.project_root` | 路径标记文件（空），`core/paths.py` 靠它定位项目根 |
| `README.md` | 用户说明文档 |
| `AI_README.md` | 本文件，AI通用项目导读 |
| `CLAUDE.md` | Claude Code 专属入口，引用本文件 |
| `AGENTS.md` | Codex CLI 专属入口，引用本文件 |

---

## 三、目录结构全览

```
AutoDesignMaker/
├── core/               【运行时骨架】全部运行时 Python 代码
├── pipeline/           【步骤插件】20个设计/开发阶段插件
├── knowledge/          【知识库】设计数据、规则、skill、schema、AI记忆
├── settings/           【配置】API密钥、应用配置
├── tools/              【维护工具】非运行时的辅助脚本
├── ucos/               【设计AI记忆】已迁移至 knowledge/ucos/
├── artifact_layer/     【制品注册表】已迁移至 pipeline/artifact_layer/
├── _archive/           【历史档案】旧文档和参考资料
├── sandbox/            【运行沙盒】gitignore，运行时动态生成
├── saves/              【存档】gitignore，运行时生成
└── logs/               【日志】gitignore，运行时生成
```

---

## 四、core/ 内部结构详解

```
core/
├── main.py             唯一程序入口，整合编排器+CLI
├── paths.py            所有路径常量，基于.project_root定位
├── registry.py         步骤注册表(STEP_SPECS)，合并自pipeline_registry
├── io.py               文件工具：read_json/write_json/file_manifest
├── stage.py            阶段工具：stage_dir/reset_stage/gate_log
├── stage_plugin.py     StagePlugin 抽象基类（所有步骤必须实现）
├── context.py          StageContext/StageResult 数据结构
├── plugin_manager.py   读取 pipeline/_registry.json 加载插件
│
├── source/             源包系统（从 steps/common.py 拆出）
│   ├── groups.py       SourceGroup数据类 + SOURCE_TYPES/MARKERS
│   ├── finder.py       find_sources() 源包发现
│   └── importer.py     run_import_step() 导入引擎 + forbidden_runtime_matches
│   ├── folder_manager.py  源包文件夹版本管理
│   └── snapshot.py     源包快照系统
│
├── adapters/           AI适配器（通用接口，可替换模型）
│   ├── base.py         ModelAdapter/ModelTask/ModelResult 接口
│   ├── codex/          Codex CLI包装（executor/task_builder/file_guard/result_parser）
│   ├── codex_adapter.py    CodexAdapter
│   ├── openai_adapter.py   OpenAI兼容适配器
│   ├── local_adapter.py    本地模型占位
│   ├── claude_code_adapter.py  Claude Code CLI适配器
│   ├── registry.py     get_adapter(name) 工厂函数
│   └── memory/         ucos记忆注入门面（context_builder/token_budget）
│
├── artifact/           制品审查与验证系统
│   ├── registry_loader.py  load_registry()/artifacts_by_id()
│   ├── graph.py        依赖图构建 + topological_step_order()
│   ├── preflight.py    preflight_stage_contract() 步骤前预检
│   ├── reviewer.py     run_review_pipeline() 4个reviewer
│   ├── validator.py    run_artifact_validators() 7个validator
│   └── manifest.py     制品清单工具
│
├── engines/            业务引擎
│   ├── generation.py   内容生成主引擎（原development_plan_artifacts.py）
│   ├── delta_patch.py  增量补丁生成器
│   ├── handoff_loader.py  设计交接契约加载
│   └── execution_objects/  执行对象状态机
│       ├── workflow.py     状态机：draft→submitted→approved→verified
│       ├── integration.py  与流水线制品对接
│       ├── paths.py        执行对象存储路径
│       └── correction_queue.py  修正队列
│
├── save/               存档引擎
│   └── manager.py      ensure_current_save/retry_sync/快照
│
├── runtime/            运行时控制
│   ├── control.py      stop/resume信号 + PipelineStopRequested
│   ├── guard.py        forbidden_runtime_matches 安全守卫
│   ├── preflight.py    Unity项目路径预检
│   └── pipeline_state.py  流水线步骤状态读写
│
├── config/             配置加载
│   ├── ai_config.py    统一 AI API 三分类配置入口（settings/ai_config.json）
│   ├── ai_config_schema.py  AI 配置 v3 数据结构与兼容转换
│   ├── validator.py    AI 配置验证与 CLI 可用性检测
│   ├── loader.py       load_config()/get_pipeline_adapter()/get_api_config兼容层
│   └── integrity.py    启动时数据完整性检查与 AI 配置迁移
│
├── design/             设计引擎（原design_tool/）
│   ├── engine.py       DesignEngine 领域/节点/玩法系统
│   ├── data_loader.py  加载knowledge/design_data/
│   ├── ai_*.py         AI访谈/映射/提示词/摘要等辅助模块
│   └── export_adapter.py  导出DevFlow概念包
│
├── ui/                 GUI代码
│   ├── gui_app.py      完整GUI入口（tkinter）
│   ├── main_window.py  完整GUI壳：顶部切换 + 底部 AI/进度状态栏
│   ├── app_window.py   设计工作台 CommercialDesignApp
│   ├── pipeline_panel.py  Step00-17 开发流水线面板
│   ├── ai_config_unified_dialog.py  统一 AI Profile 配置弹窗
│   ├── ai_interview_window.py  AI访谈窗口
│   ├── embedded_interview.py  设计工作台内嵌访谈面板
│   ├── theme.py        主题配色
│   └── workbench.py    旧桌面工作台辅助工具，当前无主入口引用，删除前需二次审计
│
├── utils/              通用工具（无业务依赖）
│   ├── base_tool.py    BaseTool基类
│   ├── process_utils.py  subprocess工具（Windows隐藏窗口）
│   ├── structured_md.py  Markdown结构化数据读写
│   ├── yaml_compat.py  PyYAML兼容层
│   ├── md_parser.py    LLM输出Markdown解析器
│   └── text_extractor.py  UI文本提取
│
└── tests/              核心代码测试
    ├── unit/           单元测试
    └── integration/    集成测试
```

---

## 五、pipeline/ 内部结构详解

```
pipeline/
├── _registry.json      步骤注册表，声明20个插件（替代硬编码STEP_MODULES）
├── _design_base.py     D1-D4设计阶段基类 DesignStagePlugin
├── README.md           步骤总览
│
├── step_d1_project_portrait/   D1 设计前置：项目画像
├── step_d2_design_decisions/   D2 设计决策
├── step_d3_design_validation/  D3 设计验证
├── step_d4_devflow_handoff/    D4 DevFlow交接
│
├── step_00_idea_intake/        步骤00：创意收集
├── step_01_gameplay_framework/ 步骤01：玩法框架
├── step_02_design_review_freeze/  步骤02：设计冻结
├── step_03_program_requirements/  步骤03：程序需求
├── step_04_art_requirements/   步骤04：美术需求
├── step_05_program_review/     步骤05：程序评审
├── step_06_art_review/         步骤06：美术评审
├── step_07_art_style_generation/   步骤07：美术风格生成
├── step_08_art_style_confirmation/ 步骤08：美术风格确认
├── step_09_design_to_plan/     步骤09：开发计划
├── step_10_art_plan/           步骤10：美术计划
├── step_11_asset_alignment/    步骤11：资源对齐
├── step_12_dev_execution/      步骤12：程序执行记录
├── step_13_art_production/     步骤13：美术生产记录
├── step_14_integration_validation/ 步骤14：集成验证
├── step_15_build_package/      步骤15：构建打包
├── step_16_delta_patch/        步骤16：增量补丁
└── step_17_migration_audit/    步骤17：迁移审计

每个步骤目录包含：
  plugin.py     实现 StagePlugin.execute()
  prompts/      main.txt  AI提示词
  README.md     步骤设计说明
```

---

## 六、knowledge/ 内部结构

```
knowledge/
├── Core_Rules.md           核心设计规则（artifact_layer引用）
├── Design_Decisions.md     架构决策记录
├── Frozen_Contracts.md     冻结契约
├── Naming_Convention.md    命名规范
├── Runtime_Standards.md    运行时标准
├── README.md               知识库说明
├── decisions/              单项决策文档
│
├── ai_memory/              【AI记忆系统】持久化跨会话记忆
│   ├── INDEX.md            记忆总索引（每次进入项目必读）
│   ├── project_understanding/  项目架构理解缓存
│   ├── code_conventions/   代码惯例和反模式
│   ├── session_history/    历次会话记录
│   └── decisions/          架构决策和待解决问题
│
├── design_data/            设计引擎静态数据（原data/design/）
│   ├── domains/            游戏设计领域JSON（17个领域）
│   ├── entity_schemas/     实体结构定义
│   ├── framework_memory/   框架记忆
│   ├── project_templates/  游戏模板（50+个参考游戏）
│   ├── prompt_framework/   提示词框架模块
│   └── prompt_evaluation/  提示词评估报告
│
├── schemas/                JSON Schema定义
│   ├── execution_object_workflow.schema.json
│   ├── design_domains.schema.json
│   └── ...（共10个schema文件）
│
├── skills/                 Skill库（双层）
│   ├── pipeline/           步骤执行时AI可调用的skill
│   └── dev/                开发脚手架skill
│
└── governance/             治理规范
    ├── AI_COLLABORATION.md
    ├── CODE_NAMING_CONVENTION.md
    └── ...（25个规范文档）
```

---

## 七、settings/ 内部结构

```
settings/
├── app.toml                应用/UI/插件/门控配置（git提交，不含AI密钥）
├── ai_config.example.json  AI配置模板（git提交，不含真实密钥）
├── ai_config.json          统一AI配置：Profile + Adapter + LLM/Image（gitignore！勿提交）
├── project_settings.json   项目路径等本地设置（gitignore！勿提交）
├── api_config.toml         旧版API配置，仅用于自动迁移兼容（gitignore！勿提交）
└── local.toml              本地覆盖（gitignore！勿提交）
```

---

## 八、tools/ 内部结构

```
tools/
├── validators/     独立验证工具（contract/compile/environment/output）
├── asset_production/ 媒体制作工具（图片/音频/精灵/本地化）
├── dev/            开发辅助（scaffold/generators/git）
├── scripts/        维护脚本（inspect_reports/export/migrate）
├── memory/         AI记忆系统维护工具
│   ├── update_freshness.py   更新文件哈希缓存
│   └── check_staleness.py    检查缓存是否过时
└── build/          构建工具
    ├── AutoDesignMaker.spec  PyInstaller规格
    ├── DevFlow.spec
    └── build.py / verify_build.py
```

---

## 九、项目总分总设计框架

### 总：项目定位

AutoDesignMaker 是一个**Step00-17 确定性游戏设计文档流水线**。AI辅助内容生成，人类在关键节点决策。所有步骤都是可复现的确定性操作，不依赖随机性。

### 分：八层职责分工

| 层 | 目录 | 职责 | 可修改？ |
|----|------|------|---------|
| 步骤插件层 | `pipeline/` | 每个阶段的业务逻辑 | 主要修改区 |
| 运行骨架层 | `core/` | 编排、适配器、工具 | 谨慎修改 |
| 知识层 | `knowledge/` | 规则、数据、schema、AI记忆 | 内容更新 |
| 配置层 | `settings/` | 本地配置、API密钥 | 本地修改 |
| 工具层 | `tools/` | 维护、构建、脚本 | 按需添加 |
| 认知层 | `knowledge/ucos/` | 游戏设计会话AI记忆（仅episodic/turns） | 不添加 |
| 注册表层 | `pipeline/artifact_layer/` | 制品依赖声明 | 随步骤更新 |
| 沙盒层 | `sandbox/saves/logs/` | 运行时输出 | 程序自动管理 |

### 总：核心设计原则

1. **步骤自治** — 每个 `pipeline/step_*/` 包含执行所需的一切（代码+提示词+说明）
2. **接口统一** — 所有步骤实现 `StagePlugin`，返回 `StageResult`，无例外
3. **路径单一来源** — 所有路径常量来自 `core/paths.py`，禁止在其他文件硬编码路径
4. **AI可插拔** — 通过 `core/adapters/` 切换模型，步骤代码不感知具体模型
5. **沙盒隔离** — 运行时输出全部进 `sandbox/`，源代码目录始终保持干净可提交状态

---

## 十、开发规则

### 何时新增文件

| 场景 | 操作 |
|------|------|
| 新增一个流水线阶段 | 在 `pipeline/` 新建步骤目录，不修改 `core/` |
| 新增AI适配器（如Gemini） | 在 `core/adapters/` 新增 `gemini_adapter.py`，更新 `registry.py` |
| 新增维护脚本 | 在 `tools/scripts/` 新增，不放在根目录 |
| 新增媒体处理工具 | 在 `tools/asset_production/` 新增 |
| 新增治理文档 | 在`knowledge/governance/` 新增 |
| 新增知识规则文件 | 在 `knowledge/` 对应目录新增 |

### 何时新增文件夹

**允许**新增文件夹的情况：
- `pipeline/` 下新增步骤目录（遵循 `step_NN_slug/` 命名）
- `tools/` 下新增工具类别目录（有明确职责边界）
- `knowledge/` 下新增知识子类别

**禁止**新增文件夹的情况：
- 不在 `core/` 根层级新增顶级模块（应归入现有子目录）
- 不在根目录新增任何目录（根目录已固定为8+个固定目录）
- 不创建与现有目录职责重叠的目录

### 何时必须拆分大文件

满足以下任一条件必须拆分：
- **超过 300 行** 且包含多个不相关的功能块
- **单一文件承担超过2种职责**
- **被3个以上不同模块引用**

---

## 十一、文件命名规则

| 类型 | 规范 | 示例 |
|------|------|------|
| 步骤目录 | `step_{NN}_{snake_slug}/` | `step_03_program_requirements/` |
| 适配器文件 | `{model}_adapter.py` | `openai_adapter.py` |
| 引擎文件 | `{功能}.py`（名词） | `generation.py`, `delta_patch.py` |
| 工具脚本 | 动词+名词 | `inspect_reports.py`, `export_concept.py` |
| Schema文件 | `{名称}.schema.json` | `execution_object_workflow.schema.json` |
| 配置文件 | `{范围}.toml/json` | `app.toml`, `ai_config.example.json` |

---

## 十二、禁止事项

```
❌ 在 core/ 以外的地方写运行时核心逻辑
❌ 在步骤插件(plugin.py)中硬编码路径字符串
❌ 直接 import steps.* 或 design_tool.*（已删除）
❌ 在 tools/ 根目录放任何 .py 文件（必须放在子目录）
❌ 在 sandbox/ saves/ logs/ 下提交任何文件（gitignore）
❌ 在 settings/ai_config.json、settings/api_config.toml 和 project_settings.json 里提交真实密钥/路径
❌ 创建超过 400 行的单一功能文件（必须拆分）
❌ 在 ucos/knowledge/episodic/ 以外的 ucos/ 目录添加或修改文件
```

---

## 十三、新增步骤完整流程

```bash
# 1. 在 pipeline/ 创建步骤目录
mkdir pipeline/step_16_new_stage/

# 2. 创建 plugin.py（继承 StagePlugin）
# 3. 创建 prompts/main.txt（AI提示词）
# 4. 创建 README.md（步骤说明）
# 5. 在 pipeline/_registry.json 注册
# 6. 在 pipeline/artifact_layer/registry.json 声明制品和依赖
# 7. 在 core/registry.py 的 STEP_SPECS 添加步骤定义
```

`plugin.py` 最小模板：
```python
from core.stage_plugin import StagePlugin
from core.context import StageContext, StageResult
from core.source.groups import SourceGroup
from core.source.importer import run_import_step
from core.engines.generation import apply_development_plan_outputs

class Plugin(StagePlugin):
    stage_id = "16"
    _source_groups = [SourceGroup("label", ("pattern_*",), "latest", True, ("SourceType",))]

    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.test_mode:
            return StageResult(status="success", outputs={"stage_id": self.stage_id})
        report = run_import_step(int(self.stage_id), self._source_groups, context=ctx)
        result = apply_development_plan_outputs(int(self.stage_id), report)
        return StageResult(status=result.get("status","success"), outputs=result)
```

---

## 十四、数据流概览

```
sandbox/source_artifacts/{type}_*/
  ↓ core/source/finder.py::find_sources()
  ↓
pipeline/step_NN/plugin.py::execute()
  ↓ core/source/importer.py::run_import_step()
  ↓ core/engines/generation.py::apply_development_plan_outputs()
  ↓
sandbox/outputs/artifacts/stage_NN/
  ↓ core/artifact/preflight.py::preflight_stage_contract()
  ↓ core/artifact/reviewer.py::run_review_pipeline()
  ↓ core/artifact/validator.py::run_artifact_validators()
  ↓
saves/{id}/snapshots/ ← core/save/manager.py::retry_sync()
```

```
sandbox/                    程序运行时的输出隔离区
├── source_artifacts/       输入源包（游戏创意文件）
├── outputs/
│   ├── artifacts/stage_*/  每步生成的设计文档
│   ├── artifact_layer/     预检报告
│   └── runtime_control/    停止/恢复信号文件
└── workspace/              用户工作区

saves/                      存档（save_manager.py管理）
└── {id}/
    ├── save_manifest.json
    ├── workspace/
    └── snapshots/

logs/
├── pipeline/gate_log.yaml  步骤执行门日志
├── changes/CHANGELOG.md    变更记录
├── git/                    git工作流说明
└── errors/                 错误日志
```
