from __future__ import annotations

from typing import Callable
import tkinter as tk

from core.ui.theme import COLORS, FONT_BODY, FONT_BADGE


_STATUS_COLOR: dict[str, str] = {
    "not_started": COLORS["surface_alt"],
    "in_progress":  COLORS["primary_soft"],
    "success":      COLORS["success_soft"],
    "failed":       COLORS["danger_soft"],
    "blocked":      COLORS["warning_soft"],
    "waiting_confirmation": COLORS["warning_soft"],
}

_STATUS_LABEL: dict[str, str] = {
    "not_started": "未执行",
    "in_progress":  "执行中",
    "success":      "已完成",
    "failed":       "失败",
    "blocked":      "等待依赖",
    "waiting_confirmation": "等待确认",
}


def workbench_key_to_status(key: str) -> str:
    return {
        "passed":           "success",
        "imported_pending": "not_started",
        "needs_run":        "not_started",
        "needs_input":      "blocked",
        "needs_fix":        "failed",
    }.get(key, "not_started")


class StepCard(tk.Frame):
    def __init__(self, parent: tk.Widget, step_num: int, title: str, on_select: Callable[[int], None]):
        super().__init__(parent, cursor="hand2", bd=1, relief=tk.FLAT)
        self._step_num = step_num
        self._on_select = on_select
        self._status = "not_started"

        self._bg = tk.Frame(self, padx=8, pady=5)
        self._bg.pack(fill=tk.BOTH, expand=True)

        num_lbl = tk.Label(self._bg, text=f"{step_num:02d}", font=FONT_BADGE, width=3, anchor=tk.W)
        num_lbl.pack(side=tk.LEFT)

        title_lbl = tk.Label(self._bg, text=title, font=FONT_BODY, anchor=tk.W)
        title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._dot = tk.Label(self._bg, text="●", font=FONT_BADGE)
        self._dot.pack(side=tk.RIGHT)

        self._all_widgets = [self, self._bg, num_lbl, title_lbl, self._dot]
        for w in self._all_widgets:
            w.bind("<Button-1>", self._click)
        self._apply_status()

    def _click(self, _event=None):
        self._on_select(self._step_num)

    def update_status(self, status: str):
        if self._status == status:
            return
        self._status = status
        self._apply_status()

    def set_selected(self, selected: bool):
        bg = COLORS["primary_soft"] if selected else _STATUS_COLOR.get(self._status, COLORS["surface_alt"])
        for w in self._all_widgets:
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass

    def _apply_status(self):
        bg = _STATUS_COLOR.get(self._status, COLORS["surface_alt"])
        dot_color = {
            "success":      COLORS["success"],
            "failed":       COLORS["danger"],
            "in_progress":  COLORS["primary"],
            "blocked":      COLORS["warning"],
            "waiting_confirmation": COLORS["warning"],
        }.get(self._status, COLORS["muted"])
        for w in self._all_widgets:
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass
        self._dot.configure(fg=dot_color)
