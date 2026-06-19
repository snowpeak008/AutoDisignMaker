from __future__ import annotations

import io
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.paths import PROJECT_ROOT, ARTIFACTS_DIR
from core.registry import STEP_SPECS, iter_steps
from core.runtime.control import request_stop
from core.runtime.pipeline_state import load_pipeline_state
from core.runtime.preflight import run_actual_development_preflight
from core.ui.pipeline_step_card import StepCard
from core.ui.theme import COLORS, FONT_BODY, FONT_SECTION, FONT_SMALL


_GROUPS = [
    ("设计阶段", range(0, 7)),
    ("开发阶段", range(7, 12)),
    ("验证阶段", range(12, 16)),
]

_CN_TITLES: dict[int, str] = {
    0:  "初始想法输入",
    1:  "玩法框架确认",
    2:  "设计评审冻结",
    3:  "程序需求确认",
    4:  "美术需求确认",
    5:  "程序需求评审",
    6:  "美术需求评审",
    7:  "程序开发计划",
    8:  "美术制作计划",
    9:  "资产契约对齐",
    10: "程序开发执行",
    11: "美术制作执行",
    12: "集成验证",
    13: "构建打包",
    14: "差量补丁",
    15: "最终审计",
}

_PIPELINE_STATUS_MAP = {
    "success":     "success",
    "failed":      "failed",
    "in_progress": "in_progress",
    "pending":     "not_started",
    "skipped":     "not_started",
}


class _QueueWriter(io.TextIOBase):
    def __init__(self, q: queue.Queue):
        self._q = q

    def write(self, s: str) -> int:
        if s:
            self._q.put(s)
        return len(s)

    def flush(self):
        pass


class PipelinePanel(tk.Frame):
    def __init__(self, parent: tk.Widget, log_queue: queue.Queue):
        super().__init__(parent, bg=COLORS["bg"])
        self._log_queue = log_queue
        self._selected_step: int | None = None
        self._running = False
        self._cards: dict[int, StepCard] = {}
        self._build()
        self.refresh()

    def _build(self):
        # 垂直分割：上=步骤树+详情，下=日志
        outer = tk.PanedWindow(self, orient=tk.VERTICAL, sashrelief=tk.FLAT,
                               sashwidth=4, bg=COLORS["border"])
        outer.pack(fill=tk.BOTH, expand=True)

        top_frame = tk.Frame(outer, bg=COLORS["bg"])
        outer.add(top_frame, stretch="always")

        log_frame = tk.Frame(outer, bg=COLORS["surface"])
        outer.add(log_frame, minsize=80, stretch="never")
        tk.Label(log_frame, text="运行日志", bg=COLORS["surface"],
                 fg=COLORS["muted"], font=FONT_SMALL, pady=4, padx=8).pack(anchor=tk.W)
        self._log_text = tk.Text(log_frame, bg=COLORS["dark"], fg="#D0E8C0",
                                 font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        log_sb = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._poll_log_queue()

        # 水平分割：左=步骤树，右=详情
        paned = ttk.PanedWindow(top_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ── Left sidebar ─────────────────────────────────────
        left = tk.Frame(paned, bg=COLORS["surface"], width=200)
        left.pack_propagate(False)
        paned.add(left, weight=1)

        canvas = tk.Canvas(left, bg=COLORS["surface"], highlightthickness=0)
        sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        inner = tk.Frame(canvas, bg=COLORS["surface"])
        win_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        for group_name, step_range in _GROUPS:
            tk.Label(inner, text=group_name, bg=COLORS["surface"], fg=COLORS["muted"],
                     font=FONT_SMALL, pady=4).pack(fill=tk.X, padx=6)
            for step_num in step_range:
                title = _CN_TITLES.get(step_num, f"步骤 {step_num:02d}")
                card = StepCard(inner, step_num, title, self._select_step)
                card.pack(fill=tk.X, padx=4, pady=1)
                self._cards[step_num] = card

        btn_frame = tk.Frame(left, bg=COLORS["surface"], pady=6)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=6)
        ttk.Button(btn_frame, text="▶ 运行全部",  command=self._run_all).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="⏹ 停止",      command=self._stop).pack(fill=tk.X, pady=2)

        # ── Right detail ─────────────────────────────────────
        self._detail = tk.Frame(paned, bg=COLORS["bg"])
        paned.add(self._detail, weight=4)
        tk.Label(self._detail, text="点击左侧步骤查看详情",
                 bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_BODY).pack(expand=True)

    def refresh(self):
        state = load_pipeline_state(PROJECT_ROOT)
        steps_state = state.get("steps", {})
        first_incomplete: int | None = None
        for step_num, card in self._cards.items():
            step_info = steps_state.get(str(step_num), {})
            raw = step_info.get("status", "pending") if isinstance(step_info, dict) else "pending"
            card.update_status(_PIPELINE_STATUS_MAP.get(raw, "not_started"))
            if first_incomplete is None and raw != "success":
                first_incomplete = step_num
        if self._selected_step is None and first_incomplete is not None:
            self._select_step(first_incomplete)
        elif self._selected_step is not None:
            self._render_detail(self._selected_step)

    def _select_step(self, step_num: int):
        for num, card in self._cards.items():
            card.set_selected(num == step_num)
        self._selected_step = step_num
        self._render_detail(step_num)

    def _render_detail(self, step_num: int):
        for w in self._detail.winfo_children():
            w.destroy()

        title = _CN_TITLES.get(step_num, f"步骤 {step_num:02d}")
        state = load_pipeline_state(PROJECT_ROOT)
        step_info = state.get("steps", {}).get(str(step_num), {})
        status = step_info.get("status", "pending") if isinstance(step_info, dict) else "pending"

        card = tk.Frame(self._detail, bg=COLORS["surface"], padx=16, pady=12)
        card.pack(fill=tk.X, padx=12, pady=12)

        tk.Label(card, text=f"步骤 {step_num:02d}：{title}",
                 bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        tk.Label(card, text=f"状态：{status}",
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_BODY).pack(anchor=tk.W, pady=(4, 8))

        btn_row = tk.Frame(card, bg=COLORS["surface"])
        btn_row.pack(anchor=tk.W)
        ttk.Button(btn_row, text="▶ 运行此步骤",
                   command=lambda: self._run_single(step_num)).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="📁 查看制品",
                   command=lambda: self._open_artifacts(step_num)).pack(side=tk.LEFT, padx=(8, 0))
        from core.ui.unity_config_dialog import UnityConfigDialog
        ttk.Button(btn_row, text="⚙ Unity配置",
                   command=lambda: UnityConfigDialog(self)).pack(side=tk.LEFT, padx=(8, 0))

        artifact_dir = ARTIFACTS_DIR / f"stage_{step_num:02d}"
        if artifact_dir.exists():
            files_frame = tk.Frame(self._detail, bg=COLORS["surface_alt"], padx=12, pady=8)
            files_frame.pack(fill=tk.X, padx=12)
            tk.Label(files_frame, text="制品文件",
                     bg=COLORS["surface_alt"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
            for f in sorted(artifact_dir.iterdir()):
                if f.is_file():
                    lbl = tk.Label(files_frame, text=f"  📄 {f.name}",
                                   bg=COLORS["surface_alt"], fg=COLORS["text"],
                                   font=FONT_SMALL, cursor="hand2", anchor=tk.W)
                    lbl.pack(fill=tk.X)
                    lbl.bind("<Button-1>", lambda e, p=f: os.startfile(str(p)))

    def _run_single(self, step_num: int):
        if step_num >= 3:
            result = run_actual_development_preflight(PROJECT_ROOT)
            if result.get("status") != "passed":
                msgs = "\n".join(
                    b.get("message", "") for b in result.get("blockers", []) if isinstance(b, dict)
                )
                messagebox.showwarning("无法运行", f"Unity 配置不完整：\n{msgs}", parent=self)
                return
        self._exec_range(step_num, step_num)

    def _run_all(self):
        self._exec_range(0, 15)

    def _exec_range(self, from_step: int, stop_step: int):
        if self._running:
            messagebox.showinfo("提示", "流水线正在运行中", parent=self)
            return
        self._running = True

        def _worker():
            writer = _QueueWriter(self._log_queue)
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = writer
            try:
                from core.main import run_range
                run_range(from_step, stop_step, auto_approve=True, skip_preflight=(from_step >= 3))
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
            self.after(0, self._on_run_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_run_done(self):
        self._running = False
        self.refresh()

    def _stop(self):
        request_stop(PROJECT_ROOT)

    def _append_log(self, text: str):
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, text)
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _poll_log_queue(self):
        try:
            while True:
                self._append_log(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _open_artifacts(self, step_num: int):
        path = ARTIFACTS_DIR / f"stage_{step_num:02d}"
        if path.exists():
            os.startfile(str(path))
