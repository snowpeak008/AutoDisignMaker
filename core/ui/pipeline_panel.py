from __future__ import annotations

import io
import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from core.paths import PROJECT_ROOT, ARTIFACTS_DIR
from core.registry import max_step_number
from core.runtime.control import request_stop, run_state_path
from core.runtime.pipeline_state import load_pipeline_state
from core.runtime.preflight import run_actual_development_preflight
from core.ui.pipeline_step_card import StepCard
from core.ui.theme import COLORS, FONT_BODY, FONT_SECTION, FONT_SMALL


_GROUPS = [
    ("设计阶段", range(0, 7)),
    ("风格确认", range(7, 8)),
    ("计划阶段", range(8, 11)),
    ("执行阶段", range(11, 13)),
    ("验证阶段", range(13, 17)),
]

_CN_TITLES: dict[int, str] = {
    0: "初始想法输入",
    1: "玩法框架确认",
    2: "设计评审冻结",
    3: "程序需求确认",
    4: "美术需求确认",
    5: "程序需求评审",
    6: "美术需求评审",
    7: "美术风格生成与确认",
    8: "程序开发计划",
    9: "美术制作计划",
    10: "资产契约对齐",
    11: "程序开发执行",
    12: "美术制作执行",
    13: "集成验证",
    14: "构建打包",
    15: "差量补丁",
    16: "最终审计",
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
            config_bar, text="AI 配置", command=self._open_ai_config
        ).pack(side=tk.LEFT, padx=(8, 0))
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

        self._right_paned = tk.PanedWindow(
            right,
            orient=tk.VERTICAL,
            sashrelief=tk.FLAT,
            sashwidth=4,
            bg=COLORS["border"],
        )
        self._right_paned.pack(fill=tk.BOTH, expand=True)

        self._detail = tk.Frame(self._right_paned, bg=COLORS["bg"])
        self._right_paned.add(self._detail, stretch="never")
        tk.Label(
            self._detail,
            text="点击左侧步骤查看详情",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=FONT_BODY,
        ).pack(expand=True)

        log_frame = tk.Frame(self._right_paned, bg=COLORS["surface"])
        self._right_paned.add(log_frame, stretch="always", minsize=80)
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
        try:
            from core.config.ai_config import AI_CONFIG_PATH, get_active_profile

            if AI_CONFIG_PATH.exists():
                profile = get_active_profile()
                adapter_key = profile.adapter
                adapter_label = f"{profile.name} ({SUPPORTED_ADAPTERS.get(adapter_key, adapter_key)})"
            else:
                adapter_key = settings.get("pipeline_adapter", "none")
                adapter_label = SUPPORTED_ADAPTERS.get(adapter_key, adapter_key)
        except Exception:
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
        if step_num == 7 and self._maybe_render_style_grid(step_num):
            self.after(60, self._expand_style_detail)
        else:
            self.after(60, self._restore_default_detail_height)

    def _maybe_render_style_grid(self, step_num: int) -> bool:
        confirmation = self._load_approved_style_confirmation()
        if confirmation is not None:
            self._render_style_confirmed_summary(confirmation)
            return True

        style_json = self._locate_style_options_json(step_num)
        if style_json is None:
            return False
        options = [
            item
            for item in style_json.get("options", [])
            if isinstance(item, dict) and item.get("style_id")
        ]
        if not options:
            return False

        self._style_var = tk.StringVar(value="")
        self._style_imgs: list[tk.PhotoImage] = []

        grid_shell = tk.Frame(self._detail, bg=COLORS["bg"])
        grid_shell.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        canvas = tk.Canvas(grid_shell, bg=COLORS["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(grid_shell, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=COLORS["bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfig(win_id, width=event.width),
        )
        inner.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        for index, option in enumerate(options):
            self._build_style_option_card(inner, option, index)

        footer = tk.Frame(self._detail, bg=COLORS["bg"], padx=12, pady=8)
        footer.pack(fill=tk.X)
        tk.Label(
            footer,
            text="批注",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W)
        self._style_notes = tk.Text(footer, height=3, wrap=tk.WORD, font=FONT_SMALL)
        self._style_notes.pack(fill=tk.X, pady=(2, 6))
        row_btn = tk.Frame(footer, bg=COLORS["bg"])
        row_btn.pack(anchor=tk.W)
        ttk.Button(
            row_btn,
            text="确认选择",
            command=lambda: self._on_style_confirm(options),
        ).pack(side=tk.LEFT)
        ttk.Button(
            row_btn,
            text="重新生成",
            command=lambda: self._open_prompt_editor(options),
        ).pack(side=tk.LEFT, padx=(8, 0))
        return True

    def _load_approved_style_confirmation(self) -> dict[str, Any] | None:
        path = ARTIFACTS_DIR / "stage_07" / "style_confirmation.json"
        if not path.exists():
            return None
        try:
            confirmation = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(confirmation, dict) and confirmation.get("status") == "approved":
            return confirmation
        return None

    def _render_style_confirmed_summary(self, confirmation: dict[str, Any]) -> None:
        frame = tk.Frame(self._detail, bg=COLORS["bg"], padx=16, pady=16)
        frame.pack(fill=tk.X)
        title = confirmation.get("selected_title") or confirmation.get("selected_style_id") or "已选择"
        tk.Label(
            frame,
            text=f"✓ 已确认风格：{title}",
            bg=COLORS["bg"],
            fg=COLORS["success"],
            font=FONT_SECTION,
        ).pack(anchor=tk.W)
        notes = str(confirmation.get("notes") or "").strip()
        if notes:
            tk.Label(
                frame,
                text=f"批注：{notes}",
                bg=COLORS["bg"],
                fg=COLORS["muted"],
                font=FONT_SMALL,
                wraplength=760,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=(4, 0))
        ttk.Button(
            frame,
            text="重新选择风格",
            command=self._reselect_style,
        ).pack(anchor=tk.W, pady=(12, 0))

    def _build_style_option_card(
        self, parent: tk.Widget, option: dict[str, Any], index: int
    ) -> None:
        row, col = index // 3, index % 3
        card = tk.Frame(
            parent,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=8,
            pady=8,
        )
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        parent.grid_columnconfigure(col, weight=1)

        image_label = tk.Label(card, bg=COLORS["surface"])
        image_label.pack(fill=tk.BOTH, expand=True)
        image_path_text = str(option.get("image_path") or "")
        try:
            from core.ui.style_confirmation_dialog import _resolve_image_path

            image_path = _resolve_image_path(image_path_text)
            image = tk.PhotoImage(file=str(image_path))
            while image.width() > 330 or image.height() > 225:
                image = image.subsample(2, 2)
            self._style_imgs.append(image)
            image_label.configure(image=image)
            image_label.configure(cursor="hand2")
            image_label.bind(
                "<Double-1>",
                lambda _event, path_text=image_path_text: self._show_image_fullscreen(path_text),
            )
        except (tk.TclError, OSError, ValueError):
            image_label.configure(
                text="图片不可用",
                fg=COLORS["danger"],
                font=FONT_SMALL,
                width=24,
                height=8,
            )

        suffix = "  推荐" if option.get("recommended") else ""
        score = option.get("score")
        score_text = f"  {score}分" if score not in (None, "") else ""
        title = f"{option.get('style_id')}  {option.get('title', '')}{suffix}{score_text}".strip()
        tk.Radiobutton(
            card,
            text=title,
            value=str(option.get("style_id")),
            variable=self._style_var,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["surface"],
            anchor=tk.W,
            wraplength=330,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, fill=tk.X, pady=(6, 2))
        tk.Label(
            card,
            text=str(option.get("description") or ""),
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            wraplength=330,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _on_style_confirm(self, options: list[dict[str, Any]]) -> None:
        style_var = getattr(self, "_style_var", None)
        selected_id = style_var.get() if style_var is not None else ""
        option = next(
            (item for item in options if str(item.get("style_id")) == selected_id),
            None,
        )
        if option is None:
            messagebox.showwarning("无法确认", "请先选择一个风格方案。", parent=self)
            return
        notes_widget = getattr(self, "_style_notes", None)
        notes = notes_widget.get("1.0", tk.END) if notes_widget is not None else ""
        from core.ui.style_confirmation_dialog import write_style_confirmation

        write_style_confirmation(ARTIFACTS_DIR / "stage_07", option, notes)
        self._exec_range(7, 7)

    def _on_style_regenerate(self) -> None:
        self._clear_style_confirmation()
        self._exec_range(7, 7)

    def _open_prompt_editor(self, options: list[dict[str, Any]]) -> None:
        try:
            from core.ui.style_prompt_editor import StylePromptEditorDialog

            StylePromptEditorDialog(
                self.winfo_toplevel(),
                options,
                self,
                output_dir=ARTIFACTS_DIR / "stage_07",
            )
        except Exception as exc:
            messagebox.showerror("提示词编辑失败", str(exc), parent=self)

    def _reselect_style(self) -> None:
        self._clear_style_confirmation()
        self.refresh()

    def _show_image_fullscreen(self, image_path_text: str) -> None:
        try:
            from core.ui.style_confirmation_dialog import _resolve_image_path

            image_path = _resolve_image_path(image_path_text)
            win = tk.Toplevel(self)
            win.title("图片预览（点击关闭）")
            win.configure(bg="#000000")
            image = tk.PhotoImage(file=str(image_path))
            while image.width() > 900 or image.height() > 700:
                image = image.subsample(2, 2)
            label = tk.Label(win, image=image, bg="#000000", cursor="hand2")
            label.image = image
            label.pack()
            label.bind("<Button-1>", lambda _event: win.destroy())
            win.bind("<Escape>", lambda _event: win.destroy())
        except (tk.TclError, OSError, ValueError):
            pass

    def _clear_style_confirmation(self) -> None:
        for filename in ("style_confirmation.json", "style_confirmation_pending.json"):
            path = ARTIFACTS_DIR / "stage_07" / filename
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def _locate_style_options_json(self, step_num: int) -> dict[str, Any] | None:
        _ = step_num
        candidates = [
            ARTIFACTS_DIR / "stage_07" / "art_style_options.json",
            ARTIFACTS_DIR / "stage_07" / "style_options.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            return data if isinstance(data, dict) else None
        return None

    def _expand_style_detail(self) -> None:
        total = self._right_paned.winfo_height()
        if total <= 120:
            return
        target = min(max(80, total - 100), total - 80)
        try:
            self._right_paned.sash_place(0, 0, target)
        except tk.TclError:
            pass

    def _restore_default_detail_height(self) -> None:
        total = self._right_paned.winfo_height()
        if total <= 240:
            return
        requested = self._detail.winfo_reqheight() + 24
        target = min(max(150, requested), total - 180)
        try:
            self._right_paned.sash_place(0, 0, target)
        except tk.TclError:
            pass

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

    def _open_ai_config(self):
        from core.ui.ai_config_unified_dialog import AIConfigUnifiedDialog

        AIConfigUnifiedDialog(self, on_saved=self.refresh)

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
        if self._locate_style_options_json(step_number) is not None:
            self._select_step(step_number)
            self._append_log("[风格确认] 请在右侧详情面板选择风格方案。\n")
            return
        try:
            from core.ui.style_confirmation_dialog import StyleConfirmationDialog

            style_options = self._load_style_options()
            output_step = 7 if step_number == 7 else step_number
            output_dir = ARTIFACTS_DIR / f"stage_{output_step:02d}"
            dialog = StyleConfirmationDialog(
                self.winfo_toplevel(), style_options, output_dir
            )
            result = dialog.wait_result()
            if result == "confirmed":
                self._exec_range(output_step, output_step)
            elif result == "regenerate":
                self._clear_style_confirmation()
                self._exec_range(7, 7)
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
