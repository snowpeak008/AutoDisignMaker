# 路径清理与导出功能问题分析

> 日期：2026-06-20

---

## 问题1：清理 `projects/` 路径

### 当前状况

**路径**：`E:\workwork\CrewAi\AutoDesignMaker\projects\`

**文件**：
- `test__001.json` (528KB) - 你手动保存的设计项目

**问题**：
这个路径是 BUG 导致的错误位置，不应该存在。

---

### 使用情况分析

通过搜索整个项目，`projects/` 被引用的地方：

#### ✅ 应该使用的（正确路径）
1. `core/paths.py:65` - `WORKSPACE_PROJECTS_DIR = WORKSPACE_DIR / "projects"`
2. `core/design/project_templates.py:27` - `runtime_project_root() / "workspace" / "projects" / "templates"`
3. `core/design/prompt_evaluation.py:1583` - `runtime_project_root() / "workspace" / "projects"`
4. 迁移脚本 - 会扫描这个路径（用于迁移）

#### ❌ 错误使用的（BUG）
1. `core/ui/app_window.py:1815,1835` - `self.runtime_subdir("projects")`
   - 由于 `runtime_project_root()` 返回错误，导致指向根目录

#### 📚 文档引用
- 多个架构文档中提到这个问题

---

### 结论

**✅ 可以安全删除 `E:\workwork\CrewAi\AutoDesignMaker\projects/`**

**原因**：
1. 这不是设计的正确位置
2. 正确位置是 `sandbox/workspace/projects/`
3. 除了迁移脚本（专门用于清理），没有其他代码依赖这个错误路径
4. 你的文件 `test__001.json` 已经通过迁移脚本转换为执行对象

**操作建议**：
```bash
# 1. 备份（如果需要）
cp E:/workwork/CrewAi/AutoDesignMaker/projects/test__001.json E:/workwork/CrewAi/AutoDesignMaker/projects/test__001.json.backup

# 2. 删除整个目录
rm -rf E:/workwork/CrewAi/AutoDesignMaker/projects

# 3. 不需要重建，因为正确的路径已经存在
# sandbox/workspace/projects/ 已经存在并且是正确的位置
```

---

## 问题2：导出功能的按钮流程

### 你的观察

**问题描述**：
> "导出界面没有真实的导出按钮，就是，点击导出按钮后，应该显示导出的文件夹，并且导出的文件夹可以被用户更换"

---

### 实际代码分析

**完整流程**（`export_project()` 方法，第1786-1811行）：

```python
def export_project(self):
    # 1. 保存当前笔记
    self.save_visible_notes()
    
    # 2. 弹出导出选项对话框（choose_export_options）
    options = self.choose_export_options()
    if not options:
        return
    export_format, export_scope, include_gameplay_global_view = options
    
    # 3. ✅ 这里会弹出文件夹选择对话框！
    default_dir = self.runtime_subdir("exports")
    directory = filedialog.askdirectory(
        title="选择导出目录", 
        initialdir=str(default_dir)
    )
    if not directory:
        return
    
    # 4. 验证路径
    if not self.ensure_project_local_path(directory, "导出目录"):
        return
    
    # 5. 执行导出
    try:
        path = write_export(
            self.engine,
            self.project_state,
            directory,
            export_format,
            export_scope,
            include_gameplay_global_view=include_gameplay_global_view,
        )
    except OSError as error:
        messagebox.showerror("导出失败", f"无法写入导出文件：\n{error}")
        return
    
    # 6. 显示成功消息
    self.status_text.set(f"已导出：{path}")
    messagebox.showinfo("导出完成", f"已导出到：\n{path}")
```

---

### 关键发现

**✅ 导出功能是完整的！**

**实际流程**：
1. 点击"导出"按钮
2. 弹出"选择导出内容"对话框（`choose_export_options`）
   - 选择格式
   - 选择范围
   - 预览内容
   - 点击"继续"
3. **弹出文件夹选择对话框**（`filedialog.askdirectory`）← 这一步存在！
   - 默认目录：`sandbox/workspace/exports/`
   - 用户可以选择其他目录
4. 生成文件
5. 显示成功消息

---

### 可能的混淆

#### 情况A：选项对话框的"继续"按钮

你可能把第2步的对话框当成了最终导出对话框。

- 第2步对话框有：**"继续"** 和 "取消" 按钮
- 点击"继续"后，**才会**弹出文件夹选择对话框

#### 情况B：文件夹选择对话框

第3步会弹出标准的 Windows 文件夹选择对话框：
- 标题："选择导出目录"
- 默认位置：`sandbox/workspace/exports/`
- 用户可以浏览和选择其他目录

---

### 测试步骤

**请按以下步骤测试**：

1. 启动设计工作台
2. 点击"导出"按钮
3. 应该看到"选择导出内容"对话框
   - 有格式选择
   - 有范围选择
   - 有预览窗口
   - 底部有"继续"和"取消"按钮
4. 点击"继续"
5. **应该弹出 Windows 文件夹选择对话框** ← 关键步骤
   - 如果没有弹出，可能是被其他窗口挡住了
   - 查看任务栏是否有闪烁的窗口
6. 选择导出目录
7. 点击"选择文件夹"
8. 应该显示"导出完成"消息框

---

## 可能存在的问题

### 问题A：对话框被遮挡

**症状**：点击"继续"后，没有看到文件夹选择对话框

**原因**：Windows 对话框可能被主窗口遮挡

**解决方案**：
在 `export_project()` 方法中，文件夹选择对话框应该设置为模态：

```python
# 第1793行，当前代码：
directory = filedialog.askdirectory(title="选择导出目录", initialdir=str(default_dir))

# 改为：
directory = filedialog.askdirectory(
    title="选择导出目录", 
    initialdir=str(default_dir),
    parent=self  # 添加父窗口引用
)
```

---

### 问题B：用户体验优化

**当前流程的问题**：
1. 用户点击"导出"
2. 第一个对话框：选择选项
3. 第二个对话框：选择目录
4. 太多步骤，可能让用户困惑

**优化建议**：

#### 方案1：在选项对话框中显示导出路径

```python
def choose_export_options(self):
    # ... 现有代码 ...
    
    # 添加导出目录选择
    dir_frame = tk.Frame(window, bg=COLORS["surface"], padx=16)
    dir_frame.pack(fill=tk.X, pady=(10, 0))
    
    tk.Label(
        dir_frame, 
        text="导出目录", 
        bg=COLORS["surface"], 
        fg=COLORS["muted"], 
        font=FONT_SMALL
    ).pack(anchor=tk.W)
    
    export_dir_var = tk.StringVar(value=str(self.runtime_subdir("exports")))
    
    dir_entry_frame = tk.Frame(dir_frame, bg=COLORS["surface"])
    dir_entry_frame.pack(fill=tk.X, pady=(4, 0))
    
    ttk.Entry(
        dir_entry_frame, 
        textvariable=export_dir_var, 
        width=40
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
    
    def choose_directory():
        directory = filedialog.askdirectory(
            title="选择导出目录",
            initialdir=export_dir_var.get()
        )
        if directory:
            export_dir_var.set(directory)
    
    ttk.Button(
        dir_entry_frame, 
        text="浏览...", 
        command=choose_directory
    ).pack(side=tk.RIGHT)
    
    # 修改 confirm 函数，返回目录
    def confirm():
        fmt = format_var.get()
        scope = "archive" if fmt == "json" else scope_var.get()
        result["value"] = (
            fmt, 
            scope, 
            include_gameplay_global_var.get(),
            export_dir_var.get()  # 添加目录
        )
        self.export_format.set(fmt)
        window.destroy()
    
    # ... 其余代码 ...
    return result["value"]
```

然后修改 `export_project()`：

```python
def export_project(self):
    self.save_visible_notes()
    options = self.choose_export_options()
    if not options:
        return
    
    # 解包包含目录的选项
    export_format, export_scope, include_gameplay_global_view, directory = options
    
    # 不再需要单独的 askdirectory 对话框
    if not self.ensure_project_local_path(directory, "导出目录"):
        return
    
    try:
        path = write_export(...)
    except OSError as error:
        messagebox.showerror("导出失败", f"无法写入导出文件：\n{error}")
        return
    
    self.status_text.set(f"已导出：{path}")
    messagebox.showinfo("导出完成", f"已导出到：\n{path}")
```

---

## 总结与建议

### 问题1：`projects/` 路径

**✅ 可以安全删除**
- 这是 BUG 产生的错误路径
- 正确路径是 `sandbox/workspace/projects/`
- 没有代码依赖这个错误路径

**操作**：
```bash
rm -rf E:/workwork/CrewAi/AutoDesignMaker/projects
```

---

### 问题2：导出功能

**✅ 功能是完整的**
- 文件夹选择对话框存在（第1793行）
- 用户可以更换导出目录
- 可能是被遮挡或用户体验问题

**建议**：
1. **短期**：测试时注意查看是否有被遮挡的对话框
2. **中期**：实施方案1，将目录选择集成到选项对话框
3. **长期**：实施执行对象存档架构，导出也作为执行对象管理

---

## 立即行动

### 1. 清理错误路径
```bash
cd E:/workwork/CrewAi/AutoDesignMaker
rm -rf projects/
```

### 2. 测试导出功能
启动设计工作台，完整走一遍导出流程，确认是否有被遮挡的对话框。

### 3. 如需优化
参考上面的"方案1"，将目录选择集成到选项对话框中。

---

**问题解答完毕** ✅
