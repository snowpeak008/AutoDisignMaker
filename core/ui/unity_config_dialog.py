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
from core.ui.theme import COLORS, FONT_SMALL, FONT_SECTION


def _save_project_settings(settings: dict) -> None:
    try:
        existing = json.loads(PROJECT_SETTINGS_FILE.read_text("utf-8")) if PROJECT_SETTINGS_FILE.exists() else {}
    except (OSError, json.JSONDecodeError):
        existing = {}
    existing.update({k: v for k, v in settings.items() if v is not None})
    PROJECT_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_SETTINGS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), "utf-8")


class ProjectConfigDialog(tk.Toplevel):
    """项目配置对话框 - 支持多引擎（Unity / Unreal Engine / Godot / 自定义）。

    布局固定顺序（区块按需 pack / pack_forget，不使用 after= 动态插入）：
      1. 标题
      2. 引擎选择
      3. [custom] 引擎名称区块
      4. 项目路径区块（始终可见）
      5. [非 custom] 编辑器路径区块
      6. 状态标签
      7. 操作按钮
    """

    _ENGINE_VALUES = list(SUPPORTED_ENGINES)
    _ENGINE_DISPLAY = [ENGINE_LABELS[e] for e in _ENGINE_VALUES]
    _DISPLAY_TO_KEY: dict[str, str] = {v: k for k, v in ENGINE_LABELS.items()}

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("项目配置")
        self.resizable(True, False)
        self.configure(bg=COLORS["bg"])
        self.grab_set()

        settings = load_project_settings(PROJECT_ROOT)

        frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # ── 1. 标题 ───────────────────────────────────────────────
        tk.Label(
            frame, text="项目配置", bg=COLORS["bg"], fg=COLORS["text"], font=FONT_SECTION,
        ).pack(anchor=tk.W, pady=(0, 12))

        # ── 2. 引擎选择 ───────────────────────────────────────────
        tk.Label(frame, text="游戏引擎", bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        self._engine_var = tk.StringVar(
            value=ENGINE_LABELS.get(settings.get("project_engine", "unity"), "Unity")
        )
        engine_combo = ttk.Combobox(
            frame,
            textvariable=self._engine_var,
            values=self._ENGINE_DISPLAY,
            state="readonly",
            width=24,
        )
        engine_combo.pack(anchor=tk.W, pady=(4, 12))
        engine_combo.bind("<<ComboboxSelected>>", lambda _: self._on_engine_change())

        # ── 3. 自定义引擎名称区块（仅 custom 时显示） ─────────────
        self._custom_name_frame = tk.Frame(frame, bg=COLORS["bg"])
        tk.Label(
            self._custom_name_frame, text="引擎名称",
            bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL,
        ).pack(anchor=tk.W)
        self._custom_name_var = tk.StringVar(value=settings.get("custom_engine_name", ""))
        ttk.Entry(self._custom_name_frame, textvariable=self._custom_name_var, width=34).pack(
            anchor=tk.W, pady=(4, 0)
        )

        # ── 4. 项目路径区块（始终可见） ───────────────────────────
        self._dev_section = tk.Frame(frame, bg=COLORS["bg"])
        self._dev_label = tk.Label(
            self._dev_section, text="", bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL,
        )
        self._dev_label.pack(anchor=tk.W)
        self._dev_hint_label = tk.Label(
            self._dev_section, text="",
            bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL,
            wraplength=460, justify=tk.LEFT,
        )
        dev_row = tk.Frame(self._dev_section, bg=COLORS["bg"])
        dev_row.pack(fill=tk.X, pady=(4, 0))
        self._development_path_var = tk.StringVar(value=settings.get("development_path", ""))
        ttk.Entry(dev_row, textvariable=self._development_path_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            dev_row, text="浏览",
            command=lambda: self._development_path_var.set(filedialog.askdirectory()),
        ).pack(side=tk.LEFT, padx=(6, 0))

        # ── 5. 编辑器路径区块（custom 时隐藏） ───────────────────
        self._editor_frame = tk.Frame(frame, bg=COLORS["bg"])
        self._editor_label = tk.Label(
            self._editor_frame, text="", bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL,
        )
        self._editor_label.pack(anchor=tk.W)
        editor_row = tk.Frame(self._editor_frame, bg=COLORS["bg"])
        editor_row.pack(fill=tk.X, pady=(4, 0))
        self._editor_path_var = tk.StringVar(value=settings.get("editor_path", ""))
        ttk.Entry(editor_row, textvariable=self._editor_path_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            editor_row, text="浏览",
            command=lambda: self._editor_path_var.set(filedialog.askopenfilename()),
        ).pack(side=tk.LEFT, padx=(6, 0))

        # ── 6. 状态标签 ───────────────────────────────────────────
        self._result_label = tk.Label(
            frame, text="", bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL,
            wraplength=460, justify=tk.LEFT,
        )

        # ── 7. 操作按钮（右下角） ─────────────────────────────────
        btn_row = tk.Frame(frame, bg=COLORS["bg"])
        ttk.Button(btn_row, text="关闭", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_row, text="保存并验证", command=self._save).pack(side=tk.RIGHT, padx=(0, 8))

        # _dev_section 始终可见，一次性 pack，不参与引擎切换
        self._dev_section.pack(fill=tk.X, pady=(0, 8))

        # 末尾静态区块（不参与引擎切换）始终 pack
        self._result_label.pack(anchor=tk.W, pady=(12, 4))
        btn_row.pack(fill=tk.X, pady=(0, 4))

        # 初始渲染
        self._on_engine_change()

    # ──────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────

    def _current_engine_key(self) -> str:
        return self._DISPLAY_TO_KEY.get(self._engine_var.get(), "unity")

    def _on_engine_change(self) -> None:
        """按当前引擎刷新动态区块的可见性与标签文字。"""
        engine = self._current_engine_key()
        is_custom = engine == "custom"
        dev_label_text, editor_label_text = ENGINE_PATH_LABELS.get(
            engine, ("项目路径", "编辑器路径")
        )

        # 自定义引擎名称区块
        if is_custom:
            self._custom_name_frame.pack(fill=tk.X, pady=(0, 8))
        else:
            self._custom_name_frame.pack_forget()

        # 项目路径标签与说明提示
        self._dev_label.configure(text=dev_label_text)
        if is_custom:
            self._dev_hint_label.configure(
                text="此路径为自定义引擎的项目根目录，流水线将以此作为工作区基准路径。若不使用路径验证可留空。"
            )
            self._dev_hint_label.pack(anchor=tk.W, pady=(2, 0))
        else:
            self._dev_hint_label.pack_forget()

        # 编辑器路径区块（所有引擎均显示）
        self._editor_label.configure(text=editor_label_text)
        self._editor_frame.pack(fill=tk.X, pady=(0, 8))

    def _save(self) -> None:
        engine = self._current_engine_key()
        _save_project_settings({
            "project_engine": engine,
            "custom_engine_name": self._custom_name_var.get().strip() if engine == "custom" else "",
            "development_path": self._development_path_var.get().strip(),
            "editor_path": self._editor_path_var.get().strip() if engine != "custom" else "",
        })
        result = run_actual_development_preflight(PROJECT_ROOT)
        if result.get("status") == "passed":
            self._result_label.config(text="验证通过", fg=COLORS["success"])
        else:
            msgs = "\n".join(
                b.get("message", "") for b in result.get("blockers", []) if isinstance(b, dict)
            )
            self._result_label.config(text=f"验证失败：\n{msgs}", fg=COLORS["danger"])


# 兼容旧引用
UnityConfigDialog = ProjectConfigDialog
