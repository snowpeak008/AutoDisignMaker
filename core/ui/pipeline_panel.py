from __future__ import annotations

import io
import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.paths import PROJECT_ROOT, ARTIFACTS_DIR
from core.registry import max_step_number
from core.runtime.control import request_stop, run_state_path
from core.runtime.pipeline_state import load_pipeline_state
from core.runtime.preflight import run_actual_development_preflight
from core.ui.pipeline_step_card import StepCard
from core.ui.theme import COLORS, FONT_BODY, FONT_SECTION, FONT_SMALL


_GROUPS = [
    ("设计阶段", range(0, 7)),
    ("风格确认", range(7, 9)),
    ("计划阶段", range(9, 12)),
    ("执行阶段", range(12, 14)),
    ("验证阶段", range(14, 18)),
]

_CN_TITLES: dict[int, str] = {
    0: "初始想法输入",
    1: "玩法框架确认",
    2: "设计评审冻结",
    3: "程序需求确认",
    4: "美术需求确认",
    5: "程序需求评审",
    6: "美术需求评审",
    7: "美术风格生成",
    8: "美术风格确认",
    9: "程序开发计划",
    10: "美术制作计划",
    11: "资产契约对齐",
    12: "程序开发执行",
    13: "美术制作执行",
    14: "集成验证",
    15: "构建打包",
    16: "差量补丁",
    17: "最终审计",
}

_PIPELINE_STATUS_MAP = {
    "success": "success",
    "failed": "failed",
    "in_progress": "in_progress",
    "pending": "not_started",
    "skipped": "not_started",
    "waiting_confirmation": "waiting_confirmation",
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
        # 水平分割：左=步骤树，右=详情+日志
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
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
        inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        for group_name, step_range in _GROUPS:
            tk.Label(
                inner,
                text=group_name,
                bg=COLORS["surface"],
                fg=COLORS["muted"],
                font=FONT_SMALL,
                pady=4,
            ).pack(fill=tk.X, padx=6)
            for step_num in step_range:
                title = _CN_TITLES.get(step_num, f"步骤 {step_num:02d}")
                card = StepCard(inner, step_num, title, self._select_step)
                card.pack(fill=tk.X, padx=4, pady=1)
                self._cards[step_num] = card

        # left sidebar bottom padding only
        tk.Frame(left, bg=COLORS["surface"], height=4).pack(side=tk.BOTTOM)

        # ── Right panel (vertical: detail top + log bottom) ───
        right = tk.Frame(paned, bg=COLORS["bg"])
        paned.add(right, weight=4)

        # R4+R5: 项目配置区 + 运行范围（固定在右侧顶部）
        config_bar = tk.Frame(right, bg=COLORS["surface_alt"], padx=12, pady=6)
        config_bar.pack(fill=tk.X, side=tk.TOP)
        from core.ui.unity_config_dialog import UnityConfigDialog

        ttk.Button(
            config_bar, text="项目配置", command=lambda: UnityConfigDialog(self)
        ).pack(side=tk.LEFT)
        ttk.Button(
            config_bar, text="导出到流水线", command=self._export_to_pipeline
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._from_var = tk.IntVar(value=0)
        max_step = max_step_number()
        self._to_var = tk.IntVar(value=max_step)
        self._skip_manual_gates_var = tk.BooleanVar(value=False)
        tk.Label(
            config_bar,
            text="  从步骤",
            bg=COLORS["surface_alt"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(side=tk.LEFT)
        tk.Spinbox(
            config_bar,
            from_=0,
            to=max_step,
            textvariable=self._from_var,
            width=3,
            font=FONT_SMALL,
        ).pack(side=tk.LEFT, padx=2)
        tk.Label(
            config_bar,
            text="到",
            bg=COLORS["surface_alt"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(side=tk.LEFT)
        tk.Spinbox(
            config_bar,
            from_=0,
            to=max_step,
            textvariable=self._to_var,
            width=3,
            font=FONT_SMALL,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(
            config_bar,
            text="跳过人工确认",
            variable=self._skip_manual_gates_var,
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(config_bar, text="▶ 运行", command=self._run_range).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(config_bar, text="⏹ 停止", command=self._stop).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        right_paned = tk.PanedWindow(
            right,
            orient=tk.VERTICAL,
            sashrelief=tk.FLAT,
            sashwidth=4,
            bg=COLORS["border"],
        )
        right_paned.pack(fill=tk.BOTH, expand=True)

        self._detail = tk.Frame(right_paned, bg=COLORS["bg"])
        right_paned.add(self._detail, stretch="never")
        tk.Label(
            self._detail,
            text="点击左侧步骤查看详情",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_BODY,
        ).pack(expand=True)

        log_frame = tk.Frame(right_paned, bg=COLORS["surface"])
        right_paned.add(log_frame, stretch="always", minsize=80)
        tk.Label(
            log_frame,
            text="运行日志",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            pady=4,
            padx=8,
        ).pack(anchor=tk.W)
        self._log_text = tk.Text(
            log_frame,
            bg=COLORS["dark"],
            fg="#D0E8C0",
            font=("Consolas", 9),
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        log_sb = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._poll_log_queue()

    def refresh(self):
        state = load_pipeline_state(PROJECT_ROOT)
        steps_state = state.get("steps", {})
        first_incomplete: int | None = None
        for step_num, card in self._cards.items():
            step_info = steps_state.get(str(step_num), {})
            raw = (
                step_info.get("status", "pending")
                if isinstance(step_info, dict)
                else "pending"
            )
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
        status = (
            step_info.get("status", "pending")
            if isinstance(step_info, dict)
            else "pending"
        )

        from core.runtime.preflight import ENGINE_LABELS, load_project_settings
        from core.adapters.registry import SUPPORTED_ADAPTERS

        settings = load_project_settings(PROJECT_ROOT)
        engine_key = settings.get("project_engine", "unity")
        engine_label = ENGINE_LABELS.get(engine_key, engine_key)
        if engine_key == "custom" and settings.get("custom_engine_name"):
            engine_label = f"自定义（{settings['custom_engine_name']}）"
        adapter_key = settings.get("pipeline_adapter", "none")
        adapter_label = SUPPORTED_ADAPTERS.get(adapter_key, adapter_key)

        card = tk.Frame(self._detail, bg=COLORS["surface"], padx=16, pady=12)
        card.pack(fill=tk.X, padx=12, pady=12)

        tk.Label(
            card,
            text=f"步骤 {step_num:02d}：{title}",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONT_SECTION,
        ).pack(anchor=tk.W)
        tk.Label(
            card,
            text=f"状态：{status}",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_BODY,
        ).pack(anchor=tk.W, pady=(4, 2))
        tk.Label(
            card,
            text=f"当前引擎：{engine_label}",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W, pady=(0, 2))
        tk.Label(
            card,
            text=f"AI 适配器：{adapter_label}",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W, pady=(0, 8))

        btn_row = tk.Frame(card, bg=COLORS["surface"])
        btn_row.pack(anchor=tk.W)
        run_label = "▶ 运行此步骤" if status != "success" else "🔁 重新运行"
        ttk.Button(
            btn_row, text=run_label, command=lambda: self._run_single(step_num)
        ).pack(side=tk.LEFT)

    def _run_single(self, step_num: int):
        if step_num >= 3:
            result = run_actual_development_preflight(PROJECT_ROOT)
            if result.get("status") != "passed":
                msgs = "\n".join(
                    b.get("message", "")
                    for b in result.get("blockers", [])
                    if isinstance(b, dict)
                )
                messagebox.showwarning(
                    "无法运行", f"Unity 配置不完整：\n{msgs}", parent=self
                )
                return
        self._exec_range(step_num, step_num)

    def _run_range(self):
        self._exec_range(self._from_var.get(), self._to_var.get())

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

                run_range(
                    from_step,
                    stop_step,
                    auto_approve=True,
                    skip_preflight=(from_step >= 3),
                    skip_all_gates=self._skip_manual_gates_var.get(),
                )
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr
            self.after(0, self._on_run_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_run_done(self):
        self._running = False
        self.refresh()
        self._check_and_show_confirmation_dialog()

    def _check_and_show_confirmation_dialog(self):
        state = self._read_run_state()
        if state.get("status") != "waiting_confirmation":
            return
        step_number = int(state.get("current_step") or 0)
        if state.get("confirmation_ui") != "style_confirmation_dialog":
            return
        try:
            from core.ui.style_confirmation_dialog import StyleConfirmationDialog

            style_options = self._load_style_options()
            output_dir = ARTIFACTS_DIR / f"stage_{step_number:02d}"
            dialog = StyleConfirmationDialog(
                self.winfo_toplevel(), style_options, output_dir
            )
            result = dialog.wait_result()
            if result == "confirmed":
                self._exec_range(step_number, step_number)
            elif result == "regenerate":
                self._exec_range(step_number - 1, step_number)
        except Exception as exc:
            messagebox.showerror("风格确认失败", str(exc), parent=self)

    def _read_run_state(self) -> dict:
        try:
            return json.loads(run_state_path(PROJECT_ROOT).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _load_style_options(self) -> dict:
        path = ARTIFACTS_DIR / "stage_07" / "style_options.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _export_to_pipeline(self):
        """执行 D4 导出，将设计内容打包到流水线 source_artifacts，并写入存档记录。"""
        import json
        from datetime import datetime
        from core.design.export_adapter import export_concept_package
        from core.save import manager as save_manager
        from core.design.data_loader import runtime_project_root

        try:
            result = export_concept_package()
            # 写入存档记录
            runtime_root = runtime_project_root()
            save_id = save_manager.current_save_id(runtime_root)
            if save_id:
                record = {
                    "exported_at": datetime.now().isoformat(timespec="seconds"),
                    "package_dir": result.get("package_dir", ""),
                    "attachment": result.get("attachment", ""),
                }
                record_path = (
                    save_manager.workspace_dir(runtime_root, save_id)
                    / "concept_export_record.json"
                )
                record_path.parent.mkdir(parents=True, exist_ok=True)
                record_path.write_text(
                    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            self._append_log(
                f"[导出] 设计内容已导出到流水线：{result.get('package_dir', '')}\n"
            )
            messagebox.showinfo(
                "导出成功",
                f"设计内容已导出到流水线。\n\n包目录：{result.get('package_dir', '')}",
                parent=self,
            )
        except Exception as exc:
            self._append_log(f"[导出] 失败：{exc}\n")
            messagebox.showerror("导出失败", str(exc), parent=self)

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
