from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.design.ai_backend import (
    CodexCliBackend, CodexProcessRegistry, CodexRunResult,
    CodexUnavailableError, codex_available,
)
from core.design.ai_interview import (
    add_message, build_output_partition_prompt, build_interview_prompt,
    choose_output_domain_partitions, detect_force_output, ensure_ai_interview,
    new_memory_id, now_iso, record_prompt_runtime, should_force_readiness_check,
    update_conversation_summary, update_applicability_scores,
    update_route_overview, write_turn_replay,
)
from core.design.ai_mapping_agent import (
    build_mapping_prompt, project_state_hash,
    should_schedule_mapping, validate_mapping_payload,
)
from core.design.ai_summary_agent import (
    build_summary_correction_prompt, validate_summary_payload,
)
from core.design.ai_validator import (
    apply_high_confidence_output, format_differences,
    merge_partial_project_outputs, validate_partial_project_output,
    validate_full_project_output, validate_ai_response_payload,
)
from core.design.framework_memory import (
    complete_evaluation_batch, ensure_project_memory,
    record_ai_payload_context, record_backend_runtime_event,
    record_question_group_review, record_user_correction,
)
from core.design.exporter import safe_file_name
from core.ui.theme import COLORS, FONT_BODY, FONT_CARD, FONT_SECTION, FONT_SMALL


class EmbeddedInterviewPanel(tk.Frame):
    """AI 访谈嵌入面板 — 仅显示对话 + 输入 + 4个按钮，业务逻辑与 AIInterviewWindow 相同。"""

    def __init__(self, parent: tk.Widget, app):
        super().__init__(parent, bg=COLORS["surface"])
        self.app = app
        self.engine = app.engine
        self.project_state = app.project_state
        self.runtime_root = app.runtime_root
        self.process_registry = CodexProcessRegistry()
        self.backend = self._make_backend()
        self.running = False
        self.current_run_started_perf = None
        self.status_refresh_after_id = None
        self.mapping_jobs: dict = {}
        self.closed = False

        self.status_var = tk.StringVar(value="就绪")
        self.input_hint_var = tk.StringVar(value="请先描述项目方向，AI 会开始第一轮提问。")

        ensure_ai_interview(self.project_state)
        update_route_overview(self.engine, self.project_state)
        self._build_ui()
        self.render()

    def _build_ui(self):
        # 当前提问区
        q_frame = tk.Frame(self, bg=COLORS["surface"], padx=8, pady=4)
        q_frame.pack(fill=tk.X)
        tk.Label(q_frame, text="当前 AI 提问", bg=COLORS["surface"],
                 fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W)
        self.current_question_text = tk.Text(
            q_frame, height=3, bg=COLORS["ai_message_bg"], fg=COLORS["text"],
            bd=0, highlightthickness=1, highlightbackground=COLORS["ai_message_border"],
            wrap=tk.WORD, font=FONT_BODY, padx=6, pady=4, state=tk.DISABLED,
        )
        self.current_question_text.pack(fill=tk.X)

        # 对话区
        chat_frame = tk.Frame(self, bg=COLORS["surface"])
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=8)
        self.chat_text = tk.Text(
            chat_frame, bg=COLORS["surface"], fg=COLORS["text"],
            bd=0, highlightthickness=1, highlightbackground=COLORS["border"],
            wrap=tk.WORD, font=FONT_BODY, padx=6, pady=6, state=tk.DISABLED,
        )
        sb = ttk.Scrollbar(chat_frame, command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        # 输入区
        input_frame = tk.Frame(self, bg=COLORS["surface"], padx=8, pady=6)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(input_frame, textvariable=self.input_hint_var,
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor=tk.W, pady=(0, 4))
        self.input_text = tk.Text(
            input_frame, height=3, bg=COLORS["surface_alt"], fg=COLORS["text"],
            bd=0, highlightthickness=1, highlightbackground=COLORS["border"],
            wrap=tk.WORD, font=FONT_BODY, padx=8, pady=6,
        )
        self.input_text.pack(fill=tk.X)
        self.input_text.bind("<Control-Return>", self.submit_input_from_keyboard)

        status_bar = tk.Frame(input_frame, bg=COLORS["surface"])
        status_bar.pack(fill=tk.X, pady=(2, 4))
        tk.Label(status_bar, textvariable=self.status_var,
                 bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(side=tk.LEFT)

        btn_row = tk.Frame(input_frame, bg=COLORS["surface"])
        btn_row.pack(fill=tk.X)
        self.send_button = ttk.Button(btn_row, text="发送回答", command=self.send_user_message)
        self.send_button.pack(side=tk.LEFT, padx=(0, 6))
        self.output_button = ttk.Button(btn_row, text="生成输出", command=self.force_output)
        self.output_button.pack(side=tk.LEFT, padx=(0, 6))
        self.correction_button = ttk.Button(btn_row, text="标记不准", command=self.mark_last_ai_inaccurate)
        self.correction_button.pack(side=tk.LEFT, padx=(0, 6))
        self.archive_button = ttk.Button(btn_row, text="保存访谈存档", command=self.save_interview_archive_dialog)
        self.archive_button.pack(side=tk.LEFT)

    # ── 后端 ──────────────────────────────────────────────────────────────

    def _make_backend(self, timeout_seconds=None):
        if timeout_seconds is None:
            try:
                timeout_seconds = int(os.environ.get("AI_CODEX_TIMEOUT_SECONDS", "180"))
            except (TypeError, ValueError):
                timeout_seconds = 180
        return CodexCliBackend(
            self.runtime_root,
            workdir=self.runtime_root,
            timeout_seconds=max(30, int(timeout_seconds)),
            process_registry=self.process_registry,
        )

    def safe_after(self, callback):
        if self.closed:
            return
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except tk.TclError:
            pass

    def schedule_status_refresh(self):
        if self.closed or not self.running:
            return
        try:
            self.status_refresh_after_id = self.after(500, self.refresh_running_status)
        except tk.TclError:
            self.status_refresh_after_id = None

    def refresh_running_status(self):
        self.status_refresh_after_id = None
        if self.closed or not self.running:
            return
        self.render()
        self.schedule_status_refresh()

    def set_backend_stage(self, stage, turn_id="", schedule_render=True):
        ai_state = ensure_ai_interview(self.project_state)
        ai_state["backendStage"] = stage
        if turn_id:
            ai_state["activeTurnId"] = turn_id
        if stage in ("calling_codex", "calling_codex_partitions"):
            ai_state["backendStartedAt"] = now_iso()
        if stage in ("completed", "unavailable", "error", "cancelled"):
            ai_state["activeTurnId"] = ""
        self.app.project_state = self.project_state
        if schedule_render:
            self.safe_after(self.render)

    def set_running(self, value):
        self.running = value
        state = tk.DISABLED if value else tk.NORMAL
        self.send_button.configure(state=state)
        self.output_button.configure(state=state)
        self.correction_button.configure(state=state)
        self.status_var.set("AI 正在生成..." if value else "就绪")
        if value:
            self.schedule_status_refresh()
        elif self.status_refresh_after_id:
            try:
                self.after_cancel(self.status_refresh_after_id)
            except tk.TclError:
                pass
            self.status_refresh_after_id = None

    # ── 用户操作 ─────────────────────────────────────────────────────────

    def send_user_message(self):
        text = self.input_text.get("1.0", tk.END).strip()
        if not text or self.running:
            return
        self.input_text.delete("1.0", tk.END)
        self.run_ai_turn(text, force_output=False)

    def submit_input_from_keyboard(self, event=None):
        self.send_user_message()
        return "break"

    def force_output(self):
        if self.running:
            return
        self.run_ai_turn("请基于当前访谈生成 AI 全项目输出。", force_output=True)

    def mark_last_ai_inaccurate(self):
        if self.running:
            return
        ai_state = ensure_ai_interview(self.project_state)
        last_ai = ""
        for message in reversed(ai_state.get("messages", [])):
            if message.get("role") == "assistant":
                last_ai = message.get("content", "")
                break
        correction = "用户标记上一轮 AI 回答或映射不准确。" + (f" 摘要：{last_ai[:120]}" if last_ai else "")
        record_user_correction(self.runtime_root, self.project_state, correction,
                               target_module="mapping", signal_type="explicit_user_correction")
        update_conversation_summary(self.project_state, correction=correction)
        self.status_var.set("已记录反馈")

    # ── AI 轮次 ──────────────────────────────────────────────────────────

    def run_ai_turn(self, user_text, force_output=False):
        ai_state = ensure_ai_interview(self.project_state)
        ensure_project_memory(self.project_state, self.runtime_root)
        turn_id = new_memory_id("turn")
        add_message(ai_state, "user", user_text, meta={"turnId": turn_id})
        ai_state.update({"status": "running", "activeTurnId": turn_id,
                         "runStartedAt": now_iso(), "backendStartedAt": "",
                         "backendStage": "queued", "lastError": "", "awaitingUserAnswer": False})
        self.current_run_started_perf = time.perf_counter()
        self.app.project_state = self.project_state
        self.app.render()
        self.render()
        self.auto_save_interview_archive("user_submitted")
        self.set_running(True)
        threading.Thread(target=self.worker_run_ai_turn,
                         args=(user_text, force_output, turn_id), daemon=True).start()

    def worker_run_ai_turn(self, user_text, force_output, turn_id):
        try:
            self.set_backend_stage("building_prompt", turn_id)
            ai_state = ensure_ai_interview(self.project_state)
            should_output = force_output or detect_force_output(user_text)
            force_readiness = should_force_readiness_check(ai_state) and not should_output
            schema_mode = "full_output" if should_output else ("readiness" if force_readiness else "turn")
            if should_output:
                result = self.run_partitioned_output(user_text, turn_id)
                self.set_backend_stage("validating", turn_id)
                self.safe_after(lambda: self.handle_ai_result(result, turn_id))
                return
            prompt = build_interview_prompt(self.engine, self.project_state, user_text,
                                            force_output=should_output,
                                            force_readiness_check=force_readiness,
                                            runtime_root=self.runtime_root, turn_id=turn_id)
            self.set_backend_stage("calling_codex", turn_id)
            result = self.backend.run_turn(prompt, session_id="", schema_mode=schema_mode)
            self.set_backend_stage("validating", turn_id)
            self.safe_after(lambda: self.handle_ai_result(result, turn_id))
        except CodexUnavailableError as error:
            detail = str(error)
            self.safe_after(lambda detail=detail: self.handle_ai_unavailable(detail, turn_id))
        except Exception as error:
            detail = str(error)
            self.safe_after(lambda detail=detail: self.handle_ai_error(detail, turn_id))

    def run_partitioned_output(self, user_text, parent_turn_id):
        self.set_backend_stage("planning_partitions", parent_turn_id)
        partition_plan = choose_output_domain_partitions(self.engine, self.project_state,
                                                         user_text, runtime_root=self.runtime_root)
        partitions = partition_plan.get("partitions", [])
        if not partitions:
            raise RuntimeError("没有可用于分片输出的领域。")
        started_at = time.perf_counter()
        memory = ensure_project_memory(self.project_state, self.runtime_root)
        write_turn_replay(self.runtime_root, parent_turn_id, {
            "projectMemoryId": memory.get("projectMemoryId", ""),
            "evaluationBatchId": memory.get("evaluationBatchId", ""),
            "outputPartitionCount": len(partitions),
        })

        def run_partition(index, domain_ids):
            part_turn_id = f"{parent_turn_id}_part{index + 1}"
            prompt = build_output_partition_prompt(self.engine, self.project_state, user_text,
                                                   domain_ids, partition_index=index + 1,
                                                   partition_count=len(partitions),
                                                   runtime_root=self.runtime_root, turn_id=part_turn_id)
            backend = self._make_backend()
            result = backend.run_turn(prompt, session_id="", schema_mode="partial_output")
            errors = validate_partial_project_output(self.engine, result.payload, allowed_domain_ids=domain_ids)
            record_prompt_runtime(self.runtime_root, part_turn_id, result,
                                  validation_errors=errors, mode=result.payload.get("mode", ""))
            write_turn_replay(self.runtime_root, part_turn_id, {
                "response": result.payload,
                "validationResult": {"ok": not errors, "errors": errors},
            })
            if errors:
                raise RuntimeError(f"分片 {index + 1} 输出校验失败：{'；'.join(errors[:6])}")
            return result

        max_workers = max(1, min(int(os.environ.get("AI_OUTPUT_PARTITION_MAX_WORKERS", "4")), len(partitions)))
        self.set_backend_stage("calling_codex_partitions", parent_turn_id)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(run_partition, i, d): i for i, d in enumerate(partitions)}
            ordered = [None] * len(partitions)
            for future in as_completed(future_map):
                ordered[future_map[future]] = future.result()
        self.set_backend_stage("merging_output", parent_turn_id)
        merged_payload, errors = merge_partial_project_outputs(
            self.engine, self.project_state, [r.payload for r in ordered if r])
        if errors:
            raise RuntimeError("分片输出合并失败：" + "；".join(errors[:8]))
        duration = time.perf_counter() - started_at
        first_events = [r.first_event_seconds for r in ordered if r and r.first_event_seconds is not None]
        return CodexRunResult(
            payload=merged_payload, session_id="",
            raw_output="\n".join(r.raw_output for r in ordered if r and r.raw_output),
            raw_events=[e for r in ordered if r for e in (r.raw_events or [])],
            duration_seconds=duration,
            first_event_seconds=min(first_events) if first_events else None,
            response_chars=sum(r.response_chars for r in ordered if r),
        )

    # ── 结果处理 ─────────────────────────────────────────────────────────

    def handle_ai_result(self, result, turn_id=""):
        payload = result.payload
        session_id = result.session_id
        ai_state = ensure_ai_interview(self.project_state)
        self.set_backend_stage("validating", turn_id, schedule_render=False)
        ai_state["status"] = "processing_result"
        ai_state["lastBackendDurationSeconds"] = round(float(result.duration_seconds or 0), 4)
        ai_state["lastFirstEventSeconds"] = (
            round(float(result.first_event_seconds), 4) if result.first_event_seconds is not None else None)
        if session_id:
            if ai_state.get("codexSessionId") == session_id:
                ai_state["sessionTurnCount"] = ai_state.get("sessionTurnCount", 0) + 1
            else:
                ai_state["sessionTurnCount"] = 1
            ai_state["codexSessionId"] = session_id
        validation_seconds = 0.0
        t0 = time.perf_counter()
        errors = validate_full_project_output(self.engine, payload)
        validation_seconds += time.perf_counter() - t0
        if errors:
            record_ai_payload_context(self.runtime_root, self.project_state, payload, validation_errors=errors)
            complete_evaluation_batch(self.runtime_root, self.project_state, reason="validation_failed")
            ai_state.update({"status": "validation_failed", "backendStage": "validation_failed",
                             "activeTurnId": "", "lastError": "\n".join(errors)})
            add_message(ai_state, "assistant", payload.get("assistantMessage", "AI 输出需要修正。"))
            add_message(ai_state, "system", "AI 输出校验失败：\n" + "\n".join(errors))
            record_prompt_runtime(self.runtime_root, turn_id, result,
                                  validation_seconds=validation_seconds, validation_errors=errors,
                                  mode=payload.get("mode", ""))
            write_turn_replay(self.runtime_root, turn_id, {"response": payload,
                "validationResult": {"ok": False, "errors": errors}})
            self.current_run_started_perf = None
            self.set_running(False)
            self.auto_save_interview_archive("validation_failed")
            self.render()
            return
        t0 = time.perf_counter()
        payload_errors = validate_ai_response_payload(payload)
        validation_seconds += time.perf_counter() - t0
        if payload_errors:
            record_ai_payload_context(self.runtime_root, self.project_state, payload, validation_errors=payload_errors)
            complete_evaluation_batch(self.runtime_root, self.project_state, reason="payload_validation_failed")
            ai_state.update({"status": "validation_failed", "backendStage": "validation_failed",
                             "activeTurnId": "", "lastError": "\n".join(payload_errors)})
            add_message(ai_state, "system", "AI 输出校验失败：\n" + "\n".join(payload_errors))
            record_prompt_runtime(self.runtime_root, turn_id, result,
                                  validation_seconds=validation_seconds, validation_errors=payload_errors,
                                  mode=payload.get("mode", ""))
            self.current_run_started_perf = None
            self.set_running(False)
            self.auto_save_interview_archive("payload_validation_failed")
            self.render()
            return
        mode = payload.get("mode")
        question_group = payload.get("questionGroup")
        raw_assistant = payload.get("assistantMessage", "")
        assistant_content = self._assistant_message_with_questions(raw_assistant, question_group)
        add_message(ai_state, "assistant", assistant_content, meta={
            "turnId": turn_id, "mode": mode,
            "questionGroup": question_group if isinstance(question_group, dict) else None,
        })
        route = payload.get("routeOverview")
        if isinstance(route, dict):
            ai_state["routeOverview"] = route
        if isinstance(payload.get("inferences"), list):
            ai_state["inferences"].extend(payload["inferences"])
            update_applicability_scores(self.project_state, payload["inferences"])
        if mode == "question_group" and isinstance(question_group, dict):
            qlines = self._format_question_group(question_group)
            ai_state["currentQuestionText"] = "\n".join([
                f"第 {ai_state.get('questionGroupCount', 0) + 1} 轮 - AI 提问：", assistant_content])
            ai_state["currentQuestionTurnId"] = turn_id
            ai_state["currentQuestionCount"] = len(qlines)
            ai_state["awaitingUserAnswer"] = bool(qlines)
            ai_state["questionGroupCount"] = ai_state.get("questionGroupCount", 0) + 1
            record_question_group_review(self.runtime_root, self.project_state, payload)
        should_correct_summary = mode == "readiness_check"
        if should_correct_summary:
            ai_state["lastReadinessCheckGroup"] = ai_state.get("questionGroupCount", 0)
        update_conversation_summary(self.project_state, payload)
        if should_correct_summary:
            self._schedule_summary_correction(turn_id)
        apply_seconds = 0.0
        differences = []
        should_map = False
        if mode == "full_project_output" or payload.get("fullProjectOutput"):
            self.set_backend_stage("applying", turn_id, schedule_render=False)
            t0 = time.perf_counter()
            self.project_state, differences = apply_high_confidence_output(
                self.engine, self.project_state, payload)
            apply_seconds = time.perf_counter() - t0
            self.app.project_state = self.project_state
            ensure_ai_interview(self.project_state)["status"] = "output_applied"
            record_ai_payload_context(self.runtime_root, self.project_state, payload, differences=differences)
            complete_evaluation_batch(self.runtime_root, self.project_state, reason="full_project_output_applied")
            diff_lines = format_differences(differences, limit=40)
            add_message(ensure_ai_interview(self.project_state), "system",
                        "AI 全项目输出已自动应用高置信内容。选项差异：\n" + "\n".join(diff_lines))
            if hasattr(self.app, "sync_profile_labels"):
                self.app.sync_profile_labels()
            if hasattr(self.app, "clear_expanded_nodes"):
                self.app.clear_expanded_nodes()
            self.app.render()
        else:
            ai_state["status"] = "idle"
            self.app.project_state = self.project_state
            should_map = True
        self.project_state = self.app.project_state
        record_prompt_runtime(self.runtime_root, turn_id, result,
                              validation_seconds=validation_seconds, apply_seconds=apply_seconds,
                              validation_errors=[], mode=mode)
        write_turn_replay(self.runtime_root, turn_id, {
            "response": payload, "validationResult": {"ok": True, "errors": []},
            "differences": differences})
        ai_state = ensure_ai_interview(self.project_state)
        ai_state["backendStage"] = "completed"
        ai_state["activeTurnId"] = ""
        self.current_run_started_perf = None
        self.set_running(False)
        self.auto_save_interview_archive("turn_completed")
        self.render()
        if should_map:
            self._schedule_background_mapping(turn_id)

    def handle_ai_unavailable(self, detail="", turn_id=""):
        ai_state = ensure_ai_interview(self.project_state)
        self.set_backend_stage("unavailable", turn_id, schedule_render=False)
        record_backend_runtime_event(self.runtime_root, self.project_state,
                                     "codex_unavailable", "Codex 后端暂时不可用。", detail)
        ai_state.update({"status": "unavailable", "lastError": "网络问题，AI 暂时不可用。"})
        add_message(ai_state, "system", "网络问题，AI 暂时不可用。")
        record_prompt_runtime(self.runtime_root, turn_id, validation_errors=["codex_unavailable"], mode="unavailable")
        write_turn_replay(self.runtime_root, turn_id, {"response": None,
            "validationResult": {"ok": False, "errors": ["codex_unavailable"]}, "backendError": detail})
        self.current_run_started_perf = None
        self.set_running(False)
        self.auto_save_interview_archive("backend_unavailable")
        self.render()
        messagebox.showwarning("AI 暂时不可用", "网络问题，AI 暂时不可用。",
                               parent=self.winfo_toplevel())

    def handle_ai_error(self, message, turn_id=""):
        ai_state = ensure_ai_interview(self.project_state)
        self.set_backend_stage("error", turn_id, schedule_render=False)
        record_backend_runtime_event(self.runtime_root, self.project_state, "ai_turn_error", "AI 处理异常。", message)
        ai_state.update({"status": "error", "lastError": message})
        add_message(ai_state, "system", f"AI 处理失败：{message}")
        record_prompt_runtime(self.runtime_root, turn_id, validation_errors=[message], mode="error")
        write_turn_replay(self.runtime_root, turn_id, {"response": None,
            "validationResult": {"ok": False, "errors": [message]}, "backendError": message})
        self.current_run_started_perf = None
        self.set_running(False)
        self.auto_save_interview_archive("ai_error")
        self.render()

    # ── 渲染 ─────────────────────────────────────────────────────────────

    def render(self):
        self.project_state = self.app.project_state
        ai_state = ensure_ai_interview(self.project_state)
        self.write_chat_messages(self.chat_text, ai_state.get("messages", []))
        self.write_text(self.current_question_text, self._latest_question_panel_lines(ai_state))
        self.input_hint_var.set(self._input_hint_for_state(ai_state))

    def write_text(self, widget, lines):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, "\n".join(lines))
        widget.configure(state=tk.DISABLED)

    def _configure_chat_tags(self, widget):
        for tag, opts in {
            "user_header":      {"background": COLORS["user_message_border"], "foreground": "#FFFFFF", "font": FONT_CARD, "lmargin1": 6, "lmargin2": 6, "spacing1": 8, "spacing3": 0},
            "user_body":        {"background": COLORS["user_message_bg"],     "foreground": COLORS["text"], "lmargin1": 14, "lmargin2": 14, "rmargin": 10, "spacing3": 2},
            "assistant_header": {"background": COLORS["ai_message_border"],   "foreground": "#FFFFFF", "font": FONT_CARD, "lmargin1": 6, "lmargin2": 6, "spacing1": 8, "spacing3": 0},
            "assistant_body":   {"background": COLORS["ai_message_bg"],       "foreground": COLORS["text"], "lmargin1": 14, "lmargin2": 14, "rmargin": 10, "spacing3": 2},
            "system_header":    {"background": COLORS["system_message_border"],"foreground": "#FFFFFF", "font": FONT_CARD, "lmargin1": 6, "lmargin2": 6, "spacing1": 8, "spacing3": 0},
            "system_body":      {"background": COLORS["system_message_bg"],   "foreground": COLORS["text"], "lmargin1": 14, "lmargin2": 14, "rmargin": 10, "spacing3": 2},
            "message_gap":      {"spacing3": 8},
        }.items():
            widget.tag_configure(tag, **opts)

    def _insert_chat_block(self, widget, kind, title, lines):
        header_tag = f"{kind}_header" if kind in {"user", "assistant", "system"} else "system_header"
        body_tag = f"{kind}_body" if kind in {"user", "assistant", "system"} else "system_body"
        widget.insert(tk.END, f"{title}\n", header_tag)
        for line in lines or ["（无内容）"]:
            widget.insert(tk.END, f"{line}\n", body_tag)
        widget.insert(tk.END, "\n", "message_gap")

    def write_chat_messages(self, widget, messages):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        self._configure_chat_tags(widget)
        if not messages:
            self._insert_chat_block(widget, "assistant", "AI 提问", [
                "请先描述你想做的游戏方向、目标玩家、核心体验或目前最不确定的地方。"])
            widget.configure(state=tk.DISABLED)
            return
        for msg in messages:
            role = msg.get("role", "system")
            content = str(msg.get("content", "")).strip()
            if role == "user":
                self._insert_chat_block(widget, "user", "你", content.splitlines() or [""])
            elif role == "assistant":
                self._insert_chat_block(widget, "assistant", "AI", content.splitlines() or [""])
            else:
                self._insert_chat_block(widget, "system", "系统", content.splitlines() or [""])
        widget.configure(state=tk.DISABLED)
        widget.see(tk.END)

    def _format_question_group(self, question_group):
        if not isinstance(question_group, dict):
            return []
        questions = question_group.get("questions")
        if not isinstance(questions, list):
            return []
        lines = []
        for i, q in enumerate(questions[:4], 1):
            text = str(q.get("text", "") if isinstance(q, dict) else q).strip()
            if text:
                lines.append(f"{i}. {text}")
        return lines

    def _assistant_message_with_questions(self, assistant_message, question_group):
        content = str(assistant_message or "").strip()
        qlines = self._format_question_group(question_group)
        if not qlines:
            return content
        return content + ("\n\n" if content else "") + "\n".join(qlines)

    def _latest_question_panel_lines(self, ai_state):
        text = str(ai_state.get("currentQuestionText", "")).strip()
        if text:
            return text.splitlines()
        messages = ai_state.get("messages", [])
        if not messages:
            return ["AI 尚未生成提问。请先在下方输入项目方向。"]
        for msg in reversed(messages):
            if msg.get("role") != "assistant":
                continue
            meta = msg.get("meta", {})
            if isinstance(meta, dict):
                qlines = self._format_question_group(meta.get("questionGroup"))
                if qlines:
                    return [str(msg.get("content", ""))] + [""] + qlines
        return ["请在下方输入你的回答或项目方向。"]

    def _input_hint_for_state(self, ai_state):
        if self.running:
            return "AI 正在生成下一组提问，请等待。"
        if ai_state.get("awaitingUserAnswer") and str(ai_state.get("currentQuestionText", "")).strip():
            return '请回答上方"当前 AI 提问"；可以逐条回答，也可以合并说明。'
        for msg in reversed(ai_state.get("messages", [])):
            if msg.get("role") == "assistant":
                return "可以继续补充你的想法，AI 会基于上下文继续追问。"
            if msg.get("role") == "user":
                return "你的回答已发送；如果没有看到 AI 提问，请等待。"
        return "请先描述项目方向，AI 会开始第一轮提问。"

    # ── 存档 ─────────────────────────────────────────────────────────────

    def interview_archive_dir(self):
        path = self.runtime_root / "ai_interview_archives"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_interview_archive_id(self, ai_state):
        if not ai_state.get("interviewArchiveId"):
            ai_state["interviewArchiveId"] = new_memory_id("interview_archive")
        return ai_state["interviewArchiveId"]

    def archive_project_label(self):
        name = self.project_state.get("projectName") or getattr(self.app, "project_name", None)
        if hasattr(name, "get"):
            name = name.get()
        return safe_file_name(name or "ai-interview", fallback="ai-interview")

    def write_interview_archive(self, path, reason="manual"):
        ai_state = ensure_ai_interview(self.project_state)
        self.ensure_interview_archive_id(ai_state)
        ai_state["lastArchivedAt"] = now_iso()
        memory = ensure_project_memory(self.project_state, self.runtime_root)
        payload = {
            "archiveVersion": "1.0", "archiveType": "ai_interview",
            "archiveId": ai_state["interviewArchiveId"], "createdAt": now_iso(), "reason": reason,
            "projectName": self.project_state.get("projectName", ""),
            "profile": self.project_state.get("profile", {}),
            "session": {"codexSessionId": ai_state.get("codexSessionId", ""),
                        "sessionTurnCount": ai_state.get("sessionTurnCount", 0),
                        "questionGroupCount": ai_state.get("questionGroupCount", 0),
                        "status": ai_state.get("status", "")},
            "messages": ai_state.get("messages", []),
            "summary": ai_state.get("summary", {}),
            "runtimeRefs": {"projectMemoryId": memory.get("projectMemoryId", ""),
                            "runtimeRoot": str(self.runtime_root)},
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if reason == "manual":
            ai_state["lastManualArchivePath"] = str(path)
        else:
            try:
                ai_state["autoArchivePath"] = str(path.relative_to(self.runtime_root))
            except ValueError:
                ai_state["autoArchivePath"] = str(path)
        self.app.project_state = self.project_state
        return path

    def auto_save_interview_archive(self, reason):
        try:
            ai_state = ensure_ai_interview(self.project_state)
            archive_id = self.ensure_interview_archive_id(ai_state)
            stored_path = ai_state.get("autoArchivePath", "")
            if stored_path:
                path = Path(stored_path)
                if not path.is_absolute():
                    path = self.runtime_root / path
            else:
                path = self.interview_archive_dir() / f"{self.archive_project_label()}_{archive_id}.json"
            self.write_interview_archive(path, reason=reason)
        except Exception as error:
            ensure_ai_interview(self.project_state)["lastError"] = f"AI 访谈自动存档失败：{error}"

    def save_interview_archive_dialog(self):
        ai_state = ensure_ai_interview(self.project_state)
        self.ensure_interview_archive_id(ai_state)
        default_name = f"{self.archive_project_label()}_{time.strftime('%Y%m%d_%H%M%S')}.ai_interview.json"
        path = filedialog.asksaveasfilename(
            title="保存 AI 访谈存档", defaultextension=".json",
            filetypes=[("AI 访谈存档", "*.json"), ("JSON", "*.json")],
            initialdir=str(self.interview_archive_dir()), initialfile=default_name,
            parent=self.winfo_toplevel(),
        )
        if not path:
            return
        try:
            saved_path = self.write_interview_archive(path, reason="manual")
        except OSError as error:
            messagebox.showerror("保存失败", f"无法写入：\n{error}", parent=self.winfo_toplevel())
            return
        self.status_var.set(f"已保存：{saved_path}")
        messagebox.showinfo("保存访谈存档", f"已保存：\n{saved_path}", parent=self.winfo_toplevel())

    # ── 后台 mapping / summary ────────────────────────────────────────────

    def _schedule_background_mapping(self, turn_id):
        ai_state = ensure_ai_interview(self.project_state)
        user_text = next((m.get("content", "") for m in reversed(ai_state.get("messages", []))
                          if m.get("role") == "user" and m.get("meta", {}).get("turnId") == turn_id), "")
        if not should_schedule_mapping(self.engine, self.project_state, user_text, force_output=False):
            return
        job_id = f"{turn_id}_mapping"
        if job_id in self.mapping_jobs:
            return
        state_hash = project_state_hash(self.engine, self.project_state)
        self.mapping_jobs[job_id] = {"basedOnTurnId": turn_id, "projectStateHash": state_hash}
        threading.Thread(target=self._worker_background_mapping,
                         args=(job_id, turn_id, user_text, state_hash), daemon=True).start()

    def _worker_background_mapping(self, job_id, turn_id, user_text, state_hash):
        try:
            prompt = build_mapping_prompt(self.engine, self.project_state, user_text,
                                          self.runtime_root, turn_id=job_id)
            result = self._make_backend(timeout_seconds=60).run_turn(prompt, session_id="", schema_mode="mapping")
            self.safe_after(lambda: self._handle_mapping_result(job_id, turn_id, state_hash, result))
        except Exception as error:
            detail = str(error)
            self.safe_after(lambda detail=detail: self.mapping_jobs.pop(job_id, None))

    def _handle_mapping_result(self, job_id, turn_id, state_hash, result):
        self.mapping_jobs.pop(job_id, None)
        current_hash = project_state_hash(self.engine, self.project_state)
        if current_hash == state_hash and not validate_mapping_payload(self.engine, result.payload):
            record_prompt_runtime(self.runtime_root, job_id, result, mode="mapping")

    def _schedule_summary_correction(self, turn_id):
        threading.Thread(target=self._worker_summary_correction,
                         args=(turn_id,), daemon=True).start()

    def _worker_summary_correction(self, turn_id):
        try:
            prompt = build_summary_correction_prompt(self.engine, self.project_state,
                                                     self.runtime_root, turn_id=turn_id)
            result = self._make_backend(timeout_seconds=60).run_turn(prompt, session_id="", schema_mode="summary")
            if not validate_summary_payload(result.payload):
                self.safe_after(self.render)
        except Exception:
            pass
