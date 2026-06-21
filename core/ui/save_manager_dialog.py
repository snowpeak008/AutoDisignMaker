"""存档管理对话框。

提供完整的存档槽管理界面：新建、保存、加载、删除、打开目录。
"""

from __future__ import annotations

import os
import subprocess
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from core.save import manager as save_manager
from core.ui.theme import COLORS, FONT_SECTION, FONT_SMALL

if TYPE_CHECKING:
    from core.ui.app_window import CommercialDesignApp


class SaveManagerDialog(tk.Toplevel):
    """存档管理对话框 - 管理设计工作台的存档槽。

    功能：
    - 列出所有存档（名称 / 最近工作时间 / 阶段进度 / 存档ID）
    - 新建空白存档
    - 保存当前设计状态到选中存档
    - 加载选中存档并恢复设计状态
    - 删除选中存档
    - 在系统文件管理器中打开存档目录
    """

    def __init__(self, app: CommercialDesignApp) -> None:
        super().__init__(app)
        self.app = app
        self.runtime_root = app.runtime_root

        self.title("存档管理")
        self.geometry("980x520")
        self.minsize(860, 460)
        self.configure(bg=COLORS["surface"])
        self.transient(app)
        self.grab_set()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_ui()
        self.refresh()

    # ──────────────────────────────────────────────────────────
    # UI 构建
    # ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """构建对话框布局。"""
        frame = ttk.Frame(self, padding=10)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.tree = self._build_tree(frame)
        self._build_buttons(frame)
        self._build_statusbar(frame)

    def _build_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        """构建存档列表 Treeview。"""
        columns = ("name", "last", "progress", "id")
        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=14,
        )
        tree.heading("name", text="存档名")
        tree.heading("last", text="最近工作时间")
        tree.heading("progress", text="阶段进度")
        tree.heading("id", text="存档ID")
        tree.column("name", width=240, anchor="w")
        tree.column("last", width=180, anchor="w")
        tree.column("progress", width=100, anchor="center")
        tree.column("id", width=300, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        return tree

    def _build_buttons(self, parent: ttk.Frame) -> None:
        """构建底部操作按钮行。"""
        button_row = ttk.Frame(parent)
        button_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for col in range(8):
            button_row.columnconfigure(col, weight=1)

        button_specs = [
            ("新建存档", self.on_new_save),
            ("保存到选中存档", self.on_save_to_selected),
            ("加载选中存档", self.on_load_selected),
            ("重命名", self.on_rename_selected),
            ("删除选中存档", self.on_delete_selected),
            ("打开存档目录", self.on_open_save_dir),
            ("刷新", self.refresh),
            ("关闭", self.destroy),
        ]
        for col, (label, command) in enumerate(button_specs):
            ttk.Button(button_row, text=label, command=command).grid(
                row=0, column=col, padx=3, sticky="ew"
            )

    def _build_statusbar(self, parent: ttk.Frame) -> None:
        """构建底部状态栏。"""
        self.status_var = tk.StringVar(value="")
        tk.Label(
            parent,
            textvariable=self.status_var,
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            anchor="w",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # ──────────────────────────────────────────────────────────
    # 存档列表
    # ──────────────────────────────────────────────────────────

    def _save_has_design_project(self, save_id: str) -> bool:
        """判断存档是否包含设计项目数据。"""
        import json
        store_path = (
            save_manager.workspace_dir(self.runtime_root, save_id)
            / "outputs"
            / "execution_objects"
            / "execution_objects.json"
        )
        if not store_path.exists():
            return False
        try:
            data = json.loads(store_path.read_text(encoding="utf-8-sig"))
            objects = data.get("objects", []) if isinstance(data, dict) else []
            return any(
                obj.get("object_type") == "design_project"
                for obj in objects
                if isinstance(obj, dict)
            )
        except (OSError, ValueError):
            return False

    def refresh(self) -> None:
        """重新加载并渲染存档列表，只显示包含设计项目数据的存档。"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        all_saves = save_manager.list_saves(self.runtime_root)
        current_id = save_manager.current_save_id(self.runtime_root)
        design_saves = [s for s in all_saves if self._save_has_design_project(str(s.get("save_id", "")))]

        for item in design_saves:
            save_id = str(item.get("save_id", ""))
            display_name = item.get("display_name", "")
            if save_id == current_id:
                display_name = f"▶ {display_name}"
            progress = item.get("progress") or {}
            self.tree.insert(
                "",
                tk.END,
                iid=save_id,
                values=(
                    display_name,
                    (item.get("last_worked_at") or "")[:19],
                    progress.get("label", "已通过 0/16"),
                    save_id,
                ),
            )

        self.status_var.set(f"设计存档数量：{len(design_saves)}（共 {len(all_saves)} 个存档）")

    def selected_save_id(self) -> str | None:
        """返回当前选中的存档ID，无选中时返回 None。"""
        selection = self.tree.selection()
        return str(selection[0]) if selection else None

    # ──────────────────────────────────────────────────────────
    # 子对话框
    # ──────────────────────────────────────────────────────────

    def ask_save_name(self, default: str | None = None) -> str | None:
        """弹出命名对话框，返回用户输入的存档名，取消时返回 None。"""
        dialog = tk.Toplevel(self)
        dialog.title("存档命名")
        dialog.geometry("420x130")
        dialog.configure(bg=COLORS["surface"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)

        tk.Label(
            dialog,
            text="存档名称",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        name_var = tk.StringVar(value=default or save_manager.default_display_name())
        entry = ttk.Entry(dialog, textvariable=name_var)
        entry.grid(row=1, column=0, padx=12, sticky="ew")

        result: dict[str, str | None] = {"value": None}

        def confirm() -> None:
            result["value"] = name_var.get().strip() or save_manager.default_display_name()
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        actions = ttk.Frame(dialog)
        actions.grid(row=2, column=0, sticky="e", padx=12, pady=12)
        ttk.Button(actions, text="确认", command=confirm).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="取消", command=cancel).pack(side=tk.LEFT, padx=4)
        entry.focus_set()
        entry.selection_range(0, tk.END)
        self.wait_window(dialog)
        return result["value"]

    # ──────────────────────────────────────────────────────────
    # 项目配置存档支持
    # ──────────────────────────────────────────────────────────

    def _save_project_config_to(self, save_id: str) -> None:
        """将当前 project_settings.json 写入指定存档槽的 workspace。"""
        import json
        from core.paths import PROJECT_SETTINGS_FILE
        if not PROJECT_SETTINGS_FILE.exists():
            return
        try:
            config = json.loads(PROJECT_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        dest = save_manager.workspace_dir(self.runtime_root, save_id) / "project_config.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    def _restore_project_config_from(self, save_id: str) -> None:
        """从指定存档槽的 workspace 恢复 project_settings.json，并刷新 UI 配置。"""
        import json
        from core.paths import PROJECT_SETTINGS_FILE
        src = save_manager.workspace_dir(self.runtime_root, save_id) / "project_config.json"
        if not src.exists():
            return
        try:
            config = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        PROJECT_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROJECT_SETTINGS_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    # ──────────────────────────────────────────────────────────

    def on_new_save(self) -> None:
        """新建存档并将当前设计状态保存进去，默认以项目名称作为存档名。"""
        project_name = self.app.project_name.get().strip() or None
        name = self.ask_save_name(default=project_name)
        if not name:
            return
        try:
            from core.engines.execution_objects.design_project import save_design_project
            from core.engines.execution_objects.integration import load_execution_object_store

            save_manager.create_save(self.runtime_root, name, event="user_new_save")
            self._save_project_config_to(save_manager.current_save_id(self.runtime_root))
            store = load_execution_object_store(self.runtime_root)
            execution_obj = save_design_project(
                store,
                self.app.project_state,
                title=f"设计项目: {self.app.project_name.get()}",
                save_type="manual",
            )
            self.app.status_text.set(f"已保存: {execution_obj['execution_object_id']}")
            self.status_var.set(f"✅ 已新建存档并保存：{name}")
            self.refresh()
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("新建失败", str(exc), parent=self)

    def on_save_to_selected(self) -> None:
        """将当前设计状态保存到选中存档槽。"""
        save_id = self.selected_save_id()
        if not save_id:
            messagebox.showinfo("未选择存档", "请先选择一个存档。", parent=self)
            return
        if not messagebox.askyesno(
            "保存到选中存档",
            "这样做会覆盖当前选中存档，是否这样操作？",
            parent=self,
        ):
            return
        try:
            from core.engines.execution_objects.design_project import save_design_project
            from core.engines.execution_objects.integration import load_execution_object_store

            save_manager.set_current_save(self.runtime_root, save_id)
            self._save_project_config_to(save_id)
            store = load_execution_object_store(self.runtime_root)
            execution_obj = save_design_project(
                store,
                self.app.project_state,
                title=f"设计项目: {self.app.project_name.get()}",
                save_type="manual",
            )
            self.app.status_text.set(f"已保存: {execution_obj['execution_object_id']}")
            self.status_var.set(f"✅ 已保存到存档：{save_id}")
            self.refresh()
        except Exception as exc:
            traceback.print_exc()
            self.status_var.set(f"❌ 保存失败：{exc}")

    def on_load_selected(self) -> None:
        """加载选中存档并恢复设计状态到工作台。"""
        save_id = self.selected_save_id()
        if not save_id:
            messagebox.showinfo("未选择存档", "请先选择一个存档。", parent=self)
            return
        if not messagebox.askyesno(
            "加载选中存档",
            "这会覆盖当前的工作区，是否这样操作？",
            parent=self,
        ):
            return
        try:
            from core.engines.execution_objects.design_project import load_latest_design_project
            from core.engines.execution_objects.integration import load_execution_object_store
            from core.design.profile_schema import option_label

            save_manager.load_save(self.runtime_root, save_id)
            self._restore_project_config_from(save_id)
            store = load_execution_object_store(self.runtime_root)
            project_data = load_latest_design_project(store)

            if project_data:
                self.app.project_state = self.app.engine.normalize_state(project_data)
                self.app.project_name.set(
                    self.app.project_state.get("projectName", "未命名游戏设计项目")
                )
                self.app.sync_profile_labels()
                self.app.current_domain_id = self.app.engine.first_domain_id()
                self.app.clear_expanded_nodes()
                self.app.render()
                self.app.status_text.set(f"已加载存档：{save_id}")
                self.status_var.set(f"✅ 已加载存档：{save_id}")
            else:
                self.app.status_text.set(f"已加载存档（无设计项目数据）：{save_id}")
                self.status_var.set("⚠ 存档已加载，但未找到设计项目数据。")

            self.refresh()
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("加载失败", str(exc), parent=self)

    def on_rename_selected(self) -> None:
        """重命名选中存档。"""
        import json
        save_id = self.selected_save_id()
        if not save_id:
            messagebox.showinfo("未选择存档", "请先选择一个存档。", parent=self)
            return
        current_manifest = save_manager.get_save(self.runtime_root, save_id)
        if not current_manifest:
            messagebox.showerror("错误", "无法读取存档信息。", parent=self)
            return
        new_name = self.ask_save_name(default=current_manifest.get("display_name", ""))
        if not new_name:
            return
        try:
            manifest_path = save_manager.save_manifest_path(self.runtime_root, save_id)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["display_name"] = new_name
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            save_manager._replace_entry(self.runtime_root, manifest)
            self.refresh()
            self.status_var.set(f"已重命名为：{new_name}")
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("重命名失败", str(exc), parent=self)

    def on_delete_selected(self) -> None:
        """永久删除选中存档。"""
        save_id = self.selected_save_id()
        if not save_id:
            messagebox.showinfo("未选择存档", "请先选择一个存档。", parent=self)
            return
        if not messagebox.askyesno(
            "永久删除",
            "确定永久删除选中存档吗？删除后无法恢复。",
            parent=self,
        ):
            return
        try:
            save_manager.delete_save(self.runtime_root, save_id)
            self.refresh()
            self.status_var.set(f"已删除存档：{save_id}")
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("删除失败", str(exc), parent=self)

    def on_open_save_dir(self) -> None:
        """在系统文件管理器中打开选中存档的权威目录。"""
        save_id = self.selected_save_id()
        if not save_id:
            messagebox.showinfo("未选择存档", "请先选择一个存档。", parent=self)
            return
        path = save_manager.save_dir(self.runtime_root, save_id)
        try:
            if os.name == "nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("打开失败", f"无法打开目录：\n{exc}", parent=self)
