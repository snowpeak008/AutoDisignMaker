from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path

from core.paths import PROJECT_ROOT, PROJECT_SETTINGS_FILE
from core.runtime.preflight import load_project_settings, run_actual_development_preflight
from core.ui.theme import COLORS, FONT_SMALL, FONT_SECTION


def _save_project_settings(settings: dict) -> None:
    try:
        existing = json.loads(PROJECT_SETTINGS_FILE.read_text("utf-8")) if PROJECT_SETTINGS_FILE.exists() else {}
    except (OSError, json.JSONDecodeError):
        existing = {}
    existing.update({k: v for k, v in settings.items() if v is not None})
    PROJECT_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_SETTINGS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), "utf-8")


class UnityConfigDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Unity 路径配置")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.grab_set()

        settings = load_project_settings(PROJECT_ROOT)

        frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Unity 路径配置", bg=COLORS["bg"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W, pady=(0, 12))

        for label, key, is_dir in [
            ("Unity 项目路径（development_path）", "development_path", True),
            ("Unity Editor 路径（editor_path）",   "editor_path",       False),
        ]:
            tk.Label(frame, text=label, bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
            row = tk.Frame(frame, bg=COLORS["bg"])
            row.pack(fill=tk.X, pady=(2, 10))
            var = tk.StringVar(value=settings.get(key, ""))
            setattr(self, f"_{key}_var", var)
            ttk.Entry(row, textvariable=var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
            browse = (lambda v=var: v.set(filedialog.askdirectory())) if is_dir else (lambda v=var: v.set(filedialog.askopenfilename()))
            ttk.Button(row, text="浏览", command=browse).pack(side=tk.LEFT, padx=(6, 0))

        self._result_label = tk.Label(frame, text="", bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL, wraplength=460, justify=tk.LEFT)
        self._result_label.pack(anchor=tk.W, pady=(0, 8))

        btn_row = tk.Frame(frame, bg=COLORS["bg"])
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="保存并验证", command=self._save).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="关闭",       command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))

    def _save(self):
        _save_project_settings({
            "development_path": self._development_path_var.get().strip(),
            "editor_path":      self._editor_path_var.get().strip(),
        })
        result = run_actual_development_preflight(PROJECT_ROOT)
        if result.get("status") == "passed":
            self._result_label.config(text="验证通过", fg=COLORS["success"])
        else:
            msgs = "\n".join(b.get("message", "") for b in result.get("blockers", []) if isinstance(b, dict))
            self._result_label.config(text=f"验证失败：\n{msgs}", fg=COLORS["danger"])
