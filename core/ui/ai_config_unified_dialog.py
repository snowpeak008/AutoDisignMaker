from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from core.config.ai_config import (
    AIConfig,
    AIProfile,
    ImageConfig,
    LLMConfig,
    create_default_config,
    load_ai_config,
    mask_secret,
    save_ai_config,
)
from core.config.validator import AIConfigValidator
from core.ui.theme import COLORS, FONT_BODY, FONT_SECTION, FONT_SMALL, center_window


ADAPTER_LABELS = {
    "openai": "OpenAI API",
    "codex": "Codex CLI",
    "claude": "Claude Code CLI",
    "local": "Local",
    "none": "禁用",
}


def _entry(parent: tk.Widget, label: str, variable: tk.StringVar, *, secret: bool = False) -> ttk.Entry:
    tk.Label(parent, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
    entry = ttk.Entry(parent, textvariable=variable, show="*" if secret else "")
    entry.pack(fill=tk.X, pady=(2, 8))
    return entry


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
        self._selected_index = 0
        self._validator = AIConfigValidator()
        self._validation_after_id: str | None = None
        self._validation_request_id = 0
        self._suspend_validation = False

        self._name_var = tk.StringVar()
        self._adapter_var = tk.StringVar(value="openai")
        self._llm_base_url_var = tk.StringVar()
        self._llm_api_key_var = tk.StringVar()
        self._llm_cli_path_var = tk.StringVar()
        self._llm_model_var = tk.StringVar()
        self._image_enabled_var = tk.BooleanVar(value=False)
        self._image_source_var = tk.StringVar(value="api")
        self._image_base_url_var = tk.StringVar()
        self._image_api_key_var = tk.StringVar()
        self._image_cli_path_var = tk.StringVar()
        self._image_model_var = tk.StringVar()
        self._status_var = tk.StringVar()
        self._validation_status_var = tk.StringVar(value="验证: 等待加载")
        self._install_validation_traces()

        self._build()
        self._reload_profiles()
        self._select_active()
        self.update_idletasks()
        center_window(self, 820, 650)
        self.deiconify()

    def _install_validation_traces(self) -> None:
        variables = (
            self._name_var, self._adapter_var, self._llm_base_url_var, self._llm_api_key_var,
            self._llm_cli_path_var, self._llm_model_var, self._image_enabled_var,
            self._image_source_var, self._image_base_url_var, self._image_api_key_var,
            self._image_cli_path_var, self._image_model_var,
        )
        for variable in variables:
            variable.trace_add("write", lambda *_: self._queue_form_validation())

    def _build(self) -> None:
        root = tk.Frame(self, bg=COLORS["bg"], padx=16, pady=14)
        root.pack(fill=tk.BOTH, expand=True)
        tk.Label(root, text="AI 配置管理", bg=COLORS["bg"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        body = tk.Frame(root, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        left = tk.Frame(body, bg=COLORS["surface"], padx=10, pady=10, width=230)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        tk.Label(left, text="Profile", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        self._listbox = tk.Listbox(left, height=22, exportselection=False)
        self._listbox.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self._listbox.bind("<<ListboxSelect>>", lambda _event: self._on_select())
        self._listbox.bind("<Double-Button-1>", lambda _event: self._activate_selected())
        row = tk.Frame(left, bg=COLORS["surface"])
        row.pack(fill=tk.X)
        ttk.Button(row, text="+ 新建", command=self._add_profile).pack(side=tk.LEFT)
        ttk.Button(row, text="- 删除", command=self._delete_profile).pack(side=tk.LEFT, padx=(6, 0))

        editor = tk.Frame(body, bg=COLORS["surface"], padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["border"])
        editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        _entry(editor, "名称", self._name_var)
        tk.Label(editor, text="适配器", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        adapter_box = ttk.Combobox(
            editor,
            textvariable=self._adapter_var,
            state="readonly",
            values=list(ADAPTER_LABELS.keys()),
        )
        adapter_box.pack(fill=tk.X, pady=(2, 10))
        adapter_box.bind("<<ComboboxSelected>>", lambda _event: self._on_adapter_change())
        self._validation_label = tk.Label(
            editor, textvariable=self._validation_status_var, bg=COLORS["success_soft"],
            fg=COLORS["success"], font=FONT_SMALL, anchor=tk.W, padx=8, pady=5,
        )
        self._validation_label.pack(fill=tk.X, pady=(0, 10))

        self._api_frame = tk.LabelFrame(editor, text="API LLM", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_BODY, padx=8, pady=8)
        self._api_frame.pack(fill=tk.X, pady=(0, 8))
        _entry(self._api_frame, "Base URL", self._llm_base_url_var)
        _entry(self._api_frame, "API Key", self._llm_api_key_var, secret=True)

        self._cli_frame = tk.LabelFrame(editor, text="CLI LLM", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_BODY, padx=8, pady=8)
        self._cli_frame.pack(fill=tk.X, pady=(0, 8))
        _entry(self._cli_frame, "CLI Path", self._llm_cli_path_var)

        _entry(editor, "模型", self._llm_model_var)
        image_frame = tk.LabelFrame(editor, text="图片生成", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_BODY, padx=8, pady=8)
        image_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(image_frame, text="启用图片生成", variable=self._image_enabled_var, command=self._refresh_visibility).pack(anchor=tk.W)
        tk.Label(image_frame, text="来源", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W, pady=(6, 0))
        source_box = ttk.Combobox(image_frame, textvariable=self._image_source_var, values=["api", "cli_builtin", "none"], state="readonly")
        source_box.pack(fill=tk.X, pady=(2, 8))
        source_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_visibility())
        _entry(image_frame, "Image Base URL", self._image_base_url_var)
        _entry(image_frame, "Image API Key", self._image_api_key_var, secret=True)
        _entry(image_frame, "Image CLI Path", self._image_cli_path_var)
        _entry(image_frame, "Image Model", self._image_model_var)

        footer = tk.Frame(root, bg=COLORS["bg"])
        footer.pack(fill=tk.X, pady=(12, 0))
        tk.Label(footer, textvariable=self._status_var, bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(footer, text="取消", command=self._close).pack(side=tk.RIGHT)
        ttk.Button(footer, text="保存", command=lambda: self._apply_changes(close=True)).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(footer, text="应用", command=lambda: self._apply_changes(close=False)).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(footer, text="激活", command=self._activate_selected).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(footer, text="测试连接", command=self._test_current).pack(side=tk.RIGHT, padx=(0, 8))

    def _reload_profiles(self) -> None:
        self._listbox.delete(0, tk.END)
        for index, profile in enumerate(self._config.profiles):
            active = profile.id == self._config.active_profile_id
            mark = "● " if active else "  "
            self._listbox.insert(tk.END, f"{mark}{profile.name} ({profile.adapter})")
            if active:
                try:
                    self._listbox.itemconfig(
                        index, background=COLORS["primary_soft"], foreground=COLORS["primary"],
                        selectbackground=COLORS["primary"], selectforeground="#FFFFFF",
                    )
                except tk.TclError:
                    pass

    def _select_active(self) -> None:
        active = self._config.active_profile
        self._selected_index = self._config.profiles.index(active)
        self._listbox.selection_clear(0, tk.END)
        self._listbox.selection_set(self._selected_index)
        self._load_profile(active)

    def _on_select(self) -> None:
        selection = self._listbox.curselection()
        if not selection:
            return
        self._save_fields_to_profile()
        self._selected_index = int(selection[0])
        self._load_profile(self._config.profiles[self._selected_index])

    def _load_profile(self, profile: AIProfile) -> None:
        self._suspend_validation = True
        try:
            self._name_var.set(profile.name)
            self._adapter_var.set(profile.adapter)
            self._llm_base_url_var.set(profile.llm.base_url)
            self._llm_api_key_var.set(profile.llm.api_key)
            self._llm_cli_path_var.set(profile.llm.cli_path or profile.adapter)
            self._llm_model_var.set(profile.llm.model)
            self._image_enabled_var.set(profile.image.enabled)
            self._image_source_var.set(profile.image.source)
            self._image_base_url_var.set(profile.image.base_url)
            self._image_api_key_var.set(profile.image.api_key)
            self._image_cli_path_var.set(profile.image.cli_path or "codex")
            self._image_model_var.set(profile.image.model)
        finally:
            self._suspend_validation = False
        self._refresh_visibility()
        self._schedule_validation(check_cli=True)

    def _save_fields_to_profile(self) -> AIProfile:
        profile = self._config.profiles[self._selected_index]
        adapter = self._adapter_var.get()
        llm_source = "cli" if adapter in {"codex", "claude"} else ("none" if adapter == "none" else "api")
        profile.name = self._name_var.get().strip() or profile.id
        profile.adapter = adapter
        profile.llm = LLMConfig(
            source=llm_source,
            provider="openai",
            base_url=self._llm_base_url_var.get().strip(),
            api_key=self._llm_api_key_var.get().strip(),
            cli_path=self._llm_cli_path_var.get().strip(),
            model=self._llm_model_var.get().strip() or "gpt-5.5",
        )
        profile.image = ImageConfig(
            enabled=self._image_enabled_var.get(),
            source=self._image_source_var.get(),
            provider="openai",
            base_url=self._image_base_url_var.get().strip(),
            api_key=self._image_api_key_var.get().strip(),
            cli_path=self._image_cli_path_var.get().strip(),
            model=self._image_model_var.get().strip() or "gpt-image-2",
        )
        return profile

    def _on_adapter_change(self) -> None:
        adapter = self._adapter_var.get()
        if adapter == "codex":
            self._llm_cli_path_var.set(self._llm_cli_path_var.get() or "codex")
            self._image_source_var.set("cli_builtin")
            self._image_cli_path_var.set("codex")
        elif adapter == "claude":
            self._llm_cli_path_var.set(self._llm_cli_path_var.get() or "claude")
            if self._image_source_var.get() == "cli_builtin":
                self._image_source_var.set("none")
        elif adapter == "none":
            self._image_enabled_var.set(False)
            self._image_source_var.set("none")
        self._refresh_visibility()
        self._schedule_validation(check_cli=True)

    def _refresh_visibility(self) -> None:
        adapter = self._adapter_var.get()
        api_enabled = adapter not in {"codex", "claude", "none"}
        cli_enabled = adapter in {"codex", "claude"}
        for frame, enabled in ((self._api_frame, api_enabled), (self._cli_frame, cli_enabled)):
            state = tk.NORMAL if enabled else tk.DISABLED
            for child in frame.winfo_children():
                try:
                    child.configure(state=state)
                except tk.TclError:
                    pass
        current_key = mask_secret(self._llm_api_key_var.get()) or "未填写"
        self._status_var.set(f"当前 Profile: {self._name_var.get() or '未命名'} / Key {current_key}")

    def _queue_form_validation(self) -> None:
        if self._suspend_validation:
            return
        self._refresh_visibility()
        self._schedule_validation(check_cli=False)

    def _schedule_validation(self, *, check_cli: bool) -> None:
        if self._validation_after_id:
            try:
                self.after_cancel(self._validation_after_id)
            except tk.TclError:
                pass
        delay = 120 if check_cli else 250
        self._validation_after_id = self.after(
            delay,
            lambda: self._run_validation(self._save_fields_to_profile(), check_cli=check_cli),
        )

    def _run_validation(self, profile: AIProfile, *, check_cli: bool, show_message: bool = False) -> None:
        self._validation_after_id = None
        self._validation_request_id += 1
        request_id = self._validation_request_id
        needs_thread = check_cli and profile.adapter in {"codex", "claude"}
        if needs_thread:
            self._validation_status_var.set("验证: 正在检测 CLI 可用性...")
            self._validation_label.configure(bg=COLORS["warning_soft"], fg=COLORS["warning"])

            def _worker() -> None:
                result = self._validator.validate_profile(profile, check_cli=True)
                try:
                    self.after(0, lambda: self._apply_validation_result(request_id, profile, result, show_message))
                except tk.TclError:
                    pass

            threading.Thread(target=_worker, daemon=True).start()
            return

        result = self._validator.validate_profile(profile, check_cli=check_cli)
        self._apply_validation_result(request_id, profile, result, show_message)

    def _apply_validation_result(self, request_id, profile: AIProfile, result, show_message: bool) -> None:
        if request_id != self._validation_request_id:
            return
        if result.errors:
            self._validation_status_var.set("✗ " + "；".join(result.errors[:2]))
            self._validation_label.configure(bg=COLORS["danger_soft"], fg=COLORS["danger"])
        elif result.warnings:
            cli_available = all(" available:" in item for item in result.warnings)
            prefix = "✓ " if cli_available else "⚠ "
            self._validation_status_var.set(prefix + "；".join(result.warnings[:2]))
            colors = (COLORS["success_soft"], COLORS["success"]) if cli_available else (
                COLORS["warning_soft"], COLORS["warning"]
            )
            self._validation_label.configure(bg=colors[0], fg=colors[1])
        else:
            self._validation_status_var.set(f"✓ 配置可用：{profile.name} ({profile.adapter})")
            self._validation_label.configure(bg=COLORS["success_soft"], fg=COLORS["success"])
        if show_message:
            if result.is_valid:
                messagebox.showinfo("测试完成", "当前配置验证通过。", parent=self)
            else:
                messagebox.showwarning("测试未通过", "；".join(result.errors[:3]), parent=self)

    def _test_current(self) -> None:
        profile = self._save_fields_to_profile()
        self._run_validation(profile, check_cli=True, show_message=True)

    def _activate_selected(self) -> None:
        profile = self._save_fields_to_profile()
        self._config.active_profile_id = profile.id
        self._reload_profiles()
        self._listbox.selection_clear(0, tk.END)
        self._listbox.selection_set(self._selected_index)
        self._schedule_validation(check_cli=False)
        self._show_toast("已激活，保存后生效")

    def _apply_changes(self, *, close: bool) -> None:
        try:
            self._save_fields_to_profile()
            save_ai_config(self._config)
            if self._on_saved:
                self._on_saved()
            self._reload_profiles()
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(self._selected_index)
            self._show_toast("配置已保存")
            self._schedule_validation(check_cli=True)
            if close:
                self.after(450, self._close)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)

    def _close(self) -> None:
        self._validation_request_id += 1
        if self._validation_after_id:
            try:
                self.after_cancel(self._validation_after_id)
            except tk.TclError:
                pass
            self._validation_after_id = None
        self.destroy()

    def _show_toast(self, text: str) -> None:
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.configure(bg=COLORS["success"])
        toast.transient(self)
        tk.Label(toast, text=text, bg=COLORS["success"], fg="#FFFFFF", font=FONT_SMALL, padx=14, pady=8).pack()
        self.update_idletasks()
        x = self.winfo_rootx() + self.winfo_width() - 180
        y = self.winfo_rooty() + 52
        toast.geometry(f"+{x}+{y}")
        toast.after(900, toast.destroy)

    def _add_profile(self) -> None:
        config = create_default_config()
        base = config.profiles[0]
        existing = {profile.id for profile in self._config.profiles}
        index = 1
        profile_id = "custom"
        while profile_id in existing:
            index += 1
            profile_id = f"custom_{index}"
        profile = AIProfile(
            id=profile_id, name=f"自定义配置 {index}", adapter=base.adapter,
            llm=LLMConfig(**base.llm.__dict__), image=ImageConfig(**base.image.__dict__),
        )
        self._config.profiles.append(profile)
        self._reload_profiles()
        self._selected_index = len(self._config.profiles) - 1
        self._listbox.selection_clear(0, tk.END)
        self._listbox.selection_set(self._selected_index)
        self._load_profile(profile)

    def _delete_profile(self) -> None:
        profile = self._config.profiles[self._selected_index]
        if len(self._config.profiles) <= 1:
            messagebox.showinfo("无法删除", "至少保留一个 Profile。", parent=self)
            return
        if profile.id == self._config.active_profile_id:
            messagebox.showwarning("无法删除", "不能删除当前激活的 Profile。", parent=self)
            return
        if not messagebox.askyesno("删除 Profile", f"确定删除“{profile.name}”吗？", parent=self):
            return
        del self._config.profiles[self._selected_index]
        self._selected_index = max(0, min(self._selected_index, len(self._config.profiles) - 1))
        self._reload_profiles()
        self._listbox.selection_set(self._selected_index)
        self._load_profile(self._config.profiles[self._selected_index])
