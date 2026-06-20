# UI 集成指南：设计工作台执行对象存档

## 概述

本文档说明如何将 `core/ui/app_window.py` 的设计工作台保存/加载功能改为使用执行对象存储。

---

## 修改清单

### 1. 保存项目 (save_project)

**原实现**（第1813-1832行）：
```python
def save_project(self):
    self.save_visible_notes()
    default_dir = self.runtime_subdir("projects")
    path = filedialog.asksaveasfilename(...)
    if not path:
        return
    if not self.ensure_project_local_path(path, "项目文件"):
        return
    try:
        Path(path).write_text(json.dumps(self.project_state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as error:
        messagebox.showerror("保存失败", f"无法写入项目文件：\n{error}")
        return
    self.status_text.set(f"已保存：{path}")
```

**新实现**：
```python
def save_project(self):
    """保存设计项目到执行对象存储"""
    from core.engines.execution_objects.design_project import save_design_project
    from core.engines.execution_objects.integration import load_execution_object_store
    from core.save import manager as save_manager
    
    # 1. 保存可见笔记
    self.save_visible_notes()
    
    # 2. 加载执行对象存储
    try:
        store = load_execution_object_store(self.project_root)
    except Exception as error:
        messagebox.showerror("存储错误", f"无法加载执行对象存储：\n{error}")
        return
    
    # 3. 保存设计项目为执行对象
    try:
        execution_obj = save_design_project(
            store,
            self.project_state,
            title=f"设计项目: {self.project_name.get()}",
            save_type="manual"
        )
        
        # 4. 触发存档同步
        save_manager.sync_current_save(
            self.project_root,
            event="design_project_save",
            message=f"保存设计项目: {execution_obj['execution_object_id']}"
        )
        
        # 5. 更新状态
        self.status_text.set(f"已保存: {execution_obj['execution_object_id']}")
        
        messagebox.showinfo(
            "保存成功", 
            f"设计项目已保存到执行对象存储\n\n"
            f"版本ID: {execution_obj['execution_object_id']}\n"
            f"项目名称: {self.project_name.get()}\n"
            f"状态: {execution_obj['state']}"
        )
        
    except Exception as error:
        messagebox.showerror("保存失败", f"无法保存设计项目：\n{error}")
        import traceback
        print(traceback.format_exc())
```

**关键变化**：
- ❌ 不再弹出文件对话框
- ❌ 不再写入文件系统
- ✅ 直接保存到执行对象存储
- ✅ 自动触发存档同步
- ✅ 显示版本ID

---

### 2. 打开项目 (open_project)

**原实现**（第1834-1855行）：
```python
def open_project(self):
    default_dir = self.runtime_subdir("projects")
    path = filedialog.askopenfilename(...)
    if not path:
        return
    if not self.ensure_project_local_path(path, "项目文件"):
        return
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        messagebox.showerror("打开失败", f"无法读取项目文件：\n{error}")
        return
    if isinstance(payload, dict) and "projectState" in payload:
        payload = payload["projectState"]
    self.project_state = self.engine.normalize_state(payload)
    self.project_name.set(self.project_state.get("projectName", "未命名游戏设计项目"))
    ...
```

**新实现**：
```python
def open_project(self):
    """打开设计项目（从执行对象存储）"""
    from core.engines.execution_objects.design_project import (
        load_latest_design_project,
        list_design_project_versions,
        restore_design_project_version,
    )
    from core.engines.execution_objects.integration import load_execution_object_store
    
    # 1. 加载执行对象存储
    try:
        store = load_execution_object_store(self.project_root)
    except Exception as error:
        messagebox.showerror("存储错误", f"无法加载执行对象存储：\n{error}")
        return
    
    # 2. 获取所有版本
    versions = list_design_project_versions(store, include_drafts=False)
    
    if not versions:
        response = messagebox.askyesno(
            "无项目", 
            "当前存档中没有设计项目。\n\n是否尝试从旧文件导入？"
        )
        if response:
            self._open_project_from_file()  # 兜底：从文件加载
        return
    
    # 3. 显示版本选择对话框
    selected_version = self._show_version_selection_dialog(versions)
    
    if not selected_version:
        return
    
    # 4. 加载选中的版本
    try:
        project_data = restore_design_project_version(
            store,
            selected_version["execution_object_id"]
        )
        
        self.project_state = self.engine.normalize_state(project_data)
        self.project_name.set(self.project_state.get("projectName", "未命名游戏设计项目"))
        
        # 重置UI状态
        for key, value in self.project_state.get("profile", {}).items():
            self.profile_vars.setdefault(key, tk.StringVar()).set(option_label(key, value))
        self.current_domain_id = self.engine.first_domain_id()
        self.clear_expanded_nodes()
        
        self.status_text.set(f"已打开: {selected_version['execution_object_id']}")
        self.render()
        
    except Exception as error:
        messagebox.showerror("打开失败", f"无法加载设计项目：\n{error}")
        import traceback
        print(traceback.format_exc())


def _show_version_selection_dialog(self, versions: list) -> dict | None:
    """显示版本选择对话框"""
    import tkinter as tk
    from tkinter import ttk
    
    dialog = tk.Toplevel(self)
    dialog.title("选择设计项目版本")
    dialog.geometry("700x400")
    dialog.transient(self)
    dialog.grab_set()
    
    selected_version = None
    
    # 创建列表框
    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill="both", expand=True)
    
    ttk.Label(frame, text="选择要打开的版本:", font=("微软雅黑", 10)).pack(anchor="w", pady=(0, 10))
    
    listbox = tk.Listbox(frame, font=("Consolas", 9))
    listbox.pack(fill="both", expand=True)
    
    # 填充版本列表
    for version in versions:
        project_name = version.get("user_content", {}).get("projectName", "未命名")
        version_id = version["execution_object_id"]
        updated_at = version.get("updated_at", "")[:19]  # 截取到秒
        state = version.get("state", "unknown")
        
        item_text = f"{version_id}  |  {project_name}  |  {updated_at}  |  {state}"
        listbox.insert("end", item_text)
    
    # 默认选中第一项（最新版本）
    if versions:
        listbox.selection_set(0)
    
    # 按钮
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill="x", padx=10, pady=10)
    
    def on_ok():
        nonlocal selected_version
        selection = listbox.curselection()
        if selection:
            selected_version = versions[selection[0]]
        dialog.destroy()
    
    def on_cancel():
        dialog.destroy()
    
    ttk.Button(button_frame, text="打开", command=on_ok).pack(side="right", padx=5)
    ttk.Button(button_frame, text="取消", command=on_cancel).pack(side="right")
    
    dialog.wait_window()
    return selected_version


def _open_project_from_file(self):
    """从文件加载项目（兜底方案）"""
    default_dir = self.runtime_subdir("projects")
    path = filedialog.askopenfilename(
        title="打开项目文件", 
        filetypes=[("JSON", "*.json")], 
        initialdir=str(default_dir)
    )
    
    if not path:
        return
    
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "projectState" in payload:
            payload = payload["projectState"]
        
        self.project_state = self.engine.normalize_state(payload)
        self.project_name.set(self.project_state.get("projectName", "未命名游戏设计项目"))
        
        # 自动迁移到执行对象存储
        response = messagebox.askyesno(
            "迁移项目", 
            "是否将此项目保存到执行对象存储？\n\n"
            "这样可以享受版本历史、自动备份等功能。"
        )
        if response:
            self.save_project()
        
        self.render()
        
    except Exception as error:
        messagebox.showerror("打开失败", f"无法读取项目文件：\n{error}")
```

**关键变化**：
- ✅ 显示版本选择对话框
- ✅ 支持查看所有历史版本
- ✅ 兜底方案：仍可从文件加载
- ✅ 自动提示迁移旧文件

---

### 3. 自动保存 (新增)

**新增方法**：
```python
def auto_save_project(self):
    """自动保存设计项目（draft状态）"""
    from core.engines.execution_objects.design_project import auto_save_design_project
    from core.engines.execution_objects.integration import load_execution_object_store
    
    try:
        store = load_execution_object_store(self.project_root)
        auto_save_design_project(store, self.project_state)
        # 不触发存档同步，仅保存到执行对象存储
        # 不显示消息框，静默保存
    except Exception:
        pass  # 静默失败，不打扰用户


def start_auto_save_timer(self):
    """启动自动保存定时器"""
    def auto_save_tick():
        self.auto_save_project()
        self.after(60000, auto_save_tick)  # 每60秒自动保存一次
    
    self.after(60000, auto_save_tick)


# 在 __init__ 中调用
def __init__(self, parent, project_root):
    # ... 现有初始化代码 ...
    
    # 启动自动保存
    self.start_auto_save_timer()
```

---

### 4. 导出功能集成

**修改 export_concept 方法**：
```python
def export_concept(self):
    # ... 现有导出逻辑 ...
    
    # 保存到执行对象存储
    from core.engines.execution_objects.user_artifact import save_user_artifact
    from core.engines.execution_objects.integration import load_execution_object_store
    
    try:
        store = load_execution_object_store(self.project_root)
        
        # 获取当前设计项目的执行对象ID
        from core.engines.execution_objects.design_project import load_latest_design_project
        latest_project = load_latest_design_project(store)
        source_project_id = latest_project.get("execution_object_id", "") if latest_project else ""
        
        # 保存导出制品
        save_user_artifact(
            store,
            export_format=export_format,
            export_scope=export_scope,
            content=content,  # 导出的内容
            title=f"{export_format} 导出",
            source_project_id=source_project_id,
            target_directory="workspace/exports/",
            metadata={
                "include_gameplay_global_view": include_gameplay_global_view,
            }
        )
    except Exception as error:
        print(f"保存导出制品到执行对象存储失败: {error}")
```

---

## 实施步骤

### Phase 1: 准备工作
1. ✅ 确保所有核心模块已创建
2. ✅ 运行数据迁移脚本

### Phase 2: UI 修改
1. 备份 `core/ui/app_window.py`
2. 逐个替换方法
3. 添加自动保存功能
4. 测试基本功能

### Phase 3: 测试
1. 测试保存项目
2. 测试打开项目
3. 测试版本选择
4. 测试自动保存
5. 测试兜底方案（从文件加载）

### Phase 4: 用户体验优化
1. 添加加载指示器
2. 优化错误提示
3. 添加版本对比功能
4. 添加版本删除功能

---

## 兼容性策略

**向后兼容**：
- 保留从文件加载的能力（`_open_project_from_file`）
- 自动提示用户迁移旧文件
- 新旧方式并存一段时间

**渐进式迁移**：
- 用户首次保存时自动迁移
- 提供手动迁移工具
- 保留旧文件作为备份

---

## 注意事项

1. **错误处理**：所有执行对象操作都需要 try-except
2. **用户提示**：首次使用时告知用户新的保存机制
3. **性能**：执行对象存储是单个 JSON 文件，注意性能
4. **备份**：迁移前务必备份原文件

---

**END OF UI INTEGRATION GUIDE**
