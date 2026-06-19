from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk
from typing import Any

from core.ui.theme import COLORS, FONT_SMALL


class BottomPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, log_queue: queue.Queue, app: Any = None):
        super().__init__(parent, bg=COLORS["surface"])
        self._log_queue = log_queue
        self._app = app
        self._build()
        self._poll_log_queue()

    def _build(self):
        bar = tk.Frame(self, bg=COLORS["surface"], pady=4)
        bar.pack(fill=tk.X, side=tk.TOP)

        self._log_btn = tk.Label(bar, text="📋 日志", bg=COLORS["primary_soft"],
                                 fg=COLORS["primary"], font=FONT_SMALL, padx=10, pady=3, cursor="hand2")
        self._log_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._log_btn.bind("<Button-1>", lambda _: self._show_log())

        self._ai_btn = tk.Label(bar, text="🤖 AI 访谈", bg=COLORS["surface"],
                                fg=COLORS["muted"], font=FONT_SMALL, padx=10, pady=3, cursor="hand2")
        self._ai_btn.pack(side=tk.LEFT, padx=2)
        self._ai_btn.bind("<Button-1>", lambda _: self._show_ai())

        self._content = tk.Frame(self, bg=COLORS["surface"])
        self._content.pack(fill=tk.BOTH, expand=True)

        self._log_pane = self._build_log_pane(self._content)
        self._ai_pane = self._build_ai_pane(self._content)
        self._log_pane.pack(fill=tk.BOTH, expand=True)

    def _build_log_pane(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=COLORS["surface"])
        self._log_text = tk.Text(frame, bg=COLORS["dark"], fg="#D0E8C0",
                                 font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        sb = ttk.Scrollbar(frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(fill=tk.BOTH, expand=True)
        return frame

    def _build_ai_pane(self, parent: tk.Widget) -> tk.Frame:
        if self._app is None:
            frame = tk.Frame(parent, bg=COLORS["surface"])
            tk.Label(frame, text="AI 访谈不可用（非设计工作台模式）",
                     bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(expand=True)
            return frame
        from core.ui.embedded_interview import EmbeddedInterviewPanel
        return EmbeddedInterviewPanel(parent, self._app)

    def append_log(self, line: str):
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, line)
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _poll_log_queue(self):
        try:
            while True:
                self.append_log(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _show_log(self):
        self._ai_pane.pack_forget()
        self._log_pane.pack(fill=tk.BOTH, expand=True)
        self._log_btn.configure(bg=COLORS["primary_soft"], fg=COLORS["primary"])
        self._ai_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])

    def _show_ai(self):
        self._log_pane.pack_forget()
        self._ai_pane.pack(fill=tk.BOTH, expand=True)
        self._ai_btn.configure(bg=COLORS["primary_soft"], fg=COLORS["primary"])
        self._log_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])
