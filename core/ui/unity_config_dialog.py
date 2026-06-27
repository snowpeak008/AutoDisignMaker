from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, ttk

from core.paths import PROJECT_ROOT, PROJECT_SETTINGS_FILE
from core.runtime.preflight import (
    ENGINE_LABELS,
    ENGINE_PATH_LABELS,
    SUPPORTED_ENGINES,
    load_project_settings,
    run_actual_development_preflight,
)
from core.ui.theme import (
    COLORS,
    FONT_BADGE,
    FONT_BODY,
    FONT_CARD,
    FONT_SECTION,
    FONT_SMALL,
    center_window,
)


def _save_project_settings(settings: dict) -> None:
    try:
        existing = (
            json.loads(PROJECT_SETTINGS_FILE.read_text("utf-8"))
            if PROJECT_SETTINGS_FILE.exists()
            else {}
        )
    except (OSError, json.JSONDecodeError):
        existing = {}
    existing.update({k: v for k, v in settings.items() if v is not None})
    PROJECT_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_SETTINGS_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), "utf-8"
    )


def _section(parent: tk.Widget, title: str) -> tk.Frame:
    """Renders a titled card section with border."""
    outer = tk.Frame(parent, bg=COLORS["bg"])
    outer.pack(fill=tk.X, pady=(0, 12))
    header = tk.Frame(outer, bg=COLORS["bg"])
    header.pack(fill=tk.X, pady=(0, 4))
    tk.Label(
        header,
        text=title,
        bg=COLORS["bg"],
        fg=COLORS["muted"],
        font=FONT_BADGE,
    ).pack(side=tk.LEFT)
    tk.Frame(header, bg=COLORS["border"], height=1).pack(
        side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=(4, 0)
    )
    card = tk.Frame(
        outer,
        bg=COLORS["surface"],
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        padx=14,
        pady=12,
    )
    card.pack(fill=tk.X)
    return card


def _field_row(parent: tk.Widget, label: str) -> tuple[tk.Label, tk.Frame]:
    """Label above + content row below."""
    lbl = tk.Label(
        parent, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL
    )
    lbl.pack(anchor=tk.W)
    row = tk.Frame(parent, bg=COLORS["surface"])
    row.pack(fill=tk.X, pady=(4, 8))
    return lbl, row


class ProjectConfigDialog(tk.Toplevel):
    """项目配置对话框（卡片布局）。

    固定顺序：
      [环境设置] 引擎
      [custom] 引擎名称
      [项目路径] dev_section（始终可见）
      [编辑器路径] editor_section
      [状态 + 按钮]
    """

    _ENGINE_VALUES = list(SUPPORTED_ENGINES)
    _ENGINE_DISPLAY = [ENGINE_LABELS[e] for e in _ENGINE_VALUES]
    _DISPLAY_TO_KEY: dict[str, str] = {v: k for k, v in ENGINE_LABELS.items()}

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.withdraw()  # 先隐藏窗口，避免闪烁
        self.title("项目配置")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.grab_set()

        settings = load_project_settings(PROJECT_ROOT)

        root_frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        root_frame.pack(fill=tk.BOTH, expand=True)

        # ── 标题行 ──────────────────────────────────────────────
        title_row = tk.Frame(root_frame, bg=COLORS["bg"])
        title_row.pack(fill=tk.X, pady=(0, 16))
        tk.Label(
            title_row,
            text="项目配置",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=FONT_SECTION,
        ).pack(side=tk.LEFT)
        tk.Label(
            title_row,
            text="设置游戏引擎与项目路径",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(side=tk.LEFT, padx=(10, 0), pady=(3, 0))

        # ── 环境设置卡片 ───────────────────────────────────────
        env_card = _section(root_frame, "环境设置")
        env_cols = tk.Frame(env_card, bg=COLORS["surface"])
        env_cols.pack(fill=tk.X)
        env_cols.columnconfigure(0, weight=1)

        # 引擎列
        engine_col = tk.Frame(env_cols, bg=COLORS["surface"])
        engine_col.grid(row=0, column=0, sticky="ew")
        tk.Label(
            engine_col,
            text="游戏引擎",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W)
        self._engine_var = tk.StringVar(
            value=ENGINE_LABELS.get(settings.get("project_engine", "unity"), "Unity")
        )
        engine_combo = ttk.Combobox(
            engine_col,
            textvariable=self._engine_var,
            values=self._ENGINE_DISPLAY,
            state="readonly",
            width=18,
        )
        engine_combo.pack(anchor=tk.W, pady=(4, 0))
        engine_combo.bind("<<ComboboxSelected>>", lambda _: self._on_engine_change())

        # ── 自定义引擎名称（仅 custom 时显示） ─────────────────────
        self._custom_name_outer = tk.Frame(root_frame, bg=COLORS["bg"])
        custom_card = tk.Frame(
            self._custom_name_outer,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        custom_card.pack(fill=tk.X)
        tk.Label(
            custom_card,
            text="引擎名称",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W)
        self._custom_name_var = tk.StringVar(
            value=settings.get("custom_engine_name", "")
        )
        ttk.Entry(custom_card, textvariable=self._custom_name_var, width=38).pack(
            anchor=tk.W, pady=(4, 0)
        )

        # ── 路径区块（始终可见） ──────────────────────────────────
        self._paths_card = _section(root_frame, "路径配置")

        self._dev_label = tk.Label(
            self._paths_card,
            text="",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        )
        self._dev_label.pack(anchor=tk.W)
        self._dev_hint_label = tk.Label(
            self._paths_card,
            text="",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            wraplength=480,
            justify=tk.LEFT,
        )
        dev_row = tk.Frame(self._paths_card, bg=COLORS["surface"])
        dev_row.pack(fill=tk.X, pady=(4, 10))
        self._development_path_var = tk.StringVar(
            value=settings.get("development_path", "")
        )
        ttk.Entry(dev_row, textvariable=self._development_path_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            dev_row,
            text="浏览",
            command=lambda: self._development_path_var.set(
                filedialog.askdirectory() or self._development_path_var.get()
            ),
        ).pack(side=tk.LEFT, padx=(6, 0))

        self._editor_label = tk.Label(
            self._paths_card,
            text="",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        )
        self._editor_label.pack(anchor=tk.W)
        editor_row = tk.Frame(self._paths_card, bg=COLORS["surface"])
        editor_row.pack(fill=tk.X, pady=(4, 0))
        self._editor_path_var = tk.StringVar(value=settings.get("editor_path", ""))
        ttk.Entry(editor_row, textvariable=self._editor_path_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            editor_row,
            text="浏览",
            command=lambda: self._editor_path_var.set(
                filedialog.askopenfilename() or self._editor_path_var.get()
            ),
        ).pack(side=tk.LEFT, padx=(6, 0))

        # ── 底部：状态 + 按钮 ────────────────────────────────────
        bottom = tk.Frame(root_frame, bg=COLORS["bg"])
        bottom.pack(fill=tk.X, pady=(4, 0))

        self._result_label = tk.Label(
            bottom,
            text="",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            wraplength=440,
            justify=tk.LEFT,
            anchor=tk.W,
        )
        self._result_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(bottom, text="关闭", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(bottom, text="保存并验证", command=self._save).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        self._on_engine_change()
        self.update_idletasks()
        center_window(self, 720, 560)
        self.deiconify()  # 构建完成后显示窗口

    # ──────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────

    def _current_engine_key(self) -> str:
        return self._DISPLAY_TO_KEY.get(self._engine_var.get(), "unity")

    def _on_engine_change(self) -> None:
        engine = self._current_engine_key()
        is_custom = engine == "custom"
        dev_label_text, editor_label_text = ENGINE_PATH_LABELS.get(
            engine, ("项目路径", "编辑器路径")
        )

        if is_custom:
            self._custom_name_outer.pack(
                fill=tk.X, pady=(0, 12), before=self._paths_card
            )
        else:
            self._custom_name_outer.pack_forget()

        self._dev_label.configure(text=dev_label_text)
        if is_custom:
            self._dev_hint_label.configure(
                text="此路径为自定义引擎的项目根目录，流水线将以此作为工作区基准路径。若不使用路径验证可留空。"
            )
            self._dev_hint_label.pack(anchor=tk.W, pady=(2, 6))
        else:
            self._dev_hint_label.pack_forget()

        self._editor_label.configure(text=editor_label_text)

    def _save(self) -> None:
        engine = self._current_engine_key()
        _save_project_settings(
            {
                "project_engine": engine,
                "custom_engine_name": (
                    self._custom_name_var.get().strip() if engine == "custom" else ""
                ),
                "development_path": self._development_path_var.get().strip(),
                "editor_path": (
                    self._editor_path_var.get().strip() if engine != "custom" else ""
                ),
            }
        )
        result = run_actual_development_preflight(PROJECT_ROOT)
        if result.get("status") == "passed":
            self._result_label.config(text="✓ 验证通过", fg=COLORS["success"])
        else:
            msgs = "  ".join(
                b.get("message", "")
                for b in result.get("blockers", [])
                if isinstance(b, dict)
            )
            self._result_label.config(text=f"✗ {msgs}", fg=COLORS["danger"])


# 兼容旧引用
UnityConfigDialog = ProjectConfigDialog
