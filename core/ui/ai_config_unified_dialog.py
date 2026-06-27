from __future__ import annotations

import json
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from core.config.ai_config import (
    APICategory,
    APIEntry,
    CATEGORY_COMPLETION,
    CATEGORY_DEV,
    CATEGORY_IMAGE,
    CODEX_FILE_CONFIG_TYPES,
    CONFIG_TYPE_CODEX_CLI_IMAGE,
    CUSTOM_CONFIG_TYPES,
    LOCAL_CLI_TYPES,
    TYPE_LABELS,
    default_entries,
    load_ai_config,
    mask_secret,
    new_entry,
    save_ai_config,
)
from core.ui.theme import COLORS, FONT_BODY, FONT_SECTION, FONT_SMALL, center_window


TAB_LABELS = {
    CATEGORY_DEV: "开发API",
    CATEGORY_IMAGE: "生图API",
    CATEGORY_COMPLETION: "补全API",
}
TYPE_OPTIONS = {
    CATEGORY_DEV: [
        ("本地 Codex CLI", "local_codex_cli"),
        ("本地 Claude Code CLI", "local_claude_cli"),
        ("OpenAI 兼容 API", "openai_dev_api"),
        ("自定义 API", "custom_dev_api"),
    ],
    CATEGORY_IMAGE: [
        ("Codex CLI 内置生图", "codex_cli_image"),
        ("OpenAI 图片 API", "openai_image_api"),
        ("本地 SD WebUI", "sd_webui_api"),
        ("自定义图片 API", "custom_image_api"),
    ],
    CATEGORY_COMPLETION: [
        ("本地 Codex CLI", "local_codex_completion_cli"),
        ("本地 Claude Code CLI", "local_claude_completion_cli"),
        ("OpenAI 补全 API", "openai_completion_api"),
        ("自定义补全 API", "custom_completion_api"),
    ],
}


def _entry(parent: tk.Widget, label: str, variable: tk.StringVar, *, secret: bool = False) -> ttk.Entry:
    tk.Label(parent, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
    widget = ttk.Entry(parent, textvariable=variable, show="*" if secret else "")
    widget.pack(fill=tk.X, pady=(2, 8))
    return widget


class AIConfigUnifiedDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title("AI 配置管理")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._on_saved = on_saved
        self._config = load_ai_config()
        self._current_tab = CATEGORY_DEV
        self._selected_index = 0
        self._tab_buttons: dict[str, tk.Button] = {}
        self._type_var = tk.StringVar()
        self._api_url_var = tk.StringVar()
        self._api_key_var = tk.StringVar()
        self._codex_toml_var = tk.StringVar()
        self._codex_json_var = tk.StringVar()
        self._status_var = tk.StringVar(value="就绪")

        self._build()
        self._switch_tab(CATEGORY_DEV)
        self.update_idletasks()
        center_window(self, 820, 650)
        self.deiconify()

    def _build(self) -> None:
        root = tk.Frame(self, bg=COLORS["bg"], padx=16, pady=14)
        root.pack(fill=tk.BOTH, expand=True)
        tk.Label(root, text="AI 配置管理", bg=COLORS["bg"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        self._build_tab_bar(root)
        body = tk.Frame(root, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._build_left_panel(body)
        self._right = tk.Frame(body, bg=COLORS["surface"], padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["border"])
        self._right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        footer = tk.Frame(root, bg=COLORS["bg"])
        footer.pack(fill=tk.X, pady=(12, 0))
        tk.Label(footer, textvariable=self._status_var, bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(footer, text="取消", command=self._close).pack(side=tk.RIGHT)
        ttk.Button(footer, text="保存", command=lambda: self._apply_changes(close=True)).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(footer, text="应用", command=lambda: self._apply_changes(close=False)).pack(side=tk.RIGHT, padx=(0, 8))

    def _build_tab_bar(self, parent: tk.Widget) -> None:
        bar = tk.Frame(parent, bg=COLORS["bg"])
        bar.pack(fill=tk.X, pady=(10, 0))
        for tab_id, label in TAB_LABELS.items():
            btn = tk.Button(bar, text=label, bd=0, padx=24, pady=8, font=FONT_BODY, command=lambda item=tab_id: self._switch_tab(item))
            btn.pack(side=tk.LEFT)
            self._tab_buttons[tab_id] = btn

    def _build_left_panel(self, parent: tk.Widget) -> None:
        left = tk.Frame(parent, bg=COLORS["surface"], padx=10, pady=10, width=250)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        self._list_title = tk.Label(left, text="", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL)
        self._list_title.pack(anchor=tk.W)
        self._listbox = tk.Listbox(left, height=22, exportselection=False, font=("Microsoft YaHei UI", 11))
        self._listbox.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self._listbox.bind("<<ListboxSelect>>", lambda _event: self._on_select())
        row = tk.Frame(left, bg=COLORS["surface"])
        row.pack(fill=tk.X)
        ttk.Button(row, text="+ 新建", command=self._add_entry).pack(side=tk.LEFT)
        ttk.Button(row, text="- 删除", command=self._delete_entry).pack(side=tk.LEFT, padx=(6, 0))

    def _category(self) -> APICategory:
        return self._config.category(self._current_tab)

    def _current_entry(self) -> APIEntry | None:
        entries = self._category().entries
        return entries[self._selected_index] if 0 <= self._selected_index < len(entries) else None

    def _switch_tab(self, tab_id: str) -> None:
        self._save_fields_to_entry()
        self._current_tab = tab_id
        for item, button in self._tab_buttons.items():
            selected = item == tab_id
            button.configure(bg=COLORS["primary"] if selected else COLORS["surface"], fg="#FFFFFF" if selected else COLORS["muted"])
        category = self._category()
        self._selected_index = next(
            (index for index, entry in enumerate(category.entries) if entry.id == category.active_entry_id),
            0,
        )
        self._reload_list()
        self._render_right_panel()

    def _reload_list(self) -> None:
        category = self._category()
        self._list_title.configure(text=TAB_LABELS[self._current_tab])
        self._listbox.delete(0, tk.END)
        for index, entry in enumerate(category.entries):
            active = entry.id == category.active_entry_id
            prefix = "✦ " if active else "  "
            display = TYPE_LABELS.get(entry.config_type, entry.config_type)
            self._listbox.insert(tk.END, f"{prefix}{entry.label or display} [{display}]")
            if active:
                self._listbox.itemconfig(index, background=COLORS["primary"], foreground="#FFFFFF", selectbackground=COLORS["primary"], selectforeground="#FFFFFF")
        if category.entries:
            self._selected_index = min(self._selected_index, len(category.entries) - 1)
            self._listbox.selection_set(self._selected_index)

    def _on_select(self) -> None:
        selection = self._listbox.curselection()
        if not selection:
            return
        self._save_fields_to_entry()
        self._selected_index = int(selection[0])
        self._render_right_panel()

    def _render_right_panel(self) -> None:
        for child in self._right.winfo_children():
            child.destroy()
        entry = self._current_entry()
        if entry is None:
            tk.Label(self._right, text="没有可编辑配置", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_BODY).pack(anchor=tk.W)
            return
        self._load_entry_to_vars(entry)
        self._enable_button = tk.Button(self._right, bd=0, pady=8, font=("Microsoft YaHei UI", 10, "bold"), command=self._toggle_active)
        self._enable_button.pack(fill=tk.X)
        self._refresh_enable_button()
        tk.Label(self._right, text="名称", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W, pady=(12, 0))
        labels = [label for label, _config_type in TYPE_OPTIONS[self._current_tab]]
        box = ttk.Combobox(self._right, textvariable=self._type_var, values=labels, state="readonly")
        box.pack(fill=tk.X, pady=(2, 10))
        box.bind("<<ComboboxSelected>>", lambda _event: self._on_type_select())
        self._condition = tk.Frame(self._right, bg=COLORS["surface"])
        self._condition.pack(fill=tk.BOTH, expand=True)
        self._render_condition_fields()

    def _load_entry_to_vars(self, entry: APIEntry) -> None:
        label = TYPE_LABELS.get(entry.config_type, entry.config_type)
        for option_label, config_type in TYPE_OPTIONS[self._current_tab]:
            if config_type == entry.config_type:
                label = option_label
                break
        self._type_var.set(label)
        self._api_url_var.set(entry.api_url)
        self._api_key_var.set(entry.api_key)
        self._codex_toml_var.set(entry.codex_toml_path)
        self._codex_json_var.set(entry.codex_json_path)

    def _selected_type(self) -> str:
        selected = self._type_var.get()
        for label, config_type in TYPE_OPTIONS[self._current_tab]:
            if label == selected:
                return config_type
        return TYPE_OPTIONS[self._current_tab][0][1]

    def _on_type_select(self) -> None:
        entry = self._current_entry()
        if entry is not None:
            entry.config_type = self._selected_type()
            entry.label = TYPE_LABELS.get(entry.config_type, entry.label)
        self._render_condition_fields()

    def _render_condition_fields(self) -> None:
        for child in self._condition.winfo_children():
            child.destroy()
        config_type = self._selected_type()
        if config_type in LOCAL_CLI_TYPES:
            command = "claude" if "claude" in config_type else "codex"
            detected = shutil.which(f"{command}.cmd") or shutil.which(command) or "未检测到 PATH 命令"
            text = f"✓ 使用本地 {command} CLI，自动从 PATH 读取，无需填写参数\n检测路径：{detected}"
            tk.Label(self._condition, text=text, justify=tk.LEFT, bg=COLORS["surface_alt"], fg=COLORS["muted"], font=FONT_BODY, padx=10, pady=10).pack(fill=tk.X, pady=(0, 10))
        if config_type in CODEX_FILE_CONFIG_TYPES:
            self._file_row(".toml 配置文件路径", self._codex_toml_var)
            self._file_row(".json 配置文件路径", self._codex_json_var)
            tk.Label(self._condition, text="Codex CLI 需要在 ~/.codex/ 下配置 config.toml 和 instructions.md，此处只记录路径供参考。", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, wraplength=480, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 8))
        if config_type not in LOCAL_CLI_TYPES:
            _entry(self._condition, "API URL", self._api_url_var)
            _entry(self._condition, "API Key", self._api_key_var, secret=True)
        self._extra_text = None
        if config_type in CUSTOM_CONFIG_TYPES:
            tk.Label(self._condition, text="高级 JSON 配置（将与上方参数合并）", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
            self._extra_text = tk.Text(self._condition, height=4, bg=COLORS["surface_alt"], fg=COLORS["text"], relief=tk.FLAT, wrap=tk.WORD)
            self._extra_text.pack(fill=tk.X, pady=(2, 8))
            entry = self._current_entry()
            if entry and entry.extra_json:
                self._extra_text.insert("1.0", entry.extra_json)

    def _file_row(self, label: str, variable: tk.StringVar) -> None:
        tk.Label(self._condition, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        row = tk.Frame(self._condition, bg=COLORS["surface"])
        row.pack(fill=tk.X, pady=(2, 8))
        ttk.Entry(row, textvariable=variable).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="浏览", command=lambda: self._browse_file(variable)).pack(side=tk.LEFT, padx=(6, 0))

    def _browse_file(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(parent=self)
        if path:
            variable.set(path)

    def _save_fields_to_entry(self) -> bool:
        entry = self._current_entry()
        if entry is None:
            return True
        config_type = self._selected_type()
        extra_json = ""
        if config_type in CUSTOM_CONFIG_TYPES and getattr(self, "_extra_text", None) is not None:
            extra_json = self._extra_text.get("1.0", tk.END).strip()
            if extra_json:
                try:
                    data = json.loads(extra_json)
                except json.JSONDecodeError as exc:
                    messagebox.showerror("JSON 格式错误", f"高级 JSON 配置无效：{exc.msg}", parent=self)
                    return False
                if not isinstance(data, dict):
                    messagebox.showerror("JSON 格式错误", "高级 JSON 配置必须是 JSON 对象。", parent=self)
                    return False
        entry.config_type = config_type
        entry.label = TYPE_LABELS.get(config_type, entry.label)
        entry.api_url = self._api_url_var.get().strip()
        entry.api_key = self._api_key_var.get().strip()
        entry.extra_json = extra_json
        entry.codex_toml_path = self._codex_toml_var.get().strip()
        entry.codex_json_path = self._codex_json_var.get().strip()
        return True

    def _toggle_active(self) -> None:
        if not self._save_fields_to_entry():
            return
        entry = self._current_entry()
        if entry is None:
            return
        category = self._category()
        category.active_entry_id = "" if category.active_entry_id == entry.id else entry.id
        self._reload_list()
        self._refresh_enable_button()

    def _refresh_enable_button(self) -> None:
        entry = self._current_entry()
        active = bool(entry and self._category().active_entry_id == entry.id)
        self._enable_button.configure(
            text="✦ 已启用（点击取消）" if active else "启用此配置",
            bg=COLORS["success"] if active else COLORS["primary"],
            fg="#FFFFFF",
        )

    def _add_entry(self) -> None:
        if not self._save_fields_to_entry():
            return
        category = self._category()
        base = default_entries(self._current_tab)[0]
        existing = {entry.id for entry in category.entries}
        index = len(category.entries) + 1
        entry_id = f"{base.id}_{index}"
        while entry_id in existing:
            index += 1
            entry_id = f"{base.id}_{index}"
        category.entries.append(new_entry(entry_id, base.label, base.config_type, api_url=base.api_url, api_key=base.api_key, extra_json=base.extra_json))
        self._selected_index = len(category.entries) - 1
        self._reload_list()
        self._render_right_panel()

    def _delete_entry(self) -> None:
        category = self._category()
        if len(category.entries) <= 1:
            messagebox.showinfo("无法删除", "至少保留一条配置。", parent=self)
            return
        entry = self._current_entry()
        if entry is None or not messagebox.askyesno("删除配置", f"确定删除“{entry.label}”吗？", parent=self):
            return
        if category.active_entry_id == entry.id:
            category.active_entry_id = ""
        del category.entries[self._selected_index]
        self._selected_index = max(0, min(self._selected_index, len(category.entries) - 1))
        self._reload_list()
        self._render_right_panel()

    def _apply_changes(self, *, close: bool) -> None:
        if not self._save_fields_to_entry():
            return
        try:
            save_ai_config(self._config)
            if self._on_saved:
                self._on_saved()
            self._status_var.set("配置已保存")
            if close:
                self.after(300, self._close)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)

    def _close(self) -> None:
        self.destroy()
