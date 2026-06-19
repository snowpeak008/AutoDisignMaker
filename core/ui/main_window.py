from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from core.ui.theme import COLORS, FONT_BODY, FONT_SMALL

_GEOM_FILE = Path(__file__).resolve().parents[2] / "settings" / "window_geometry.json"


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoDesignMaker")
        self.minsize(1180, 720)
        self.resizable(True, True)
        self.configure(bg=COLORS["bg"])

        self._configure_style()
        self._geom_after_id = None
        self._load_geometry()
        self.bind("<Configure>", self._on_configure)

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

    def _load_geometry(self):
        try:
            data = json.loads(_GEOM_FILE.read_text("utf-8"))
            geom = data.get("geometry", "")
            if geom:
                self.geometry(geom)
                return
        except (OSError, json.JSONDecodeError, tk.TclError):
            pass
        self.state("zoomed")

    def _on_configure(self, _event=None):
        if self._geom_after_id:
            self.after_cancel(self._geom_after_id)
        self._geom_after_id = self.after(500, self._save_geometry)

    def _save_geometry(self):
        self._geom_after_id = None
        try:
            geom = self.geometry()
            _GEOM_FILE.parent.mkdir(parents=True, exist_ok=True)
            _GEOM_FILE.write_text(json.dumps({"geometry": geom}), "utf-8")
        except OSError:
            pass

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
        self._content = tk.Frame(self, bg=COLORS["bg"])
        self._content.pack(fill=tk.BOTH, expand=True)
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
            import queue
            from core.ui.pipeline_panel import PipelinePanel
            self._pipeline_panel = PipelinePanel(self._content, queue.Queue())
            self._pipeline_panel.place(x=0, y=0, relwidth=1, relheight=1)
        return self._pipeline_panel

    def _show_design(self):
        self._get_design_panel().lift()
        self._design_btn.configure(bg=COLORS["primary"], fg="white")
        self._pipeline_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])

    def _show_pipeline(self):
        panel = self._get_pipeline_panel()
        panel.lift()
        panel.refresh()
        self._design_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])
        self._pipeline_btn.configure(bg=COLORS["primary"], fg="white")
