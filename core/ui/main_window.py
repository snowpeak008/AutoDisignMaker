from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk

from core.ui.theme import COLORS, FONT_BODY, FONT_SMALL


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoDesignMaker")
        self.state("zoomed")
        self.minsize(1180, 720)
        self.resizable(True, True)
        self.configure(bg=COLORS["bg"])

        self._configure_style()

        self._log_queue: queue.Queue = queue.Queue()
        self._active_tab = "design"

        self._build_topbar()
        self._build_main_area()
        self._show_design()

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=FONT_BODY, background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TButton", padding=(10, 6), font=FONT_BODY)
        style.configure("TEntry", padding=(6, 5))
        style.configure("TCombobox", padding=(6, 5))
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 8), font=FONT_SMALL)
        style.configure("Horizontal.TProgressbar", troughcolor=COLORS["surface_alt"], background=COLORS["primary"])

    def _build_topbar(self):
        bar = tk.Frame(self, bg=COLORS["surface"], pady=6)
        bar.pack(fill=tk.X, side=tk.TOP)

        self._design_btn = tk.Label(bar, text="设计工作台", bg=COLORS["primary"], fg="white",
                                    font=FONT_BODY, padx=16, pady=6, cursor="hand2")
        self._design_btn.pack(side=tk.LEFT, padx=(12, 0))
        self._design_btn.bind("<Button-1>", lambda _: self._show_design())

        self._pipeline_btn = tk.Label(bar, text="开发流水线", bg=COLORS["surface"], fg=COLORS["muted"],
                                      font=FONT_BODY, padx=16, pady=6, cursor="hand2")
        self._pipeline_btn.pack(side=tk.LEFT, padx=(4, 0))
        self._pipeline_btn.bind("<Button-1>", lambda _: self._show_pipeline())

    def _build_main_area(self):
        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self._content = tk.Frame(paned, bg=COLORS["bg"])
        paned.add(self._content, weight=5)

        from core.ui.bottom_panel import BottomPanel
        self._bottom = BottomPanel(paned, self._log_queue)
        paned.add(self._bottom, weight=1)

        # Lazily create panels on first use
        self._design_panel = None
        self._pipeline_panel = None

    def _get_design_panel(self):
        if self._design_panel is None:
            from core.ui.app_window import CommercialDesignApp
            self._design_panel = CommercialDesignApp(self._content)
            self._design_panel.place(x=0, y=0, relwidth=1, relheight=1)
        return self._design_panel

    def _get_pipeline_panel(self):
        if self._pipeline_panel is None:
            from core.ui.pipeline_panel import PipelinePanel
            self._pipeline_panel = PipelinePanel(self._content, self._log_queue)
            self._pipeline_panel.place(x=0, y=0, relwidth=1, relheight=1)
        return self._pipeline_panel

    def _show_design(self):
        self._active_tab = "design"
        self._get_design_panel().lift()
        self._design_btn.configure(bg=COLORS["primary"], fg="white")
        self._pipeline_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])
        self._bottom.set_context("design")

    def _show_pipeline(self):
        self._active_tab = "pipeline"
        panel = self._get_pipeline_panel()
        panel.lift()
        panel.refresh()
        self._design_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])
        self._pipeline_btn.configure(bg=COLORS["primary"], fg="white")
        self._bottom.set_context("pipeline")
