import json
import queue
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.paths import DRAFT_DIR as _DRAFT_DIR

_AUTOSAVE_DELAY_MS = 500
_AUTOSAVE_FILE = _DRAFT_DIR / "autosave_state.json"

from core.design.data_loader import load_project_data, runtime_project_root
from core.design.engine import DesignEngine, STATE_LABELS
from core.design.exporter import export_preview_lines, safe_file_name, write_export
from core.design.framework_memory import import_memory_archive
from core.design.gameplay_systems import parse_interview_answers_to_custom_systems
from core.design.project_templates import custom_template_path, list_project_templates, save_custom_template, target_scale_options
from core.design.profile_schema import PROFILE_FIELDS, field_label, option_label, value_from_label
from core.ui.ai_interview_window import AIInterviewWindow
from core.ui.theme import COLORS, FONT_BADGE, FONT_BODY, FONT_CARD, FONT_SECTION, FONT_SMALL, FONT_TITLE, center_window


def re_split_words(value):
    text = str(value or "").lower()
    return re.findall(r"[0-9a-z_]{2,}|[\u4e00-\u9fff]{2}", text)


class CommercialDesignApp(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(bg=COLORS["bg"])

        self.runtime_root = runtime_project_root()
        self.data = load_project_data()
        self.engine = DesignEngine(self.data)
        self.project_state = self.engine.empty_state()
        self.current_domain_id = self.engine.first_domain_id()
        self.search_text = tk.StringVar(value="")
        self.node_filter = tk.StringVar(value="全部")
        self.project_name = tk.StringVar(value=self.project_state["projectName"])
        self.export_format = tk.StringVar(value="markdown")
        self.status_text = tk.StringVar(value="就绪")
        self.profile_vars = {
            key: tk.StringVar(value=option_label(key, value))
            for key, value in self.project_state["profile"].items()
        }
        self.node_widgets = {}
        self.option_group_widgets = {}
        self.expanded_note_nodes = set()
        self.expanded_risk_nodes = set()
        self.expanded_na_nodes = set()
        self.expanded_gameplay_interview = False
        self.search_after_id = None
        self.ai_window = None
        self._autosave_after_id = None
        self._saved_state_hash: str | None = None
        self._state_version = 0
        self._last_results_version: tuple | None = None

        self.configure_style()
        self.build_ui()
        self.bind("<Control-Shift-M>", self.import_memory_archive_dialog)
        self.render()
        self.mark_saved()  # anchor empty-state baseline

    def configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=FONT_BODY, background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TButton", padding=(10, 6), font=FONT_BODY)
        style.configure("TEntry", padding=(6, 5))
        style.configure("TCombobox", padding=(6, 5))
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 8), font=FONT_SMALL)
        style.configure("Horizontal.TProgressbar", troughcolor=COLORS["surface_alt"], background=COLORS["primary"])

    def build_ui(self):
        self.build_topbar()
        self.build_workspace()
        self.build_statusbar()

    def build_topbar(self):
        topbar = tk.Frame(self, bg=COLORS["surface"], padx=16, pady=12)
        topbar.pack(side=tk.TOP, fill=tk.X)

        title_box = tk.Frame(topbar, bg=COLORS["surface"])
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(title_box, text="Commercial Game Design Decision Tool", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        tk.Label(title_box, text="完整商业游戏设计决策工具", bg=COLORS["surface"], fg=COLORS["text"], font=("Microsoft YaHei UI", 18, "bold")).pack(anchor=tk.W)
        tk.Label(
            title_box,
            text="独立项目：16 个领域全覆盖，二级节点决策，三级 checklist，节点描述与纯文本导出。",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W, pady=(3, 0))

        actions = tk.Frame(topbar, bg=COLORS["surface"])
        actions.pack(side=tk.RIGHT)
        tk.Label(actions, text="项目名称", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(actions, textvariable=self.project_name, width=26).grid(row=1, column=0, padx=(0, 8))
        tk.Label(actions, text="导出", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).grid(row=0, column=1, sticky=tk.W)
        ttk.Combobox(actions, textvariable=self.export_format, values=["markdown", "json", "txt", "text", "prompt"], state="readonly", width=10).grid(row=1, column=1, padx=(0, 8))
        ttk.Button(actions, text="导出", command=self.export_project).grid(row=1, column=2, padx=(0, 8))
        ttk.Button(actions, text="存档管理", command=self.save_project).grid(row=1, column=3, padx=(0, 8))
        ttk.Button(actions, text="模板查看", command=self.open_template_viewer).grid(row=1, column=4, padx=(0, 8))
        ttk.Button(actions, text="另存为模板", command=self.open_save_template_dialog).grid(row=1, column=5, padx=(0, 8))
        ttk.Button(actions, text="重置", command=self.reset_project).grid(row=1, column=6)

    def build_workspace(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        left = self.panel(paned, 10)
        middle = self.panel(paned, 10)
        right = self.panel(paned, 10)
        paned.add(left, weight=2)
        paned.add(middle, weight=5)
        paned.add(right, weight=3)

        self.build_domain_panel(left)
        self.build_node_panel(middle)
        self.build_result_panel(right)

    def build_domain_panel(self, parent):
        tk.Label(parent, text="领域总览", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        tk.Label(parent, text="16 个领域全部保留；项目画像只影响排序和风险提示。", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, wraplength=280).pack(anchor=tk.W, pady=(4, 10))

        profile_frame = tk.LabelFrame(parent, text="项目画像", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SMALL, padx=8, pady=8)
        profile_frame.pack(fill=tk.X, pady=(0, 10))
        for row, field in enumerate(PROFILE_FIELDS):
            key = field["id"]
            labels = [label for _, label in field["options"]]
            tk.Label(profile_frame, text=field["label"], bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).grid(row=row, column=0, sticky=tk.W, pady=2)
            var = self.profile_vars.setdefault(key, tk.StringVar(value=option_label(key, "unknown")))
            box = ttk.Combobox(profile_frame, textvariable=var, values=labels, state="readonly", width=18)
            box.grid(row=row, column=1, sticky=tk.EW, pady=2)
            box.bind("<<ComboboxSelected>>", lambda event: self.on_profile_change())

        self.domain_canvas, self.domain_frame = self.scroll_area(parent)

    def build_node_panel(self, parent):
        from core.ui.embedded_interview import EmbeddedInterviewPanel
        paned = tk.PanedWindow(parent, orient=tk.VERTICAL, sashrelief=tk.FLAT,
                               sashwidth=4, bg=COLORS["border"])
        paned.pack(fill=tk.BOTH, expand=True)
        top = self.panel(paned, 10)
        _ai = EmbeddedInterviewPanel(paned, self)
        paned.add(top, stretch="always")
        paned.add(_ai, minsize=200, stretch="always")

        header = tk.Frame(top, bg=COLORS["surface"])
        header.pack(fill=tk.X)
        self.domain_title = tk.Label(header, text="", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_TITLE)
        self.domain_title.pack(anchor=tk.W)
        self.domain_desc = tk.Label(header, text="", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_BODY, wraplength=760, justify=tk.LEFT)
        self.domain_desc.pack(anchor=tk.W, pady=(4, 8))

        tools = tk.Frame(top, bg=COLORS["surface"])
        tools.pack(fill=tk.X, pady=(0, 8))
        search_entry = ttk.Entry(tools, textvariable=self.search_text)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        search_entry.bind("<Return>", lambda event: self.render_nodes())
        search_entry.bind("<KeyRelease>", self.on_search_key_release)
        ttk.Button(tools, text="搜索", command=self.render_nodes).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(tools, text="清空", command=self.clear_search).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(tools, text="筛选", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 4))
        filter_box = ttk.Combobox(
            tools,
            textvariable=self.node_filter,
            values=["全部", "已决策", "未完成", "有风险", "不适用", "L4 未完整"],
            state="readonly",
            width=12,
        )
        filter_box.pack(side=tk.LEFT)
        filter_box.bind("<<ComboboxSelected>>", lambda event: self.render_nodes())

        self.node_canvas, self.node_frame = self.scroll_area(top)

    def build_result_panel(self, parent):
        self.tabs = ttk.Notebook(parent)
        self.tabs.pack(fill=tk.BOTH, expand=True)
        self.summary_text = self.text_tab("摘要")
        self.gap_text = self.text_tab("缺失项")
        self.risk_text = self.text_tab("风险")
        self.validation_text = self.text_tab("校验")

    def build_statusbar(self):
        bar = tk.Frame(self, bg=COLORS["dark"], padx=12, pady=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(bar, textvariable=self.status_text, bg=COLORS["dark"], fg="#FFFFFF", font=FONT_SMALL).pack(side=tk.LEFT)

    def panel(self, parent, padding):
        frame = tk.Frame(parent, bg=COLORS["surface"], padx=padding, pady=padding, highlightthickness=1, highlightbackground=COLORS["border"])
        return frame

    def scroll_area(self, parent):
        wrapper = tk.Frame(parent, bg=COLORS["surface"])
        wrapper.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(wrapper, bg=COLORS["surface"], bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient=tk.VERTICAL, command=canvas.yview)
        frame = tk.Frame(canvas, bg=COLORS["surface"])
        window = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind("<Enter>", lambda event: canvas.bind_all("<MouseWheel>", lambda e, c=canvas: c.yview_scroll(int(-1 * (e.delta / 120)), "units")))
        canvas.bind("<Leave>", lambda event: canvas.unbind_all("<MouseWheel>"))
        return canvas, frame

    def text_tab(self, title):
        frame = tk.Frame(self.tabs, bg=COLORS["surface"])
        text = tk.Text(frame, bg=COLORS["surface"], fg=COLORS["text"], bd=0, highlightthickness=0, wrap=tk.WORD, font=FONT_BODY, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tabs.add(frame, text=title)
        return text

    def runtime_subdir(self, name):
        path = self.runtime_root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path_inside_runtime_root(self, path):
        try:
            Path(path).resolve().relative_to(self.runtime_root.resolve())
            return True
        except (OSError, ValueError):
            return False

    def ensure_project_local_path(self, path, label):
        if self.path_inside_runtime_root(path):
            return True
        messagebox.showwarning(
            "项目内运行",
            f"{label}必须位于当前项目目录内：\n{self.runtime_root}",
        )
        return False

    def clear_expanded_nodes(self):
        self.expanded_note_nodes.clear()
        self.expanded_risk_nodes.clear()
        self.expanded_na_nodes.clear()
        self.expanded_gameplay_interview = False

    def bind_click_recursive(self, widget, command):
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass
        widget.bind("<Button-1>", command)
        for child in widget.winfo_children():
            self.bind_click_recursive(child, command)

    def _schedule_autosave(self) -> None:
        if self._autosave_after_id:
            self.after_cancel(self._autosave_after_id)
        self._autosave_after_id = self.after(_AUTOSAVE_DELAY_MS, self._do_autosave)

    def _do_autosave(self) -> None:
        self._autosave_after_id = None
        try:
            _AUTOSAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _AUTOSAVE_FILE.write_text(
                json.dumps(self.project_state, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _flush_autosave(self) -> None:
        if self._autosave_after_id:
            self.after_cancel(self._autosave_after_id)
            self._autosave_after_id = None
        self._do_autosave()

    def _project_state_hash(self) -> str:
        import hashlib
        return hashlib.sha256(
            json.dumps(self.project_state, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def mark_saved(self) -> None:
        """Call after every formal save or load to anchor the 'no unsaved changes' baseline."""
        self._saved_state_hash = self._project_state_hash()

    def _mark_state_changed(self) -> None:
        self._state_version += 1
        self._last_results_version = None

    def render(self, preserve_node_scroll=False):
        self.project_state["projectName"] = self.project_name.get()
        self.project_state["profile"] = self.current_profile_values()
        self.project_state = self.engine.normalize_state(self.project_state)
        self.sync_profile_labels()
        self._last_results_version = None
        self.render_domains()
        self.render_nodes(preserve_scroll=preserve_node_scroll)
        self.render_results()
        self._schedule_autosave()

    def canvas_yview_position(self, canvas):
        try:
            return canvas.yview()[0]
        except tk.TclError:
            return 0

    def restore_canvas_yview(self, canvas, position):
        try:
            canvas.yview_moveto(position)
        except tk.TclError:
            pass

    def render_domains(self):
        for child in self.domain_frame.winfo_children():
            child.destroy()
        focus_domains = self.engine.profile_focus_domains(self.project_state)
        for domain_doc in self.engine.domains:
            domain = domain_doc["domain"]
            coverage = self.engine.domain_coverage(domain["id"], self.project_state)
            l4_progress = self.engine.domain_l4_progress(domain["id"], self.project_state)
            focused = domain["id"] in focus_domains
            current = domain["id"] == self.current_domain_id
            bg = COLORS["primary_soft"] if current else (COLORS["warning_soft"] if focused else COLORS["surface_alt"])
            border = COLORS["primary"] if current else (COLORS["warning"] if focused else COLORS["border"])
            card = tk.Frame(self.domain_frame, bg=bg, highlightthickness=1, highlightbackground=border, padx=10, pady=8, cursor="hand2")
            card.pack(fill=tk.X, pady=(0, 8))
            tk.Label(card, text=domain["name"], bg=bg, fg=COLORS["text"], font=FONT_CARD).pack(anchor=tk.W)
            tk.Label(card, text=f"节点 {coverage['nodePercent']}% / 子项 {coverage['checklistPercent']}%", bg=bg, fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W, pady=(4, 0))
            l4_text = f"L4 {l4_progress['done']}/{l4_progress['total']}" if l4_progress["total"] else "L4 -"
            tk.Label(card, text=l4_text, bg=bg, fg=COLORS["warning"] if l4_progress["gapNodes"] else COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W, pady=(2, 0))
            progress = ttk.Progressbar(card, maximum=100, value=coverage["checklistPercent"])
            progress.pack(fill=tk.X, pady=(6, 0))
            self.bind_click_recursive(card, lambda event, domain_id=domain["id"]: self.change_domain(domain_id))

    def node_matches_filter(self, node, filter_label):
        effective_state = self.engine.effective_node_state(node, self.project_state)
        node_state = self.project_state["nodes"].get(node["id"], {})
        if filter_label == "已决策":
            return effective_state != "not_started" or bool(node_state.get("riskNote", "").strip())
        if filter_label == "未完成":
            return effective_state not in ("completed", "not_applicable")
        if filter_label == "有风险":
            if node_state.get("riskNote", "").strip():
                return True
            return any(
                self.engine.active_option_conflicts(self.project_state, node["id"], item["id"])
                for item in node.get("checklist", [])
            )
        if filter_label == "不适用":
            return effective_state == "not_applicable"
        if filter_label == "L4 未完整":
            return self.engine.node_has_l4_gap(node, self.project_state)
        return True

    def render_nodes(self, preserve_scroll=False):
        scroll_position = self.canvas_yview_position(self.node_canvas) if preserve_scroll else 0
        for child in self.node_frame.winfo_children():
            child.destroy()
        self.node_widgets = {}
        self.option_group_widgets = {}
        domain_doc = self.engine.domain_by_id.get(self.current_domain_id)
        if not domain_doc:
            return
        domain = domain_doc["domain"]
        coverage = self.engine.domain_coverage(domain["id"], self.project_state)
        self.domain_title.configure(text=domain["name"])
        self.domain_desc.configure(text=f"{domain.get('description', '')}  节点覆盖率 {coverage['nodePercent']}%，三级子项覆盖率 {coverage['checklistPercent']}%。")

        if domain["id"] == "gameplay_system_design":
            self.make_gameplay_systems_panel()

        search = self.search_text.get().strip().lower()
        filter_label = self.node_filter.get()
        visible_count = 0
        for node in self.engine.domain_nodes(domain["id"]):
            haystack = self.engine.node_search_index.get(node["id"], "")
            if search and search not in haystack:
                continue
            if not self.node_matches_filter(node, filter_label):
                continue
            self.make_node_card(node).pack(fill=tk.X, pady=(0, 10))
            visible_count += 1
        if visible_count == 0:
            tk.Label(
                self.node_frame,
                text="当前搜索或筛选下没有节点。",
                bg=COLORS["surface"],
                fg=COLORS["muted"],
                font=FONT_BODY,
                pady=16,
            ).pack(fill=tk.X)
        if preserve_scroll:
            self.node_canvas.update_idletasks()
            self.after_idle(lambda position=scroll_position: self.restore_canvas_yview(self.node_canvas, position))

    def make_gameplay_systems_panel(self):
        state = self.engine.gameplay_systems_state(self.project_state)
        selected_ids = set(state.get("selected", []))
        weight_summary = self.engine.gameplay_weight_summary(self.project_state)
        validation = self.engine.gameplay_validation_messages(self.project_state)

        panel = tk.Frame(
            self.node_frame,
            bg=COLORS["surface_alt"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        panel.pack(fill=tk.X, pady=(0, 12))

        header = tk.Frame(panel, bg=COLORS["surface_alt"])
        header.pack(fill=tk.X)
        tk.Label(header, text="玩法系统总览", bg=COLORS["surface_alt"], fg=COLORS["text"], font=FONT_SECTION).pack(side=tk.LEFT)
        summary_fg = COLORS["success"] if weight_summary["status"] == "ok" else COLORS["warning"]
        tk.Label(
            header,
            text=f"已选 {len(selected_ids)} 个 / 总占比 {weight_summary['total']}%",
            bg=COLORS["surface_alt"],
            fg=summary_fg,
            font=FONT_SMALL,
        ).pack(side=tk.RIGHT)
        tk.Label(
            panel,
            text="先确认项目需要的玩法系统，再填写占比和一句话核心循环；映射描述是定义层，核心循环是行为层。",
            bg=COLORS["surface_alt"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            wraplength=760,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, fill=tk.X, pady=(4, 8))

        if validation:
            tk.Label(
                panel,
                text="；".join(validation),
                bg=COLORS["warning_soft"],
                fg=COLORS["warning"],
                font=FONT_SMALL,
                padx=8,
                pady=4,
                wraplength=730,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, fill=tk.X, pady=(0, 8))

        options_frame = tk.Frame(panel, bg=COLORS["surface_alt"])
        options_frame.pack(fill=tk.X)
        options_frame.grid_columnconfigure(0, weight=1)
        options_frame.grid_columnconfigure(1, weight=1)
        for index, option in enumerate(self.engine.gameplay_all_options(self.project_state)):
            self.make_gameplay_option_card(options_frame, option, option["id"] in selected_ids, index)

        self.make_custom_gameplay_entry(panel)
        self.make_gameplay_interview_panel(panel)
        self.make_gameplay_global_view(panel)

    def make_gameplay_option_card(self, parent, option, selected, index):
        state = self.engine.gameplay_systems_state(self.project_state)
        system_id = option["id"]
        weights = state.setdefault("weights", {})
        core_loops = state.setdefault("coreLoops", {})
        bg = COLORS["primary_soft"] if selected else COLORS["surface"]
        border = COLORS["primary"] if selected else COLORS["border"]
        card = tk.Frame(parent, bg=bg, highlightbackground=border, highlightthickness=1, padx=8, pady=7)
        card.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 6) if index % 2 == 0 else (6, 0), pady=(0, 8))

        header = tk.Frame(card, bg=bg)
        header.pack(fill=tk.X)
        var = tk.BooleanVar(value=selected)
        tk.Checkbutton(
            header,
            text=option.get("name", system_id),
            variable=var,
            bg=bg,
            fg=COLORS["primary"] if selected else COLORS["text"],
            activebackground=bg,
            activeforeground=COLORS["primary"],
            selectcolor=COLORS["surface"],
            font=FONT_CARD if selected else FONT_SMALL,
            command=lambda option_id=system_id, check_var=var: self.on_gameplay_system_toggle(option_id, check_var.get()),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        source = "custom" if option.get("category") == "custom" else option.get("category", "preset")
        tk.Label(
            header,
            text=source,
            bg=COLORS["primary"] if selected else COLORS["surface_alt"],
            fg="#FFFFFF" if selected else COLORS["muted"],
            font=FONT_BADGE,
            padx=6,
            pady=2,
        ).pack(side=tk.RIGHT, padx=(6, 0))
        if option.get("category") == "custom":
            ttk.Button(header, text="删除", command=lambda option_id=system_id: self.delete_custom_gameplay_system(option_id)).pack(side=tk.RIGHT)

        if selected:
            tk.Label(
                card,
                text=f"映射描述（定义层）：{option.get('mapping_desc', '')}",
                bg=bg,
                fg=COLORS["muted"],
                font=FONT_SMALL,
                wraplength=330,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, fill=tk.X, pady=(4, 0))

            fields = tk.Frame(card, bg=bg)
            fields.pack(fill=tk.X, pady=(6, 0))
            tk.Label(fields, text="占比 %", bg=bg, fg=COLORS["muted"], font=FONT_SMALL).grid(row=0, column=0, sticky=tk.W)
            weight_var = tk.StringVar(value=str(weights.get(system_id, {}).get("weight", "")))
            weight_entry = ttk.Entry(fields, textvariable=weight_var, width=7)
            weight_entry.grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
            weight_entry.bind("<FocusOut>", lambda event, option_id=system_id, var=weight_var: self.update_gameplay_weight(option_id, var.get()))
            weight_entry.bind("<Return>", lambda event, option_id=system_id, var=weight_var: self.update_gameplay_weight(option_id, var.get()))

            tk.Label(fields, text="核心循环描述（行为层，一句话）", bg=bg, fg=COLORS["muted"], font=FONT_SMALL).grid(row=0, column=1, sticky=tk.W)
            loop_var = tk.StringVar(value=core_loops.get(system_id, ""))
            loop_entry = ttk.Entry(fields, textvariable=loop_var)
            loop_entry.grid(row=1, column=1, sticky=tk.EW)
            fields.grid_columnconfigure(1, weight=1)
            loop_entry.bind("<FocusOut>", lambda event, option_id=system_id, var=loop_var: self.update_gameplay_core_loop(option_id, var.get()))
            loop_entry.bind("<Return>", lambda event, option_id=system_id, var=loop_var: self.update_gameplay_core_loop(option_id, var.get()))

            overlap = self.gameplay_description_overlap(option.get("mapping_desc", ""), core_loops.get(system_id, ""))
            if overlap:
                tk.Label(
                    card,
                    text="映射描述与核心循环描述语义接近，可考虑合并或改写其中一个。",
                    bg=COLORS["warning_soft"],
                    fg=COLORS["warning"],
                    font=FONT_SMALL,
                    padx=6,
                    pady=3,
                    wraplength=330,
                    justify=tk.LEFT,
                ).pack(anchor=tk.W, fill=tk.X, pady=(6, 0))

    def make_custom_gameplay_entry(self, parent):
        frame = tk.Frame(parent, bg=COLORS["surface_alt"])
        frame.pack(fill=tk.X, pady=(2, 8))
        tk.Label(frame, text="自定义系统", bg=COLORS["surface_alt"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        row = tk.Frame(frame, bg=COLORS["surface_alt"])
        row.pack(fill=tk.X, pady=(4, 0))
        name_var = tk.StringVar(value="")
        entry = ttk.Entry(row, textvariable=name_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda event, var=name_var: self.add_custom_gameplay_system(var))
        ttk.Button(row, text="添加", command=lambda var=name_var: self.add_custom_gameplay_system(var)).pack(side=tk.LEFT)

    def make_gameplay_interview_panel(self, parent):
        state = self.engine.gameplay_systems_state(self.project_state)
        interview = state.setdefault("interview", {})
        frame = tk.Frame(parent, bg=COLORS["surface_alt"])
        frame.pack(fill=tk.X, pady=(0, 8))
        row = tk.Frame(frame, bg=COLORS["surface_alt"])
        row.pack(fill=tk.X)
        tk.Label(row, text="AI 访谈兜底", bg=COLORS["surface_alt"], fg=COLORS["text"], font=FONT_CARD).pack(side=tk.LEFT)
        label = "收起" if self.expanded_gameplay_interview else "展开"
        ttk.Button(row, text=label, command=self.toggle_gameplay_interview).pack(side=tk.RIGHT)
        if not self.expanded_gameplay_interview:
            return

        for question in interview.get("questions", [])[:3]:
            tk.Label(frame, text=f"- {question}", bg=COLORS["surface_alt"], fg=COLORS["muted"], font=FONT_SMALL, wraplength=740, justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 0))
        text = tk.Text(
            frame,
            height=4,
            wrap=tk.WORD,
            font=FONT_SMALL,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        text.insert("1.0", "\n".join(interview.get("answers", [])))
        text.pack(fill=tk.X, pady=(6, 0))
        buttons = tk.Frame(frame, bg=COLORS["surface_alt"])
        buttons.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(buttons, text="保存回答", command=lambda widget=text: self.save_gameplay_interview_answers(widget.get("1.0", tk.END))).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="解析为自定义系统", command=lambda widget=text: self.apply_gameplay_interview_answers(widget.get("1.0", tk.END))).pack(side=tk.LEFT)

    def make_gameplay_global_view(self, parent):
        systems = self.engine.gameplay_selected_systems(self.project_state, sort_by_weight=True)
        frame = tk.LabelFrame(parent, text="全局视图（只读，按占比排序）", bg=COLORS["surface_alt"], fg=COLORS["text"], font=FONT_SMALL, padx=8, pady=8)
        frame.pack(fill=tk.X)
        if not systems:
            tk.Label(frame, text="未选任何玩法系统时暂无全局视图。", bg=COLORS["surface_alt"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
            return
        for system in systems:
            weight = system.get("weight", "")
            weight_text = "未填写" if weight in ("", None) else f"{weight}%"
            loop = system.get("core_loop") or "未填写核心循环"
            tk.Label(
                frame,
                text=f"{system.get('name', system.get('id', ''))} · {weight_text} · {loop}",
                bg=COLORS["surface_alt"],
                fg=COLORS["text"],
                font=FONT_SMALL,
                wraplength=740,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, fill=tk.X, pady=(0, 4))

    def make_node_card(self, node):
        node_state = self.project_state["nodes"].get(node["id"], {})
        effective_state = self.engine.effective_node_state(node, self.project_state)
        progress = self.engine.node_progress(node, self.project_state)
        l4_progress = self.engine.node_l4_progress(node, self.project_state)
        palette = self.node_palette(effective_state)
        card = tk.Frame(self.node_frame, bg=palette["bg"], highlightbackground=palette["border"], highlightthickness=1, padx=12, pady=10)

        header = tk.Frame(card, bg=palette["bg"])
        header.pack(fill=tk.X)
        tk.Label(header, text=node["name"], bg=palette["bg"], fg=palette["fg"], font=FONT_CARD).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header, text=f"{progress['done']}/{progress['total']}", bg=palette["bg"], fg=palette["muted"], font=FONT_SMALL).pack(side=tk.RIGHT, padx=(8, 0))
        if l4_progress["total"]:
            l4_bg = COLORS["warning"] if l4_progress["missingItems"] else COLORS["success"]
            tk.Label(
                header,
                text=f"L4 {l4_progress['done']}/{l4_progress['total']}",
                bg=l4_bg,
                fg="#FFFFFF",
                font=FONT_SMALL,
                padx=8,
                pady=3,
            ).pack(side=tk.RIGHT, padx=(8, 0))
        if node.get("roleClass") in {"system_concrete", "content_concrete"}:
            entity_count = len(node_state.get("designEntities", []))
            error_count = len(node_state.get("entityValidationErrors", []))
            l5_bg = COLORS["warning"] if error_count or entity_count == 0 else COLORS["success"]
            tk.Label(
                header,
                text=f"L5 {entity_count}",
                bg=l5_bg,
                fg="#FFFFFF",
                font=FONT_SMALL,
                padx=8,
                pady=3,
            ).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Label(
            header,
            text=STATE_LABELS.get(effective_state, "未选择"),
            bg=palette["marker_bg"],
            fg=palette["marker_fg"],
            font=FONT_SMALL,
            padx=8,
            pady=3,
        ).pack(side=tk.RIGHT)

        tk.Label(card, text=node.get("description", ""), bg=palette["bg"], fg=COLORS["muted"], font=FONT_BODY, wraplength=760, justify=tk.LEFT).pack(anchor=tk.W, fill=tk.X, pady=(7, 8))

        checklist_frame = tk.Frame(card, bg=palette["bg"])
        checklist_frame.pack(fill=tk.X)
        for item in node.get("checklist", []):
            checked = bool(node_state.get("checklist", {}).get(item["id"]))
            disabled = effective_state == "not_applicable"
            self.make_checklist_item_card(checklist_frame, node["id"], item, checked, disabled)

        self.node_widgets[node["id"]] = {}

        if node.get("roleClass") in {"system_concrete", "content_concrete"}:
            self.make_design_entities_editor(card, node, palette)

        action_row = tk.Frame(card, bg=palette["bg"])
        action_row.pack(fill=tk.X, pady=(8, 0))
        has_note = bool(node_state.get("designNote", "").strip())
        note_label = "隐藏描述" if node["id"] in self.expanded_note_nodes else ("查看描述" if has_note else "补充描述")
        ttk.Button(
            action_row,
            text=note_label,
            command=lambda node_id=node["id"]: self.toggle_note_editor(node_id),
        ).pack(side=tk.LEFT, padx=(0, 8))

        risk_var = tk.BooleanVar(value=bool(node_state.get("riskNote", "").strip()) or node["id"] in self.expanded_risk_nodes)
        tk.Checkbutton(
            action_row,
            text="标记风险",
            variable=risk_var,
            bg=palette["bg"],
            fg=COLORS["muted"],
            activebackground=palette["bg"],
            font=FONT_SMALL,
            command=lambda node_id=node["id"], check_var=risk_var: self.on_risk_toggle(node_id, check_var.get()),
        ).pack(side=tk.LEFT)

        if node["id"] in self.expanded_note_nodes:
            note_box = self.note_box(card, "简单设计描述", node_state.get("designNote", ""), lambda value, node_id=node["id"]: self.update_node_text(node_id, "designNote", value))
            self.node_widgets[node["id"]]["note"] = note_box

        if risk_var.get():
            risk_box = self.note_box(card, "风险说明", node_state.get("riskNote", ""), lambda value, node_id=node["id"]: self.update_node_text(node_id, "riskNote", value))
            self.node_widgets[node["id"]]["risk"] = risk_box

        not_applicable_var = tk.BooleanVar(value=effective_state == "not_applicable")
        na_frame = tk.Frame(card, bg=palette["bg"])
        na_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Checkbutton(
            na_frame,
            text="此节点不适用",
            variable=not_applicable_var,
            bg=palette["bg"],
            fg=COLORS["muted"],
            activebackground=palette["bg"],
            font=FONT_SMALL,
            command=lambda node_id=node["id"], check_var=not_applicable_var: self.on_not_applicable_change(node_id, check_var.get()),
        ).pack(anchor=tk.W)
        if effective_state == "not_applicable":
            na_box = self.note_box(card, "不适用原因", node_state.get("notApplicableReason", ""), lambda value, node_id=node["id"]: self.update_node_text(node_id, "notApplicableReason", value))
            self.node_widgets[node["id"]]["na"] = na_box
        return card

    def make_design_entities_editor(self, parent, node, palette):
        node_id = node["id"]
        node_state = self.project_state["nodes"].setdefault(node_id, {})
        frame = tk.LabelFrame(
            parent,
            text="L5 设计实体",
            bg=palette["bg"],
            fg=COLORS["text"],
            font=FONT_SMALL,
            padx=8,
            pady=8,
        )
        frame.pack(fill=tk.X, pady=(8, 0))

        errors = node_state.get("entityValidationErrors", [])
        status_text = f"{node.get('roleClass', '')} / 实体 {len(node_state.get('designEntities', []))} 个"
        if errors:
            status_text += f" / 校验警告 {len(errors)} 条"
        tk.Label(frame, text=status_text, bg=palette["bg"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)

        text = tk.Text(
            frame,
            height=7,
            wrap=tk.NONE,
            font=("Consolas", 9),
            bg=COLORS["surface"],
            fg=COLORS["text"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        text.insert("1.0", json.dumps(node_state.get("designEntities", []), ensure_ascii=False, indent=2))
        text.pack(fill=tk.X, pady=(6, 0))

        button_row = tk.Frame(frame, bg=palette["bg"])
        button_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(
            button_row,
            text="保存实体 JSON",
            command=lambda node_id=node_id, widget=text: self.update_node_design_entities(node_id, widget.get("1.0", tk.END)),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            button_row,
            text="清空实体",
            command=lambda node_id=node_id: self.clear_node_design_entities(node_id),
        ).pack(side=tk.LEFT)

        if errors:
            error_lines = []
            for error in errors[:5]:
                error_lines.append(f"- {error.get('path', '')}: {error.get('message', '')}")
            if len(errors) > 5:
                error_lines.append(f"- 还有 {len(errors) - 5} 条未显示。")
            tk.Label(
                frame,
                text="\n".join(error_lines),
                bg=COLORS["warning_soft"],
                fg=COLORS["warning"],
                font=FONT_SMALL,
                justify=tk.LEFT,
                wraplength=700,
                padx=8,
                pady=4,
            ).pack(anchor=tk.W, fill=tk.X, pady=(6, 0))
        self.node_widgets.setdefault(node_id, {})["entities"] = text

    def make_checklist_item_card(self, parent, node_id, item, checked, disabled):
        if disabled:
            bg = COLORS["surface_alt"]
            border = COLORS["border_strong"]
            title_fg = COLORS["muted"]
            desc_fg = COLORS["muted"]
        elif checked:
            bg = COLORS["primary_soft"]
            border = COLORS["primary"]
            title_fg = COLORS["primary"]
            desc_fg = COLORS["text"]
        else:
            bg = COLORS["surface"]
            border = COLORS["border"]
            title_fg = COLORS["text"]
            desc_fg = COLORS["muted"]

        block = tk.Frame(parent, bg=bg, highlightbackground=border, highlightthickness=1, padx=10, pady=8)
        block.pack(fill=tk.X, pady=(0, 7))

        header = tk.Frame(block, bg=bg)
        header.pack(fill=tk.X)

        var = tk.BooleanVar(value=checked)
        cb = tk.Checkbutton(
            header,
            text=item["label"],
            variable=var,
            bg=bg,
            fg=title_fg,
            activebackground=bg,
            activeforeground=title_fg,
            selectcolor=COLORS["surface"],
            font=FONT_CARD if checked else FONT_SMALL,
            anchor=tk.W,
            state=tk.DISABLED if disabled else tk.NORMAL,
            command=lambda item_id=item["id"], check_var=var: self.on_checklist_change(node_id, item_id, check_var.get()),
        )
        cb.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if checked:
            tk.Label(
                header,
                text="已选",
                bg=COLORS["primary"],
                fg="#FFFFFF",
                font=FONT_BADGE,
                padx=8,
                pady=3,
            ).pack(side=tk.RIGHT, padx=(8, 0))

        description = item.get("description", "").strip()
        if description:
            desc = tk.Label(
                block,
                text=description,
                bg=bg,
                fg=desc_fg,
                font=FONT_SMALL,
                justify=tk.LEFT,
                wraplength=700,
            )
            desc.pack(anchor=tk.W, fill=tk.X, padx=(26, 0), pady=(4, 0))
        else:
            desc = None

        if checked and item.get("optionGroups"):
            l4_progress = self.engine.item_l4_progress(self.engine.node_by_id[node_id], item, self.project_state)
            if l4_progress["missingGroups"]:
                tk.Label(
                    block,
                    text=f"L4 必选未完整：{'、'.join(l4_progress['missingGroups'])}",
                    bg=COLORS["warning_soft"],
                    fg=COLORS["warning"],
                    font=FONT_SMALL,
                    justify=tk.LEFT,
                    wraplength=660,
                    padx=8,
                    pady=4,
                ).pack(anchor=tk.W, fill=tk.X, padx=(26, 0), pady=(6, 0))
            self.make_option_groups(block, node_id, item, bg, disabled)

        if not disabled:
            for widget in (block, header, desc):
                if widget:
                    widget.configure(cursor="hand2")
                    widget.bind(
                        "<Button-1>",
                        lambda event, item_id=item["id"], next_value=not checked: self.on_checklist_block_click(
                            node_id,
                            item_id,
                            next_value,
                        ),
                    )
        return block

    def make_option_groups(self, parent, node_id, item, bg, disabled):
        node_state = self.project_state["nodes"].setdefault(node_id, {})
        checklist_options = node_state.setdefault("checklistOptions", {})
        item_options = checklist_options.setdefault(item["id"], {})
        groups_frame = tk.Frame(parent, bg=bg)
        groups_frame.pack(fill=tk.X, padx=(26, 0), pady=(8, 0))
        for group in item.get("optionGroups", []):
            group_state = item_options.setdefault(group["id"], {"selected": [], "primary": ""})
            selected_ids = set(group_state.get("selected", []))
            group_box = tk.Frame(groups_frame, bg=bg)
            group_box.pack(fill=tk.X, pady=(0, 8))
            title_row = tk.Frame(group_box, bg=bg)
            title_row.pack(fill=tk.X)
            required_text = "必选" if group.get("required") else "可选"
            mode_text = "单选" if group.get("selectionMode") == "single" else "多选"
            step = group.get("progressionStep", 0)
            layer = group.get("mdaLayerLabel", "")
            group_prefix = f"步骤 {step} / {layer} / " if step and layer else ""
            tk.Label(
                title_row,
                text=f"{group_prefix}{group['label']} · {required_text} · {mode_text}",
                bg=bg,
                fg=COLORS["text"],
                font=FONT_SMALL,
            ).pack(side=tk.LEFT)
            primary = group_state.get("primary", "")
            primary_label = self.option_label_by_id(group, primary) if primary else ""
            primary_badge = tk.Label(
                title_row,
                text=f"主：{primary_label}",
                bg=COLORS["primary"],
                fg="#FFFFFF",
                font=FONT_BADGE,
                padx=8,
                pady=2,
            )
            if primary:
                primary_badge.pack(side=tk.RIGHT)
            if group.get("description"):
                tk.Label(
                    group_box,
                    text=group["description"],
                    bg=bg,
                    fg=COLORS["muted"],
                    font=FONT_SMALL,
                    justify=tk.LEFT,
                    wraplength=660,
                ).pack(anchor=tk.W, fill=tk.X, pady=(2, 4))
            if group.get("designQuestion"):
                tk.Label(
                    group_box,
                    text=f"设计问题：{group['designQuestion']}",
                    bg=bg,
                    fg=COLORS["muted"],
                    font=FONT_SMALL,
                    justify=tk.LEFT,
                    wraplength=660,
                ).pack(anchor=tk.W, fill=tk.X, pady=(0, 4))
            conflict_label = tk.Label(
                group_box,
                text="",
                bg=COLORS["danger_soft"],
                fg=COLORS["danger"],
                font=FONT_SMALL,
                justify=tk.LEFT,
                wraplength=660,
                padx=8,
                pady=4,
            )

            option_grid = tk.Frame(group_box, bg=bg)
            option_grid.pack(fill=tk.X, pady=(4, 0))
            option_grid.grid_columnconfigure(0, weight=1)
            option_grid.grid_columnconfigure(1, weight=1)
            primary_var = tk.StringVar(value=primary)
            widget_key = (node_id, item["id"], group["id"])
            self.option_group_widgets[widget_key] = {
                "group": group,
                "primaryVar": primary_var,
                "primaryBadge": primary_badge,
                "conflictLabel": conflict_label,
                "options": {},
            }
            for index, option in enumerate(group.get("options", [])):
                option_selected = option["id"] in selected_ids
                option_bg = COLORS["primary_soft"] if option_selected else COLORS["surface_alt"]
                option_border = COLORS["primary"] if option_selected else COLORS["border"]
                row = index // 2
                column = index % 2
                chip = tk.Frame(
                    option_grid,
                    bg=option_bg,
                    highlightbackground=option_border,
                    highlightthickness=1,
                    padx=6,
                    pady=5,
                )
                chip.grid(row=row, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0), pady=(0, 6))
                option_var = tk.BooleanVar(value=option_selected)
                cb = tk.Checkbutton(
                    chip,
                    text=option["label"],
                    variable=option_var,
                    bg=option_bg,
                    fg=COLORS["primary"] if option_selected else COLORS["text"],
                    activebackground=option_bg,
                    activeforeground=COLORS["primary"],
                    selectcolor=COLORS["surface"],
                    font=FONT_SMALL,
                    anchor=tk.W,
                    state=tk.DISABLED if disabled else tk.NORMAL,
                    command=lambda group_id=group["id"], option_id=option["id"], var=option_var: self.on_option_group_option_change(
                        node_id,
                        item["id"],
                        group_id,
                        option_id,
                        var.get(),
                    ),
                )
                cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
                if group.get("allowPrimary"):
                    rb = tk.Radiobutton(
                        chip,
                        text="主",
                        variable=primary_var,
                        value=option["id"],
                        bg=option_bg,
                        fg=COLORS["muted"],
                        activebackground=option_bg,
                        selectcolor=COLORS["surface"],
                        font=FONT_BADGE,
                        state=tk.NORMAL if option_selected and not disabled else tk.DISABLED,
                        command=lambda group_id=group["id"], option_id=option["id"]: self.on_option_group_primary_change(
                            node_id,
                            item["id"],
                            group_id,
                            option_id,
                        ),
                    )
                    rb.pack(side=tk.RIGHT, padx=(6, 0))
                else:
                    rb = None
                self.option_group_widgets[widget_key]["options"][option["id"]] = {
                    "chip": chip,
                    "check": cb,
                    "radio": rb,
                    "var": option_var,
                }
            self.refresh_option_group_conflict_label(node_id, item["id"], group["id"])
        return groups_frame

    def option_label_by_id(self, group, option_id):
        for option in group.get("options", []):
            if option.get("id") == option_id:
                return option.get("label", option_id)
        return option_id

    def refresh_option_group_widgets(self, node_id, item_id, group_id):
        widget_key = (node_id, item_id, group_id)
        widgets = self.option_group_widgets.get(widget_key)
        if not widgets:
            return
        group = widgets["group"]
        group_state = (
            self.project_state["nodes"]
            .setdefault(node_id, {})
            .setdefault("checklistOptions", {})
            .setdefault(item_id, {})
            .setdefault(group_id, {"selected": [], "primary": ""})
        )
        selected_ids = set(group_state.get("selected", []))
        primary = group_state.get("primary", "")
        widgets["primaryVar"].set(primary)

        primary_badge = widgets.get("primaryBadge")
        if primary_badge:
            if primary:
                primary_badge.configure(text=f"主：{self.option_label_by_id(group, primary)}")
                if not primary_badge.winfo_manager():
                    primary_badge.pack(side=tk.RIGHT)
            elif primary_badge.winfo_manager():
                primary_badge.pack_forget()

        for option in group.get("options", []):
            option_id = option["id"]
            option_widgets = widgets["options"].get(option_id)
            if not option_widgets:
                continue
            selected = option_id in selected_ids
            option_bg = COLORS["primary_soft"] if selected else COLORS["surface_alt"]
            option_border = COLORS["primary"] if selected else COLORS["border"]
            option_widgets["var"].set(selected)
            option_widgets["chip"].configure(bg=option_bg, highlightbackground=option_border)
            option_widgets["check"].configure(
                bg=option_bg,
                fg=COLORS["primary"] if selected else COLORS["text"],
                activebackground=option_bg,
            )
            radio = option_widgets.get("radio")
            if radio:
                radio.configure(
                    bg=option_bg,
                    activebackground=option_bg,
                    state=tk.NORMAL if selected else tk.DISABLED,
                )
        self.refresh_option_group_conflict_label(node_id, item_id, group_id)

    def refresh_item_option_group_widgets(self, node_id, item_id):
        for widget_node_id, widget_item_id, widget_group_id in list(self.option_group_widgets):
            if widget_node_id == node_id and widget_item_id == item_id:
                self.refresh_option_group_widgets(node_id, item_id, widget_group_id)

    def refresh_option_group_conflict_label(self, node_id, item_id, group_id):
        widgets = self.option_group_widgets.get((node_id, item_id, group_id))
        if not widgets:
            return
        label = widgets.get("conflictLabel")
        if not label:
            return
        conflicts = self.engine.active_option_conflicts(self.project_state, node_id, item_id, group_id)
        if not conflicts:
            if label.winfo_manager():
                label.pack_forget()
            return
        lines = []
        for conflict in conflicts[:3]:
            lines.append(f"软冲突：{conflict['source']['label']} ↔ {conflict['target']['label']}。{conflict['reason']}")
        if len(conflicts) > 3:
            lines.append(f"还有 {len(conflicts) - 3} 条冲突。")
        label.configure(text="\n".join(lines))
        if not label.winfo_manager():
            label.pack(anchor=tk.W, fill=tk.X, pady=(0, 6))

    def on_checklist_block_click(self, node_id, item_id, checked):
        self.on_checklist_change(node_id, item_id, checked)
        return "break"

    def note_box(self, parent, label, value, callback):
        frame = tk.Frame(parent, bg=parent.cget("bg"))
        frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(frame, text=label, bg=parent.cget("bg"), fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        text = tk.Text(frame, height=2, wrap=tk.WORD, font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text"], highlightthickness=1, highlightbackground=COLORS["border"])
        text.insert("1.0", value)
        text.pack(fill=tk.X)
        text.bind("<FocusOut>", lambda event, widget=text: callback(widget.get("1.0", tk.END).strip()))
        return text

    def node_palette(self, decision_state):
        if decision_state == "completed":
            return {"bg": COLORS["success_soft"], "border": COLORS["success"], "fg": COLORS["success"], "muted": COLORS["success"], "marker_bg": COLORS["success"], "marker_fg": "#FFFFFF"}
        if decision_state == "risk":
            return {"bg": COLORS["warning_soft"], "border": COLORS["warning"], "fg": COLORS["warning"], "muted": COLORS["warning"], "marker_bg": COLORS["warning"], "marker_fg": "#FFFFFF"}
        if decision_state == "not_applicable":
            return {"bg": COLORS["surface_alt"], "border": COLORS["border_strong"], "fg": COLORS["muted"], "muted": COLORS["muted"], "marker_bg": COLORS["border_strong"], "marker_fg": "#FFFFFF"}
        if decision_state == "selected":
            return {"bg": COLORS["primary_soft"], "border": COLORS["primary"], "fg": COLORS["primary"], "muted": COLORS["primary"], "marker_bg": COLORS["primary"], "marker_fg": "#FFFFFF"}
        return {"bg": COLORS["surface"], "border": COLORS["border"], "fg": COLORS["text"], "muted": COLORS["muted"], "marker_bg": COLORS["surface_alt"], "marker_fg": COLORS["muted"]}

    def render_results(self):
        sig = (self._state_version, self.current_domain_id, self.project_name.get())
        if sig == self._last_results_version:
            return
        self._last_results_version = sig

        project_coverage = self.engine.project_coverage(self.project_state)
        quality = self.engine.quality_metrics(self.project_state)
        concreteness = quality["concretenessCoverage"]
        consistency = quality["consistencyScore"]
        project_l4 = self.engine.project_l4_progress(self.project_state)
        focus = self.engine.profile_focus_domains(self.project_state)
        summary = [
            f"项目：{self.project_name.get()}",
            f"质量等级：{quality['qualityBadge']}",
            f"全项目节点覆盖率：{project_coverage['nodePercent']}%",
            f"全项目三级子项覆盖率：{project_coverage['checklistPercent']}%",
            f"具体度覆盖：{concreteness['percent']}%（{concreteness['doneNodes']}/{concreteness['totalNodes']} concrete 节点）",
            f"一致性分数：{consistency['score']}（CRITICAL {consistency['criticalViolationCount']}/{consistency['applicableRuleCount']}）",
            f"全项目 L4 完整度：{project_l4['done']}/{project_l4['total']}（缺口节点 {project_l4['gapNodes']} 个）",
            "",
            "项目画像：",
            *(f"- {field_label(key)}：{option_label(key, value)}" for key, value in self.project_state.get("profile", {}).items()),
            "",
            "画像重点领域：",
            *(f"- {self.engine.domain_by_id[item]['domain']['name']}" for item in sorted(focus) if item in self.engine.domain_by_id),
            "",
            "领域覆盖：",
        ]
        for domain_doc in self.engine.domains:
            domain = domain_doc["domain"]
            coverage = self.engine.domain_coverage(domain["id"], self.project_state)
            l4_progress = self.engine.domain_l4_progress(domain["id"], self.project_state)
            l4_text = f"，L4 {l4_progress['done']}/{l4_progress['total']}" if l4_progress["total"] else "，L4 -"
            summary.append(f"- {domain['name']}：节点 {coverage['nodePercent']}%，子项 {coverage['checklistPercent']}%{l4_text}")
        self.write_text(self.summary_text, summary)

        missing = self.engine.missing_items(self.current_domain_id, self.project_state)
        self.write_text(self.gap_text, missing[:300] if missing else ["当前领域没有缺失项。"])

        risks = self.engine.risk_items(self.project_state)
        risk_lines = []
        for item in risks:
            risk_lines.append(f"- {item['node']['name']}：{item['riskNote'] or '未填写风险说明'}")
        option_conflicts = self.engine.active_domain_option_conflicts(self.project_state, self.current_domain_id)
        if option_conflicts:
            if risk_lines:
                risk_lines.append("")
            risk_lines.append("选项软冲突：")
            for conflict in option_conflicts[:80]:
                risk_lines.append(
                    f"- {conflict['nodeName']} / {conflict['itemLabel']}："
                    f"{conflict['source']['label']} ↔ {conflict['target']['label']}。{conflict['reason']}"
                )
            if len(option_conflicts) > 80:
                risk_lines.append(f"- 还有 {len(option_conflicts) - 80} 条软冲突未显示。")
        self.write_text(self.risk_text, risk_lines if risk_lines else ["暂无风险节点。"])

        validation = self.data.get("_meta", {}).get("validationErrors", [])
        meta = self.data.get("_meta", {})
        lines = [
            "独立性：",
            "- 未 import 外部项目模块",
            "- 未读取外部项目数据文件",
            f"- 运行目录：{meta.get('runtimeRoot', self.runtime_root)}",
            f"- 数据来源：{meta.get('dataSource', '')}",
            "",
            "数据校验：",
        ]
        lines.extend((f"- {item}" for item in validation) if validation else ["- 通过"])
        violations = self.engine.cross_layer_violations(self.project_state)
        lines.extend(["", "跨层一致性："])
        if violations:
            for violation in violations[:80]:
                lines.append(f"- [{violation.get('severity', 'WARNING')}] {violation.get('ruleId', '')}：{violation.get('reason', '')}")
                for option in violation.get("hitOptions", [])[:3]:
                    lines.append(
                        f"  - 命中：{option.get('nodeName', '')} / {option.get('itemLabel', '')} / "
                        f"{option.get('groupLabel', '')} / {option.get('optionLabel', option.get('optionId', ''))}"
                    )
            if len(violations) > 80:
                lines.append(f"- 还有 {len(violations) - 80} 条跨层一致性问题未显示。")
        else:
            lines.append("- 通过")
        gameplay_validation = self.engine.gameplay_validation_messages(self.project_state)
        lines.extend(["", "玩法系统校验："])
        if gameplay_validation:
            lines.extend(f"- {item}" for item in gameplay_validation)
        else:
            lines.append("- 通过")
        quality_violations = self.engine.quality_violations(self.project_state)
        lines.extend(["", "质量问题："])
        if quality_violations:
            for violation in quality_violations[:80]:
                lines.append(f"- [{violation.get('severity', 'WARNING')}] {violation.get('id', violation.get('type', ''))}：{violation.get('message', '')}")
                if violation.get("nodeName"):
                    lines.append(f"  - 节点：{violation.get('nodeName', '')}")
            if len(quality_violations) > 80:
                lines.append(f"- 还有 {len(quality_violations) - 80} 条质量问题未显示。")
        else:
            lines.append("- 通过")
        self.write_text(self.validation_text, lines)

    def write_text(self, widget, lines):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, "\n".join(lines))
        widget.configure(state=tk.DISABLED)

    def change_domain(self, domain_id):
        self.save_visible_notes()
        self.current_domain_id = domain_id
        self.render()

    def clear_search(self):
        if self.search_after_id:
            self.after_cancel(self.search_after_id)
            self.search_after_id = None
        self.search_text.set("")
        self.render_nodes()

    def on_search_key_release(self, event=None):
        if self.search_after_id:
            self.after_cancel(self.search_after_id)
        self.search_after_id = self.after(220, self.render_nodes_from_search)

    def render_nodes_from_search(self):
        self.search_after_id = None
        self.render_nodes()

    def on_profile_change(self):
        self._mark_state_changed()
        self.render()

    def on_gameplay_system_toggle(self, system_id, checked):
        state = self.engine.gameplay_systems_state(self.project_state)
        selected = list(state.get("selected", []))
        if checked and system_id not in selected:
            selected.append(system_id)
        elif not checked:
            selected = [item for item in selected if item != system_id]
            state.setdefault("weights", {}).pop(system_id, None)
            state.setdefault("coreLoops", {}).pop(system_id, None)
        state["selected"] = selected
        self.project_state["gameplaySystems"] = state
        self._mark_state_changed()
        self.status_text.set("玩法系统选择已更新。")
        self.render(preserve_node_scroll=True)

    def add_custom_gameplay_system(self, name_var):
        name = name_var.get().strip() if hasattr(name_var, "get") else str(name_var or "").strip()
        if not name:
            self.status_text.set("请输入自定义玩法系统名称。")
            return
        state = self.engine.gameplay_systems_state(self.project_state)
        existing_ids = {option["id"] for option in self.engine.gameplay_all_options(self.project_state)}
        from core.design.gameplay_systems import normalize_custom_system

        item = normalize_custom_system({"name": name}, existing_ids)
        state.setdefault("custom", []).append(item)
        state.setdefault("selected", []).append(item["id"])
        state.setdefault("weights", {})[item["id"]] = {"weight": "", "weight_type": "percent"}
        state.setdefault("coreLoops", {})[item["id"]] = ""
        self.project_state["gameplaySystems"] = state
        self._mark_state_changed()
        if hasattr(name_var, "set"):
            name_var.set("")
        self.status_text.set(f"已添加自定义玩法系统：{item['name']}")
        self.render(preserve_node_scroll=True)

    def delete_custom_gameplay_system(self, system_id):
        state = self.engine.gameplay_systems_state(self.project_state)
        state["custom"] = [item for item in state.get("custom", []) if item.get("id") != system_id]
        state["selected"] = [item for item in state.get("selected", []) if item != system_id]
        state.setdefault("weights", {}).pop(system_id, None)
        state.setdefault("coreLoops", {}).pop(system_id, None)
        interview = state.setdefault("interview", {})
        interview["parsedSystemIds"] = [item for item in interview.get("parsedSystemIds", []) if item != system_id]
        self.project_state["gameplaySystems"] = state
        self._mark_state_changed()
        self.status_text.set("自定义玩法系统已删除。")
        self.render(preserve_node_scroll=True)

    def update_gameplay_weight(self, system_id, value):
        state = self.engine.gameplay_systems_state(self.project_state)
        value = str(value or "").strip().replace("%", "")
        if value:
            try:
                number = float(value)
            except ValueError:
                self.status_text.set("占比必须是 0 到 100 的数字。")
                self.render(preserve_node_scroll=True)
                return
            number = max(0.0, min(100.0, number))
            if number.is_integer():
                number = int(number)
            value = number
        state.setdefault("weights", {})[system_id] = {"weight": value, "weight_type": "percent"}
        self.project_state["gameplaySystems"] = state
        self._mark_state_changed()
        summary = self.engine.gameplay_weight_summary(self.project_state)
        self.status_text.set(f"玩法系统总占比：{summary['total']}%")
        self.render(preserve_node_scroll=True)

    def update_gameplay_core_loop(self, system_id, value):
        state = self.engine.gameplay_systems_state(self.project_state)
        state.setdefault("coreLoops", {})[system_id] = str(value or "").strip()
        self.project_state["gameplaySystems"] = state
        self._mark_state_changed()
        self.status_text.set("核心循环描述已更新。")
        self.render(preserve_node_scroll=True)

    def toggle_gameplay_interview(self):
        self.expanded_gameplay_interview = not self.expanded_gameplay_interview
        self.render(preserve_node_scroll=True)

    def save_gameplay_interview_answers(self, value):
        state = self.engine.gameplay_systems_state(self.project_state)
        answers = [line.strip() for line in str(value or "").splitlines() if line.strip()]
        state.setdefault("interview", {})["answers"] = answers
        self.project_state["gameplaySystems"] = state
        self._mark_state_changed()
        self.status_text.set("玩法系统兜底访谈回答已保存。")
        self.render(preserve_node_scroll=True)

    def apply_gameplay_interview_answers(self, value):
        state = self.engine.gameplay_systems_state(self.project_state)
        answers = [line.strip() for line in str(value or "").splitlines() if line.strip()]
        state.setdefault("interview", {})["answers"] = answers
        created = parse_interview_answers_to_custom_systems(
            answers,
            self.engine.gameplay_system_options,
            state,
        )
        if not created:
            self.project_state["gameplaySystems"] = state
            self._mark_state_changed()
            self.status_text.set("访谈回答未解析出新的自定义系统。")
            self.render(preserve_node_scroll=True)
            return
        parsed_ids = state.setdefault("interview", {}).setdefault("parsedSystemIds", [])
        selected = state.setdefault("selected", [])
        for item in created:
            state.setdefault("custom", []).append(item)
            if item["id"] not in selected:
                selected.append(item["id"])
            state.setdefault("weights", {})[item["id"]] = {"weight": "", "weight_type": "percent"}
            state.setdefault("coreLoops", {})[item["id"]] = ""
            parsed_ids.append(item["id"])
        self.project_state["gameplaySystems"] = state
        self._mark_state_changed()
        self.status_text.set(f"访谈已补充 {len(created)} 个自定义玩法系统。")
        self.render(preserve_node_scroll=True)

    def gameplay_description_overlap(self, mapping_desc, core_loop):
        mapping_tokens = {token for token in re_split_words(mapping_desc) if len(token) >= 2}
        loop_tokens = {token for token in re_split_words(core_loop) if len(token) >= 2}
        if not mapping_tokens or not loop_tokens:
            return False
        overlap = mapping_tokens & loop_tokens
        return len(overlap) >= 4 or len(overlap) / max(1, len(loop_tokens)) >= 0.6

    def on_checklist_change(self, node_id, item_id, checked):
        self.engine.set_checklist_item(self.project_state, node_id, item_id, checked)
        self._mark_state_changed()
        self.render_nodes(preserve_scroll=True)
        self.render_results()
        self._schedule_autosave()

    def on_option_group_option_change(self, node_id, item_id, group_id, option_id, checked):
        self.engine.set_option_group_option(self.project_state, node_id, item_id, group_id, option_id, checked)
        self._mark_state_changed()
        self.refresh_item_option_group_widgets(node_id, item_id)
        self.render_results()
        self._schedule_autosave()

    def on_option_group_primary_change(self, node_id, item_id, group_id, option_id):
        self.engine.set_option_group_primary(self.project_state, node_id, item_id, group_id, option_id)
        self._mark_state_changed()
        self.refresh_item_option_group_widgets(node_id, item_id)
        self.render_results()
        self._schedule_autosave()

    def toggle_note_editor(self, node_id):
        if self.save_visible_notes():
            self._mark_state_changed()
        if node_id in self.expanded_note_nodes:
            self.expanded_note_nodes.remove(node_id)
        else:
            self.expanded_note_nodes.add(node_id)
        self.render_nodes(preserve_scroll=True)
        self._schedule_autosave()

    def on_risk_toggle(self, node_id, checked):
        if self.save_visible_notes():
            self._mark_state_changed()
        if checked:
            self.expanded_risk_nodes.add(node_id)
        else:
            self.expanded_risk_nodes.discard(node_id)
            self.project_state["nodes"].setdefault(node_id, {})["riskNote"] = ""
        self._mark_state_changed()
        self.render_nodes(preserve_scroll=True)
        self.render_results()
        self._schedule_autosave()

    def on_not_applicable_change(self, node_id, checked):
        if self.save_visible_notes():
            self._mark_state_changed()
        if checked:
            self.engine.set_node_state(self.project_state, node_id, "not_applicable")
            self.expanded_na_nodes.add(node_id)
        else:
            self.engine.set_node_state(self.project_state, node_id, "not_started")
            self.expanded_na_nodes.discard(node_id)
            self.project_state["nodes"].setdefault(node_id, {})["notApplicableReason"] = ""
            self.engine.refresh_node_state(self.project_state, node_id)
        self._mark_state_changed()
        self.render_nodes(preserve_scroll=True)
        self.render_results()
        self._schedule_autosave()

    def update_node_text(self, node_id, field_name, value):
        self.project_state["nodes"].setdefault(node_id, {})[field_name] = value
        self._mark_state_changed()
        if field_name == "designNote":
            self.engine.refresh_node_state(self.project_state, node_id)
            self.render(preserve_node_scroll=True)
        else:
            self.render_results()
            self._schedule_autosave()

    def update_node_design_entities(self, node_id, value):
        try:
            raw_entities = json.loads(value or "[]")
        except json.JSONDecodeError as error:
            self.status_text.set(f"L5 JSON 解析失败：{error.msg}")
            messagebox.showerror("L5 JSON 解析失败", f"{error.msg}\nline {error.lineno}, column {error.colno}")
            return
        entities, errors = self.engine.normalize_node_design_entities(raw_entities, node_id)
        node_state = self.project_state["nodes"].setdefault(node_id, {})
        node_state["designEntities"] = entities
        node_state["entityValidationErrors"] = errors
        self.engine.refresh_node_state(self.project_state, node_id)
        self._mark_state_changed()
        if errors:
            self.status_text.set(f"L5 实体已保存，存在 {len(errors)} 条校验警告。")
        else:
            self.status_text.set(f"L5 实体已保存：{len(entities)} 个。")
        self.render(preserve_node_scroll=True)

    def clear_node_design_entities(self, node_id):
        node_state = self.project_state["nodes"].setdefault(node_id, {})
        node_state["designEntities"] = []
        node_state["entityValidationErrors"] = []
        self.engine.refresh_node_state(self.project_state, node_id)
        self._mark_state_changed()
        self.status_text.set("L5 实体已清空。")
        self.render(preserve_node_scroll=True)

    def save_visible_notes(self) -> bool:
        changed = False
        for node_id, widgets in self.node_widgets.items():
            for field_name, widget_key in (("designNote", "note"), ("riskNote", "risk"), ("notApplicableReason", "na")):
                widget = widgets.get(widget_key)
                if widget:
                    node_state = self.project_state["nodes"].setdefault(node_id, {})
                    value = widget.get("1.0", tk.END).strip()
                    if node_state.get(field_name, "") != value:
                        node_state[field_name] = value
                        changed = True
            self.engine.refresh_node_state(self.project_state, node_id)
        project_name = self.project_name.get()
        if self.project_state.get("projectName") != project_name:
            self.project_state["projectName"] = project_name
            changed = True
        profile = self.current_profile_values()
        if self.project_state.get("profile") != profile:
            self.project_state["profile"] = profile
            changed = True
        return changed

    def current_profile_values(self):
        return {
            key: value_from_label(key, var.get())
            for key, var in self.profile_vars.items()
        }

    def sync_profile_labels(self):
        for key, value in self.project_state.get("profile", {}).items():
            self.profile_vars.setdefault(key, tk.StringVar()).set(option_label(key, value))

    def open_ai_interview(self):
        self.save_visible_notes()
        if self.ai_window and self.ai_window.winfo_exists():
            self.ai_window.lift()
            self.ai_window.focus_set()
            return
        self.ai_window = AIInterviewWindow(self)

    def import_memory_archive_dialog(self, event=None):
        path = filedialog.askopenfilename(
            title="导入框架记忆归档",
            filetypes=[("JSONL", "*.jsonl"), ("JSON", "*.json"), ("All files", "*.*")],
            initialdir=str(self.runtime_subdir("data")),
        )
        if not path:
            return
        if not self.ensure_project_local_path(path, "记忆归档"):
            return
        summary = import_memory_archive(self.runtime_root, path)
        if summary.get("errors"):
            messagebox.showwarning("记忆归档导入", "导入完成但存在问题：\n" + "\n".join(summary["errors"][:6]), parent=self)
        self.status_text.set(
            f"记忆归档已暂存：{summary.get('staged', 0)} 条，重复 {summary.get('duplicates', 0)} 条"
        )

    def open_template_viewer(self):
        self.save_visible_notes()
        templates = list_project_templates(include_internal=True)
        if not templates:
            messagebox.showinfo("模板查看", "未找到项目模板。")
            return

        window = tk.Toplevel(self)
        window.withdraw()  # 先隐藏窗口，避免闪烁
        window.title("模板查看")
        window.minsize(780, 480)
        window.configure(bg=COLORS["bg"])
        window.transient(self)
        window.grab_set()

        left = tk.Frame(window, bg=COLORS["surface"], padx=10, pady=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 6), pady=12)
        right = tk.Frame(window, bg=COLORS["surface"], padx=10, pady=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 12), pady=12)

        tk.Label(left, text="项目模板", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        tk.Label(left, text="选择一个范本项目后可完整覆盖当前项目。", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W, pady=(2, 8))

        columns = ("source", "scale", "tier", "name")
        tree = ttk.Treeview(left, columns=columns, show="headings", height=18)
        tree.heading("source", text="来源")
        tree.heading("scale", text="规模")
        tree.heading("tier", text="等级")
        tree.heading("name", text="模板")
        tree.column("source", width=60, anchor=tk.CENTER)
        tree.column("scale", width=150)
        tree.column("tier", width=60, anchor=tk.CENTER)
        tree.column("name", width=260)
        tree.pack(fill=tk.BOTH, expand=True)

        template_by_iid = {}
        for index, payload in enumerate(templates):
            meta = payload["template"]
            iid = str(index)
            template_by_iid[iid] = payload
            tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    meta.get("sourceLabel", meta.get("source", "")),
                    meta.get("scaleLabel", meta.get("targetScale", "")),
                    meta.get("qualityTier", ""),
                    meta.get("name", ""),
                ),
            )

        detail = tk.Text(right, bg=COLORS["surface"], fg=COLORS["text"], bd=0, highlightthickness=0, wrap=tk.WORD, font=FONT_BODY, padx=6, pady=6)
        detail.pack(fill=tk.BOTH, expand=True)

        buttons = tk.Frame(right, bg=COLORS["surface"])
        buttons.pack(fill=tk.X, pady=(8, 0))

        selected_payload = {"value": templates[0] if templates else None}

        def render_detail(payload):
            meta = payload.get("template", {})
            lines = [
                f"{meta.get('name', '')}",
                "",
                f"来源：{meta.get('sourceLabel', meta.get('source', ''))}",
                f"项目规模：{meta.get('scaleLabel', meta.get('targetScale', ''))}",
                f"质量等级：{meta.get('qualityTier', '')}",
                "",
                meta.get("summary", ""),
                "",
                "分析：",
                *(f"- {item}" for item in meta.get("analysis", [])),
                "",
                "核验：",
                f"- 模式：{meta.get('verification', {}).get('mode', '')}",
                f"- 日期：{meta.get('verification', {}).get('checkedAt', meta.get('verification', {}).get('createdAt', ''))}",
                f"- 运行时联网：{meta.get('verification', {}).get('runtimeNetwork', 'none')}",
            ]
            detail.configure(state=tk.NORMAL)
            detail.delete("1.0", tk.END)
            detail.insert(tk.END, "\n".join(lines))
            detail.configure(state=tk.DISABLED)

        def on_select(event=None):
            selection = tree.selection()
            if not selection:
                return
            payload = template_by_iid.get(selection[0])
            if not payload:
                return
            selected_payload["value"] = payload
            render_detail(payload)

        def on_import():
            payload = selected_payload.get("value")
            if not payload:
                return
            meta = payload.get("template", {})
            name = meta.get("name", "所选模板")
            confirm = (
                f"这会放弃当前项目的全部配置，并载入范本项目：{name}。\n\n"
                "此操作不可恢复。是否继续？"
            )
            if not messagebox.askyesno("载入范本项目", confirm, parent=window):
                return
            template_state = dict(payload.get("projectState", {}) or {})
            template_state.pop("aiInterview", None)
            self.project_state = self.engine.normalize_state(template_state)
            self.project_state["projectName"] = f"范本：{name}"
            self.project_name.set(self.project_state["projectName"])
            self._mark_state_changed()
            self.sync_profile_labels()
            self.current_domain_id = self.engine.first_domain_id()
            self.clear_expanded_nodes()
            self.status_text.set(f"已载入范本项目：{name}")
            window.destroy()
            self.render()

        ttk.Button(buttons, text="载入范本项目", command=on_import).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="关闭", command=window.destroy).pack(side=tk.RIGHT)
        tree.bind("<<TreeviewSelect>>", on_select)
        first = tree.get_children()
        if first:
            tree.selection_set(first[0])
            tree.focus(first[0])
            on_select()

        center_window(window, 900, 560)
        window.deiconify()  # 构建完成后显示窗口

    def open_save_template_dialog(self):
        self.save_visible_notes()
        window = tk.Toplevel(self)
        window.withdraw()  # 先隐藏窗口，避免闪烁
        window.title("另存为模板")
        window.resizable(False, False)
        window.configure(bg=COLORS["surface"])
        window.transient(self)
        window.grab_set()

        tk.Label(window, text="另存为自定义模板", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W, padx=14, pady=(14, 4))
        tk.Label(window, text="自定义模板会写入 data/project_templates，文件名前缀为 custom_。", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, wraplength=390, justify=tk.LEFT).pack(anchor=tk.W, padx=14, pady=(0, 12))

        form = tk.Frame(window, bg=COLORS["surface"], padx=14)
        form.pack(fill=tk.X)
        tk.Label(form, text="模板名称", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        name_var = tk.StringVar(value=self.project_name.get().replace("范本：", "").strip() or "我的项目模板")
        name_entry = ttk.Entry(form, textvariable=name_var, width=34)
        name_entry.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        tk.Label(form, text="项目规模", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).grid(row=2, column=0, sticky=tk.W, pady=(0, 4))
        scale_values = target_scale_options()
        scale_by_label = {label: value for value, label in scale_values}
        current_scale = self.project_state.get("profile", {}).get("targetScale", "indie")
        current_scale_label = option_label("targetScale", current_scale)
        if current_scale_label not in scale_by_label:
            current_scale_label = scale_values[0][1]
        scale_var = tk.StringVar(value=current_scale_label)
        ttk.Combobox(form, textvariable=scale_var, values=[label for _, label in scale_values], state="readonly", width=31).grid(row=3, column=0, sticky=tk.EW)

        message_var = tk.StringVar(value="")
        tk.Label(window, textvariable=message_var, bg=COLORS["surface"], fg=COLORS["danger"], font=FONT_SMALL, wraplength=390, justify=tk.LEFT).pack(anchor=tk.W, padx=14, pady=(8, 0))

        buttons = tk.Frame(window, bg=COLORS["surface"], padx=14, pady=12)
        buttons.pack(side=tk.BOTTOM, fill=tk.X)

        def save_template():
            name = name_var.get().strip()
            if not name:
                message_var.set("请输入模板名称。")
                name_entry.focus_set()
                return
            target_scale = scale_by_label.get(scale_var.get(), scale_values[0][0])
            normalized_name = name.casefold()
            existing = [
                payload
                for payload in list_project_templates()
                if payload.get("template", {}).get("targetScale") == target_scale
                and payload.get("template", {}).get("name", "").casefold() == normalized_name
            ]
            builtin_hit = next((payload for payload in existing if payload.get("template", {}).get("source") == "builtin"), None)
            if builtin_hit:
                message_var.set("内置范本不可覆盖，请更换模板名称。")
                name_entry.focus_set()
                return
            custom_hit = next((payload for payload in existing if payload.get("template", {}).get("source") == "custom"), None)
            target_path = custom_template_path(name, target_scale)
            if custom_hit or target_path.exists():
                if not messagebox.askyesno("覆盖自定义模板", f"已存在同名自定义模板：{name}\n\n是否覆盖？", parent=window):
                    name_entry.focus_set()
                    return
            path = save_custom_template(name, target_scale, self.project_state)
            self.status_text.set(f"已保存自定义模板：{path}")
            messagebox.showinfo("另存为模板", f"已保存自定义模板：\n{path}", parent=window)
            window.destroy()

        ttk.Button(buttons, text="保存模板", command=save_template).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="取消", command=window.destroy).pack(side=tk.RIGHT)
        name_entry.focus_set()

        center_window(window, 420, 240)
        window.deiconify()  # 构建完成后显示窗口

    def choose_export_options(self):
        window = tk.Toplevel(self)
        window.withdraw()  # 先隐藏窗口，避免闪烁
        window.title("选择导出内容")
        window.resizable(True, True)
        window.configure(bg=COLORS["surface"])
        window.transient(self)
        window.grab_set()

        result = {"value": None}
        scope_var = tk.StringVar(value="decision")
        format_var = tk.StringVar(value=self.export_format.get())
        include_gameplay_global_var = tk.BooleanVar(value=False)

        tk.Label(window, text="选择导出内容", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W, padx=16, pady=(16, 6))
        tk.Label(
            window,
            text="默认使用决策导出，只输出已确认、已完成、有风险和不适用的内容；完整导出会展开整个框架。",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=16, pady=(0, 12))

        scope_frame = tk.LabelFrame(window, text="内容范围", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SMALL, padx=10, pady=8)
        scope_frame.pack(fill=tk.X, padx=16, pady=(0, 10))
        tk.Radiobutton(
            scope_frame,
            text="决策导出：适合阅读和继续补全",
            variable=scope_var,
            value="decision",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["surface"],
            font=FONT_BODY,
            command=lambda: render_preview(),
        ).pack(anchor=tk.W)
        tk.Radiobutton(
            scope_frame,
            text="完整导出：展开所有领域、节点、三级项和 L4 选项",
            variable=scope_var,
            value="archive",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["surface"],
            font=FONT_BODY,
            command=lambda: render_preview(),
        ).pack(anchor=tk.W, pady=(4, 0))

        format_frame = tk.Frame(window, bg=COLORS["surface"], padx=16)
        format_frame.pack(fill=tk.X)
        tk.Label(format_frame, text="格式", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        format_box = ttk.Combobox(
            format_frame,
            textvariable=format_var,
            values=["markdown", "json", "txt", "text", "prompt"],
            state="readonly",
            width=18,
        )
        format_box.pack(anchor=tk.W, pady=(4, 0))
        format_box.bind("<<ComboboxSelected>>", lambda event: render_preview())
        tk.Label(
            format_frame,
            text="JSON 始终导出完整机器结构，用于兼容和后续程序读取。",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 0))
        tk.Checkbutton(
            format_frame,
            text="导出时附带玩法系统全局视图附页",
            variable=include_gameplay_global_var,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["surface"],
            font=FONT_SMALL,
            command=lambda: render_preview(),
        ).pack(anchor=tk.W, pady=(8, 0))

        preview_frame = tk.LabelFrame(window, text="导出预览", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SMALL, padx=8, pady=8)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 0))
        preview_text = tk.Text(
            preview_frame,
            height=5,
            bg=COLORS["surface_alt"],
            fg=COLORS["text"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            wrap=tk.WORD,
            font=FONT_SMALL,
            padx=8,
            pady=6,
        )
        preview_text.pack(fill=tk.BOTH, expand=True)
        preview_text.configure(state=tk.DISABLED)

        buttons = tk.Frame(window, bg=COLORS["surface"], padx=16, pady=14)
        buttons.pack(side=tk.BOTTOM, fill=tk.X)

        def render_preview():
            fmt = format_var.get()
            scope = "archive" if fmt == "json" else scope_var.get()
            lines = export_preview_lines(
                self.engine,
                self.project_state,
                fmt,
                scope,
                include_gameplay_global_view=include_gameplay_global_var.get(),
            )
            preview_text.configure(state=tk.NORMAL)
            preview_text.delete("1.0", tk.END)
            preview_text.insert(tk.END, "\n".join(lines))
            preview_text.configure(state=tk.DISABLED)

        def confirm():
            fmt = format_var.get()
            scope = "archive" if fmt == "json" else scope_var.get()
            result["value"] = (fmt, scope, include_gameplay_global_var.get())
            self.export_format.set(fmt)
            window.destroy()

        def export_now():
            """立即导出：弹出文件夹选择对话框并直接导出"""
            # 默认路径：用户文档目录（外部，不参与流水线）
            default_dir = Path.home() / "Documents"
            directory = filedialog.askdirectory(
                title="选择导出目录",
                initialdir=str(default_dir),
                parent=window
            )
            if not directory:
                return

            # 获取导出参数
            fmt = format_var.get()
            scope = "archive" if fmt == "json" else scope_var.get()

            # 关闭对话框
            window.destroy()

            # 执行导出
            try:
                path = write_export(
                    self.engine,
                    self.project_state,
                    directory,
                    fmt,
                    scope,
                    include_gameplay_global_view=include_gameplay_global_var.get(),
                )
                self.status_text.set(f"已导出：{path}")
                messagebox.showinfo("导出完成", f"已导出到：\n{path}")
            except OSError as error:
                messagebox.showerror("导出失败", f"无法写入导出文件：\n{error}")

        ttk.Button(buttons, text="立即导出", command=export_now).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="继续", command=confirm).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(buttons, text="取消", command=window.destroy).pack(side=tk.RIGHT)
        render_preview()

        center_window(window, 560, 650)
        window.deiconify()  # 构建完成后显示窗口

        window.wait_window()
        return result["value"]

    def export_project(self):
        self.save_visible_notes()
        options = self.choose_export_options()
        if not options:
            return
        export_format, export_scope, include_gameplay_global_view = options
        # 默认路径：用户文档目录（外部导出）
        default_dir = Path.home() / "Documents"
        directory = filedialog.askdirectory(title="选择导出目录", initialdir=str(default_dir))
        if not directory:
            return
        if not self.ensure_project_local_path(directory, "导出目录"):
            return
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
        self.status_text.set(f"已导出：{path}")
        messagebox.showinfo("导出完成", f"已导出到：\n{path}")

    def save_project(self) -> None:
        """打开存档管理界面。"""
        from core.ui.save_manager_dialog import SaveManagerDialog
        self.save_visible_notes()
        SaveManagerDialog(self)

    def open_project(self):
        """从执行对象存储加载设计项目"""
        from core.engines.execution_objects.design_project import (
            load_latest_design_project,
            list_design_project_versions,
        )
        from core.engines.execution_objects.integration import load_execution_object_store

        try:
            # 加载执行对象存储
            store = load_execution_object_store(self.runtime_root)

            # 获取所有版本
            versions = list_design_project_versions(store, include_drafts=False)

            if not versions:
                response = messagebox.askyesno(
                    "无项目",
                    "当前存档中没有设计项目。\n\n是否从文件导入？"
                )
                if response:
                    self._open_project_from_file()
                return

            # 加载最新版本
            project_data = load_latest_design_project(store)
            if not project_data:
                messagebox.showerror("加载失败", "无法加载设计项目")
                return

            # 恢复项目状态
            self.project_state = self.engine.normalize_state(project_data)
            self.project_name.set(self.project_state.get("projectName", "未命名游戏设计项目"))

            # 重置UI状态
            for key, value in self.project_state.get("profile", {}).items():
                self.profile_vars.setdefault(key, tk.StringVar()).set(option_label(key, value))
            self.current_domain_id = self.engine.first_domain_id()
            self.clear_expanded_nodes()

            self.status_text.set(f"已打开: {versions[0]['execution_object_id']}")
            self.render()

            messagebox.showinfo(
                "加载成功",
                f"已加载设计项目\n\n"
                f"项目名称: {self.project_name.get()}\n"
                f"版本ID: {versions[0]['execution_object_id']}"
            )

        except Exception as error:
            messagebox.showerror("加载失败", f"无法加载设计项目：\n{error}")
            import traceback
            traceback.print_exc()

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
            self._mark_state_changed()

            # 重置UI状态
            for key, value in self.project_state.get("profile", {}).items():
                self.profile_vars.setdefault(key, tk.StringVar()).set(option_label(key, value))
            self.current_domain_id = self.engine.first_domain_id()
            self.clear_expanded_nodes()

            self.render()

            # 提示用户迁移
            response = messagebox.askyesno(
                "迁移到执行对象存储",
                "是否将此项目保存到执行对象存储？\n\n"
                "这样可以享受版本历史、自动备份等功能。"
            )
            if response:
                self.save_project()

        except Exception as error:
            messagebox.showerror("打开失败", f"无法读取项目文件：\n{error}")
        for key, value in self.project_state.get("profile", {}).items():
            self.profile_vars.setdefault(key, tk.StringVar()).set(option_label(key, value))
        self.current_domain_id = self.engine.first_domain_id()
        self.clear_expanded_nodes()
        self.status_text.set(f"已打开：{path}")
        self.render()

    def reset_project(self):
        if not messagebox.askyesno("重置", "清空当前项目状态？"):
            return
        self.project_state = self.engine.empty_state()
        self.project_name.set(self.project_state["projectName"])
        self._mark_state_changed()
        for key, value in self.project_state["profile"].items():
            self.profile_vars.setdefault(key, tk.StringVar()).set(option_label(key, value))
        self.current_domain_id = self.engine.first_domain_id()
        self.clear_expanded_nodes()
        self.render()
