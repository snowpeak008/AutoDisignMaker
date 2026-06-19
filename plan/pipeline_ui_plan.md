# AutoDesignMaker 开发自动化界面 — 设计与开发计划

---

## Context

当前 AutoDesignMaker 只有一个 tkinter GUI（CommercialDesignApp），功能是游戏设计决策。完成设计后用户必须手动操作命令行触发流水线（steps 0-15）。整个"开发执行"阶段对用户不可见、不可控。

目标：将整个 GUI 重构为类似 VSCode 的主框架布局，包含：
1. 顶部标签切换"设计工作台" / "开发流水线"
2. 开发流水线面板：左侧步骤树、中部内容区、底部面板（日志 / AI 对话）
3. 全屏打开，支持最小化/最大化/任意方向拉伸（resizable）

---

## 整体界面框架设计（VSCode 风格）

```
┌────────────────────────────────────────────────────────────────────────┐
│  [设计工作台]  [开发流水线]                                 最小化 □ ×  │  ← 顶部导航栏
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ←─ 左侧边栏 ─→ ←──────────── 主内容区 ────────────────→              │
│  (resizable)   (resizable)                                              │
│                                                                         │
├────────────────────────────────────────────────────────────────────────┤
│  ← 底部面板（日志 | AI对话），可上下拉伸 →                              │
└────────────────────────────────────────────────────────────────────────┘
```

**分隔线均用 ttk.PanedWindow 实现**，支持用户任意拖拽调整各区域大小，与 VSCode 体验一致。

---

## 标签一：设计工作台

保持现有 `CommercialDesignApp` 的全部内容不变。将其从根窗口剥离，封装成一个 `tk.Frame`（`DesignPanel`），嵌入主框架的内容区。

---

## 标签二：开发流水线

### 布局

```
┌──────────────┬─────────────────────────────────────────────────────────┐
│  左侧：步骤树 │  中部：步骤详情卡                                       │
│  (可拖拽宽)  │                                                          │
│              │  ┌─ 步骤信息卡 ──────────────────────────────────────┐  │
│  ▶ 设计阶段  │  │ 步骤 07：程序计划（Design to Plan）               │  │
│    ● 00 创意 │  │ 状态：✓ 已完成                                    │  │
│    ● 01 框架 │  │ 依赖：05 程序评审 ✓                               │  │
│    ● 02 冻结 │  │ 上次运行：2026-06-19 10:12:05                     │  │
│    ● 03 需求 │  │                                                   │  │
│    ● 04 美术 │  │  [▶ 运行此步骤]  [📁 查看制品]  [⚙ Unity配置]    │  │
│    ● 05 评审 │  └───────────────────────────────────────────────────┘  │
│    ● 06 美审 │                                                          │
│  ▶ 开发阶段  │  ┌─ 制品文件 ────────────────────────────────────────┐  │
│    ● 07 计划 │  │  📄 program_task_breakdown.json                   │  │
│    ● 08 美计 │  │  📄 program_plan_index.md                         │  │
│    ● 09 对齐 │  │  📄 build_config.json                             │  │
│    ● 10 执行 │  └───────────────────────────────────────────────────┘  │
│    ● 11 美产 │                                                          │
│  ▶ 验证阶段  │                                                          │
│    ● 12 集成 │                                                          │
│    ● 13 构建 │                                                          │
│    ● 14 补丁 │                                                          │
│    ● 15 审计 │                                                          │
│  ──────────  │                                                          │
│  [▶ 运行全部]│                                                          │
│  [⏹ 停止]   │                                                          │
└──────────────┴─────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────────┐
│  [📋 日志]  [🤖 AI 对话]                                    [收起 ∨]   │  ← 底部面板标签
├────────────────────────────────────────────────────────────────────────┤
│  （日志内容 / AI对话内容，随标签切换）                                   │
└────────────────────────────────────────────────────────────────────────┘
```

### 步骤状态颜色（复用 theme.py）

| 状态 | 颜色变量 | 含义 |
|------|----------|------|
| not_started | COLORS["surface_alt"] | 未执行 |
| in_progress | COLORS["primary_soft"] | 执行中（动态刷新） |
| success | COLORS["success_soft"] | 已成功 |
| failed | COLORS["danger_soft"] | 失败 |
| blocked | COLORS["warning_soft"] | 依赖未满足 |

### 步骤分组（左侧树）

- **设计阶段**：步骤 00-06
- **开发阶段**：步骤 07-11
- **验证阶段**：步骤 12-15

分组用折叠/展开节点，默认全部展开。

### Unity 路径未配置的处理

步骤 03 及其所有下游步骤（04-15），在运行时调用 `run_actual_development_preflight()` 检查。若未配置：
- 按钮"▶ 运行此步骤"点击后弹出 messagebox，精确提示缺失字段：
  - "未配置 Unity 项目路径（development_path）"
  - "未配置 Unity Editor 路径（editor_path）"
- 不允许执行，引导用户点击"⚙ Unity配置"

---

## 底部面板：日志 + AI 对话

### 日志面板

- `tk.Text` 滚动文本框（只读，自动滚到底部）
- 日志格式：`[INFO/WARN/ERROR] HH:MM:SS  消息内容`
- 线程安全：子线程通过 `queue.Queue` → 主线程 `after(100)` 轮询写入
- 不随步骤切换而清空，记录本次会话的全部输出

### AI 对话面板

参考现有 `AIInterviewWindow` 的对话区实现，嵌入底部面板（不弹出独立窗口）。

**功能定位**：辅助问答，不直接修改项目状态，仅提供建议和解释。

**对话上下文来源**（根据当前所在标签自动切换）：
- 在**设计工作台**时：提供游戏设计领域知识、节点选择建议
- 在**开发流水线**时：提供当前步骤的制品内容摘要、步骤说明、常见问题解答

**实现方式**：
- 复用 `CodexCliBackend`（`core/design/ai_backend.py`）作为后端
- 系统 prompt 根据当前 tab 动态切换（设计模式 / 流水线辅助模式）
- 消息历史仅保留当前会话，不持久化到文件
- 用户输入框 + 发送按钮，AI 回复显示在对话气泡中（复用 AIInterviewWindow 的消息渲染风格）

---

## 文件结构变更

### 新增文件

```
core/ui/
├── main_window.py            ← 主框架窗口（替代 CommercialDesignApp 作为根窗口）
│                                包含顶部标签栏、PanedWindow 骨架、底部面板
├── pipeline_panel.py         ← 开发流水线主面板（左侧树 + 中部详情）
├── pipeline_step_card.py     ← 单步骤状态卡片组件
├── bottom_panel.py           ← 底部面板（日志 + AI对话，标签切换）
└── unity_config_dialog.py    ← Unity 路径配置对话框
```

### 修改文件

```
core/ui/app_window.py   ← CommercialDesignApp 改为继承 tk.Frame（而非 tk.Tk）
                           保持内部逻辑不变，作为设计工作台面板嵌入主框架
core/ui/gui_app.py      ← main() 改为实例化 MainWindow 而非 CommercialDesignApp
```

---

## 各模块详细设计

### 1. core/ui/main_window.py — MainWindow(tk.Tk)

```python
class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoDesignMaker")
        self.state("zoomed")          # 全屏打开
        self.minsize(1180, 720)
        self.resizable(True, True)    # 支持任意拉伸

        self._build_topbar()          # 顶部标签栏
        self._build_main_area()       # 中部内容区 + 底部面板（垂直 PanedWindow）
        self._show_design()           # 默认显示设计工作台

    def _build_topbar(self):
        # 固定高度顶部栏，两个切换按钮：设计工作台 / 开发流水线
        # 当前激活标签用 COLORS["primary"] 高亮

    def _build_main_area(self):
        # 垂直 ttk.PanedWindow
        # 上半：content_frame，叠放 DesignPanel 和 PipelinePanel
        # 下半：BottomPanel（初始高度 180px）

    def _show_design(self):
        # design_panel.lift()，更新标签高亮
        # 通知 BottomPanel 切换到"设计"上下文

    def _show_pipeline(self):
        # pipeline_panel.lift()，更新标签高亮
        # pipeline_panel.refresh() 刷新步骤状态
        # 通知 BottomPanel 切换到"流水线"上下文
```

### 2. core/ui/pipeline_panel.py — PipelinePanel(tk.Frame)

```python
class PipelinePanel(tk.Frame):
    def __init__(self, parent, project_root: Path, log_queue: queue.Queue):
        # 水平 ttk.PanedWindow：左侧步骤树 + 右侧详情区
        # log_queue 传递给运行线程，日志输出到 BottomPanel

    def refresh(self):
        # 遍历 stage_dir(N)/validation_report.json，更新 StepCard 状态

    def _select_step(self, step_num: int):
        # 刷新右侧详情卡：步骤信息 + 制品文件列表

    def _run_single(self, step_num: int):
        # 步骤 >= 3 时调用 run_actual_development_preflight()
        # 若 blockers 非空 → messagebox.showwarning()，列出缺失字段，return
        # threading.Thread(target=_exec_step, args=(step_num,)).start()

    def _exec_step(self, step_num: int):
        # 重定向 sys.stdout 到 QueueWriter(log_queue)
        # run_range(step_num, step_num, auto_approve=True, skip_preflight=True)
        # 完成后 after(0, self.refresh)

    def _run_all(self):
        # 同上，run_range(0, 15, auto_approve=True)

    def _stop(self):
        # request_stop(PROJECT_ROOT)
```

### 3. core/ui/pipeline_step_card.py — StepCard(tk.Frame)

```python
class StepCard(tk.Frame):
    STATUS_COLORS = {
        "not_started": COLORS["surface_alt"],
        "in_progress": COLORS["primary_soft"],
        "success":     COLORS["success_soft"],
        "failed":      COLORS["danger_soft"],
        "blocked":     COLORS["warning_soft"],
    }

    def __init__(self, parent, step_spec: StepSpec, on_select: Callable):
        # 可点击卡片：步骤编号 + 标题 + 状态圆点

    def update_status(self, status: str):
        # 更新背景色和状态标签文字
```

### 4. core/ui/bottom_panel.py — BottomPanel(tk.Frame)

```python
class BottomPanel(tk.Frame):
    def __init__(self, parent, project_root: Path, log_queue: queue.Queue):
        # 顶部：标签栏（[📋 日志] [🤖 AI 对话] [收起 ∨]）
        # 内容区：LogPane 和 AIChatPane 叠放，随标签切换

    def set_context(self, context: str):
        # "design" 或 "pipeline"，影响 AI 对话的系统 prompt

    def append_log(self, line: str):
        # after(0, lambda: log_text.insert(END, line + "\n"))
        # after(0, lambda: log_text.see(END))

    def _poll_log_queue(self):
        # 消费 log_queue，调用 append_log
        # after(100, self._poll_log_queue)

    # AI 对话区：
    # - 消息列表（滚动 Frame，气泡式渲染，复用 AIInterviewWindow 样式）
    # - 输入框 + [发送] 按钮
    # - 发送时后台线程调用 CodexCliBackend.run_json_task()
    # - 结果通过 after() 回主线程追加到消息列表
```

### 5. core/ui/unity_config_dialog.py — UnityConfigDialog(tk.Toplevel)

```python
class UnityConfigDialog(tk.Toplevel):
    # 两个路径输入行：development_path（目录选择）、editor_path（文件选择）
    # [保存] 按钮：写入 settings/project_settings.json，
    #             调用 run_actual_development_preflight() 验证，
    #             显示通过/失败及 blocker 详情
```

### 6. 修改 core/ui/app_window.py

```python
# 将 class CommercialDesignApp(tk.Tk) 改为 class CommercialDesignApp(tk.Frame)
# __init__ 参数增加 parent，super().__init__(parent)
# 删除 self.title()、self.geometry()、self.minsize()、self.configure(bg=...) 等根窗口调用
# 其余所有内部逻辑保持不变
```

### 7. 修改 core/ui/gui_app.py

```python
def main() -> int:
    from core.ui.main_window import MainWindow
    load_config()
    validate_data_integrity()
    app = MainWindow()
    app.mainloop()
    return 0
```

---

## 复用的现有函数

| 函数/类 | 文件 | 用途 |
|---------|------|------|
| `run_range()` | `core/main.py` | 后台线程执行步骤范围 |
| `request_stop()` | `core/runtime/control.py` | 停止流水线 |
| `STEP_SPECS` | `core/registry.py` | 步骤元数据（名称、依赖） |
| `load_project_settings()` | `core/runtime/preflight.py` | 读取 Unity 路径 |
| `run_actual_development_preflight()` | `core/runtime/preflight.py` | 检查 Unity 配置 |
| `COLORS`, `FONT_*` | `core/ui/theme.py` | 统一主题配色 |
| `stage_dir()` | `core/stage.py` | 获取阶段制品目录路径 |
| `CodexCliBackend` | `core/design/ai_backend.py` | AI 对话后端 |
| `ensure_current_save()` | `core/save/manager.py` | 执行前确保有存档 |

---

## 实现顺序

1. **`core/ui/unity_config_dialog.py`** — 最小依赖，独立完成
2. **`core/ui/pipeline_step_card.py`** — 纯 UI 组件
3. **`core/ui/pipeline_panel.py`** — 核心执行面板
4. **`core/ui/bottom_panel.py`** — 日志 + AI 对话
5. **修改 `core/ui/app_window.py`** — CommercialDesignApp Frame 化
6. **`core/ui/main_window.py`** — 主框架集成
7. **修改 `core/ui/gui_app.py`** — 入口切换到 MainWindow

---

## 验证方式

1. `python gui_app.py` 启动，窗口全屏，顶部两个标签可切换
2. 设计工作台标签：原有设计 UI 完全正常，功能无回归
3. 开发流水线标签：左侧16步骤分三组显示，状态颜色正确反映 sandbox 实际状态
4. 点击步骤03，未配置 Unity 时点击"运行"弹出精确提示（列出缺失字段）
5. Unity配置对话框：能选择路径、保存、显示预检结果
6. 点击"运行此步骤"（步骤00），日志实时滚动在底部日志面板
7. "停止"后，stop_request.json 被写入，执行在边界处停止，步骤状态刷新
8. AI 对话面板：输入问题得到回复，回复不修改任何项目状态
9. 窗口四边均可拖拽，PanedWindow 分隔线可任意拖动调整布局
