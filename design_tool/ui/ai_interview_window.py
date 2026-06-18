import threading
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from design_tool.ai_backend import (
    CodexCliBackend,
    CodexProcessRegistry,
    CodexRunResult,
    CodexUnavailableError,
    codex_available,
    project_api_config_summary,
)
from design_tool.ai_interview import (
    add_message,
    build_output_partition_prompt,
    build_interview_prompt,
    choose_output_domain_partitions,
    detect_force_output,
    ensure_ai_interview,
    new_memory_id,
    now_iso,
    record_prompt_runtime,
    should_force_readiness_check,
    update_conversation_summary,
    update_applicability_scores,
    update_route_overview,
    write_turn_replay,
)
from design_tool.ai_mapping_agent import (
    build_mapping_prompt,
    project_state_hash,
    should_schedule_mapping,
    validate_mapping_payload,
)
from design_tool.ai_summary_agent import build_summary_correction_prompt, validate_summary_payload
from design_tool.ai_validator import (
    apply_high_confidence_output,
    format_differences,
    merge_partial_project_outputs,
    validate_partial_project_output,
    validate_full_project_output,
    validate_ai_response_payload,
)
from design_tool.framework_memory import (
    complete_evaluation_batch,
    ensure_project_memory,
    record_ai_payload_context,
    record_backend_runtime_event,
    record_question_group_review,
    record_user_correction,
)
from design_tool.exporter import safe_file_name
from design_tool.ui.theme import COLORS, FONT_BODY, FONT_CARD, FONT_SECTION, FONT_SMALL, FONT_TITLE


BACKEND_STAGE_LABELS = {
    "idle": "空闲",
    "queued": "已接收输入",
    "building_prompt": "构建 prompt",
    "planning_partitions": "规划分片输出",
    "calling_codex": "已启动 Codex CLI",
    "calling_codex_partitions": "并发调用 Codex CLI 分片",
    "waiting_codex": "等待 Codex 返回",
    "merging_output": "合并分片输出",
    "validating": "模型已返回，正在校验/写入",
    "validation_failed": "输出校验失败",
    "applying": "应用高置信输出",
    "completed": "本轮完成",
    "unavailable": "后端不可用",
    "error": "处理异常",
    "cancelled": "已取消",
}


AI_STATUS_LABELS = {
    "idle": "空闲",
    "running": "模型调用中",
    "processing_result": "处理模型返回结果",
    "output_applied": "已应用输出",
    "validation_failed": "输出校验失败",
    "unavailable": "后端不可用",
    "error": "处理异常",
    "cancelled": "已取消",
}


class AIInterviewWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.engine = app.engine
        self.project_state = app.project_state
        self.runtime_root = app.runtime_root
        self.process_registry = CodexProcessRegistry()
        self.backend = self.make_backend()
        self.running = False
        self.current_run_started_perf = None
        self.status_refresh_after_id = None
        self.closed = False
        self.mapping_jobs = {}

        self.title("AI 访谈")
        self.geometry("1120x760")
        self.minsize(920, 620)
        self.resizable(True, True)
        self.configure(bg=COLORS["bg"])

        ensure_ai_interview(self.project_state)
        update_route_overview(self.engine, self.project_state)
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.render()

    def make_backend(self, timeout_seconds=None):
        if timeout_seconds is None:
            try:
                timeout_seconds = int(os.environ.get("AI_CODEX_TIMEOUT_SECONDS", "180"))
            except (TypeError, ValueError):
                timeout_seconds = 180
        timeout_seconds = max(30, int(timeout_seconds))
        return CodexCliBackend(
            self.runtime_root,
            workdir=self.runtime_root,
            timeout_seconds=timeout_seconds,
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

    def close_window(self):
        if self.closed:
            return
        active_count = self.process_registry.active_count()
        if active_count or self.running:
            ai_state = ensure_ai_interview(self.project_state)
            ai_state["status"] = "cancelled"
            ai_state["backendStage"] = "cancelled"
            ai_state["activeTurnId"] = ""
            message = (
                f"AI 访谈窗口已关闭，已终止本窗口启动的 {active_count} 个 Codex CLI 进程。"
                if active_count
                else "AI 访谈窗口已关闭，已取消当前 AI 访谈任务。"
            )
            add_message(
                ai_state,
                "system",
                message,
            )
            self.app.project_state = self.project_state
        self.closed = True
        self.process_registry.cancel_all()
        self.mapping_jobs.clear()
        self.running = False
        self.current_run_started_perf = None
        if self.status_refresh_after_id:
            try:
                self.after_cancel(self.status_refresh_after_id)
            except tk.TclError:
                pass
            self.status_refresh_after_id = None
        if getattr(self.app, "ai_window", None) is self:
            self.app.ai_window = None
        try:
            self.destroy()
        except tk.TclError:
            pass

    def build_ui(self):
        header = tk.Frame(self, bg=COLORS["surface"], padx=14, pady=12)
        header.pack(side=tk.TOP, fill=tk.X)
        tk.Label(header, text="AI 访谈", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_TITLE).pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.status_var, bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL).pack(side=tk.RIGHT)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        left = tk.Frame(paned, bg=COLORS["surface"], padx=10, pady=10, highlightthickness=1, highlightbackground=COLORS["border"])
        middle = tk.Frame(paned, bg=COLORS["surface"], padx=10, pady=10, highlightthickness=1, highlightbackground=COLORS["border"])
        right = tk.Frame(paned, bg=COLORS["surface"], padx=10, pady=10, highlightthickness=1, highlightbackground=COLORS["border"])
        paned.add(left, weight=2)
        paned.add(middle, weight=5)
        paned.add(right, weight=3)

        tk.Label(left, text="路线概览", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        self.route_text = self.readonly_text(left, height=20)
        self.route_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        tk.Label(middle, text="当前 AI 提问", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        self.current_question_text = self.readonly_text(
            middle,
            height=7,
            bg=COLORS["ai_message_bg"],
            border_color=COLORS["ai_message_border"],
            border_width=2,
        )
        self.current_question_text.pack(fill=tk.X, pady=(8, 8))

        tk.Label(middle, text="访谈对话", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        self.chat_text = self.readonly_text(middle, height=15, border_color=COLORS["border"], border_width=1)
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

        input_frame = tk.Frame(middle, bg=COLORS["surface"])
        input_frame.pack(fill=tk.X)
        self.input_hint_var = tk.StringVar(value="请先描述项目方向，AI 会开始第一轮提问。")
        tk.Label(
            input_frame,
            textvariable=self.input_hint_var,
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W, pady=(0, 4))
        self.input_text = tk.Text(
            input_frame,
            height=4,
            bg=COLORS["surface_alt"],
            fg=COLORS["text"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            wrap=tk.WORD,
            font=FONT_BODY,
            padx=8,
            pady=6,
        )
        self.input_text.pack(fill=tk.X)
        self.input_text.bind("<Control-Return>", self.submit_input_from_keyboard)
        self.input_text.bind("<Control-KP_Enter>", self.submit_input_from_keyboard)
        self.input_text.focus_set()
        buttons = tk.Frame(input_frame, bg=COLORS["surface"])
        buttons.pack(fill=tk.X, pady=(8, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        self.send_button = ttk.Button(buttons, text="发送回答", command=self.send_user_message)
        self.send_button.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6))
        self.output_button = ttk.Button(buttons, text="生成输出", command=self.force_output)
        self.output_button.grid(row=1, column=0, sticky=tk.EW, padx=(0, 4))
        self.correction_button = ttk.Button(buttons, text="标记不准", command=self.mark_last_ai_inaccurate)
        self.correction_button.grid(row=1, column=1, sticky=tk.EW, padx=(4, 0))
        self.archive_button = ttk.Button(buttons, text="保存访谈存档", command=self.save_interview_archive_dialog)
        self.archive_button.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

        tk.Label(right, text="输出差异", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        self.diff_text = self.readonly_text(right, height=16)
        self.diff_text.pack(fill=tk.BOTH, expand=True, pady=(8, 10))
        tk.Label(right, text="状态", bg=COLORS["surface"], fg=COLORS["text"], font=FONT_SECTION).pack(anchor=tk.W)
        self.detail_text = self.readonly_text(right, height=10)
        self.detail_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def readonly_text(self, parent, height, bg=None, border_color=None, border_width=0):
        text = tk.Text(
            parent,
            height=height,
            bg=bg or COLORS["surface"],
            fg=COLORS["text"],
            bd=0,
            highlightthickness=border_width,
            highlightbackground=border_color or COLORS["border"],
            highlightcolor=border_color or COLORS["border"],
            wrap=tk.WORD,
            font=FONT_BODY,
            padx=6,
            pady=6,
        )
        text.configure(state=tk.DISABLED)
        return text

    def write_text(self, widget, lines):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, "\n".join(lines))
        widget.configure(state=tk.DISABLED)

    def configure_chat_tags(self, widget):
        tag_specs = {
            "user_header": {
                "background": COLORS["user_message_border"],
                "foreground": "#FFFFFF",
                "font": FONT_CARD,
                "lmargin1": 6,
                "lmargin2": 6,
                "spacing1": 8,
                "spacing3": 0,
            },
            "user_body": {
                "background": COLORS["user_message_bg"],
                "foreground": COLORS["text"],
                "lmargin1": 14,
                "lmargin2": 14,
                "rmargin": 10,
                "spacing3": 2,
            },
            "assistant_header": {
                "background": COLORS["ai_message_border"],
                "foreground": "#FFFFFF",
                "font": FONT_CARD,
                "lmargin1": 6,
                "lmargin2": 6,
                "spacing1": 8,
                "spacing3": 0,
            },
            "assistant_body": {
                "background": COLORS["ai_message_bg"],
                "foreground": COLORS["text"],
                "lmargin1": 14,
                "lmargin2": 14,
                "rmargin": 10,
                "spacing3": 2,
            },
            "system_header": {
                "background": COLORS["system_message_border"],
                "foreground": "#FFFFFF",
                "font": FONT_CARD,
                "lmargin1": 6,
                "lmargin2": 6,
                "spacing1": 8,
                "spacing3": 0,
            },
            "system_body": {
                "background": COLORS["system_message_bg"],
                "foreground": COLORS["text"],
                "lmargin1": 14,
                "lmargin2": 14,
                "rmargin": 10,
                "spacing3": 2,
            },
            "message_gap": {"spacing3": 8},
        }
        for tag, options in tag_specs.items():
            widget.tag_configure(tag, **options)

    def insert_chat_block(self, widget, kind, title, lines):
        header_tag = f"{kind}_header" if kind in {"user", "assistant", "system"} else "system_header"
        body_tag = f"{kind}_body" if kind in {"user", "assistant", "system"} else "system_body"
        widget.insert(tk.END, f"{title}\n", header_tag)
        for line in lines or ["（无内容）"]:
            widget.insert(tk.END, f"{line}\n", body_tag)
        widget.insert(tk.END, "\n", "message_gap")

    def write_chat_messages(self, widget, messages):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        self.configure_chat_tags(widget)
        if not messages:
            self.insert_chat_block(
                widget,
                "assistant",
                "第 0 轮 - AI 提问",
                [
                    "请先描述你想做的游戏方向、目标玩家、核心体验或目前最不确定的地方。",
                    "AI 会按 MDA 路线追问；每组最多 4 个问题。",
                ],
            )
            widget.configure(state=tk.DISABLED)
            widget.see(tk.END)
            return

        turn_index = 0
        for message in messages[-80:]:
            role = message.get("role", "")
            content = str(message.get("content", "")).strip()
            content_lines = content.splitlines() if content else ["（无内容）"]
            meta = message.get("meta", {})
            question_lines = []
            if isinstance(meta, dict):
                question_lines = self.format_question_group_for_chat(meta.get("questionGroup"))

            if role == "user":
                turn_index += 1
                self.insert_chat_block(widget, "user", f"第 {turn_index} 轮 - 你的回答", content_lines)
            elif role == "assistant":
                current_turn = max(turn_index, 1)
                if question_lines and not any(line in content for line in question_lines):
                    content_lines = content_lines + ["", "请回答：", *question_lines]
                title = f"第 {current_turn} 轮 - AI 提问" if question_lines else f"第 {current_turn} 轮 - AI 回复"
                self.insert_chat_block(widget, "assistant", title, content_lines)
            elif role == "system":
                self.insert_chat_block(widget, "system", "系统提示", content_lines)
            else:
                self.insert_chat_block(widget, "system", str(role or "消息"), content_lines)
        widget.configure(state=tk.DISABLED)
        widget.see(tk.END)

    def record_render_snapshot(self, ai_state, chat_lines, question_lines, status_lines):
        try:
            path = self.runtime_root / "ai_runtime" / "ui_interview_last_render.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "createdAt": now_iso(),
                "status": ai_state.get("status", ""),
                "backendStage": ai_state.get("backendStage", ""),
                "activeTurnId": ai_state.get("activeTurnId", ""),
                "currentQuestionTurnId": ai_state.get("currentQuestionTurnId", ""),
                "currentQuestionCount": ai_state.get("currentQuestionCount", 0),
                "awaitingUserAnswer": ai_state.get("awaitingUserAnswer", False),
                "messageCount": len(ai_state.get("messages", [])),
                "chatText": "\n".join(chat_lines),
                "currentQuestionText": "\n".join(question_lines),
                "statusText": "\n".join(status_lines),
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def interview_archive_dir(self):
        path = self.runtime_root / "ai_interview_archives"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_interview_archive_id(self, ai_state):
        archive_id = ai_state.get("interviewArchiveId", "")
        if not archive_id:
            archive_id = new_memory_id("interview_archive")
            ai_state["interviewArchiveId"] = archive_id
        return archive_id

    def archive_project_label(self):
        name = self.project_state.get("projectName") or getattr(self.app, "project_name", None)
        if hasattr(name, "get"):
            name = name.get()
        return safe_file_name(name or "ai-interview", fallback="ai-interview")

    def build_interview_archive_payload(self, reason):
        ai_state = ensure_ai_interview(self.project_state)
        memory = ensure_project_memory(self.project_state, self.runtime_root)
        archive_id = self.ensure_interview_archive_id(ai_state)
        return {
            "archiveVersion": "1.0",
            "archiveType": "ai_interview",
            "archiveId": archive_id,
            "createdAt": now_iso(),
            "reason": reason,
            "projectName": self.project_state.get("projectName", ""),
            "profile": self.project_state.get("profile", {}),
            "session": {
                "codexSessionId": ai_state.get("codexSessionId", ""),
                "sessionTurnCount": ai_state.get("sessionTurnCount", 0),
                "questionGroupCount": ai_state.get("questionGroupCount", 0),
                "status": ai_state.get("status", ""),
                "backendStage": ai_state.get("backendStage", ""),
            },
            "currentQuestion": {
                "text": ai_state.get("currentQuestionText", ""),
                "turnId": ai_state.get("currentQuestionTurnId", ""),
                "count": ai_state.get("currentQuestionCount", 0),
                "awaitingUserAnswer": ai_state.get("awaitingUserAnswer", False),
            },
            "messages": ai_state.get("messages", []),
            "summary": ai_state.get("summary", {}),
            "routeOverview": ai_state.get("routeOverview", {}),
            "runtimeRefs": {
                "projectMemoryId": memory.get("projectMemoryId", ""),
                "evaluationBatchId": memory.get("evaluationBatchId", ""),
                "runtimeRoot": str(self.runtime_root),
            },
        }

    def write_interview_archive(self, path, reason="manual"):
        ai_state = ensure_ai_interview(self.project_state)
        self.ensure_interview_archive_id(ai_state)
        ai_state["lastArchivedAt"] = now_iso()
        payload = self.build_interview_archive_payload(reason)
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
                filename = f"{self.archive_project_label()}_{archive_id}.json"
                path = self.interview_archive_dir() / filename
            self.write_interview_archive(path, reason=reason)
        except Exception as error:
            ensure_ai_interview(self.project_state)["lastError"] = f"AI 访谈自动存档失败：{error}"

    def save_interview_archive_dialog(self):
        ai_state = ensure_ai_interview(self.project_state)
        self.ensure_interview_archive_id(ai_state)
        default_name = f"{self.archive_project_label()}_{time.strftime('%Y%m%d_%H%M%S')}.ai_interview.json"
        path = filedialog.asksaveasfilename(
            title="保存 AI 访谈存档",
            defaultextension=".json",
            filetypes=[("AI 访谈存档", "*.json"), ("JSON", "*.json")],
            initialdir=str(self.interview_archive_dir()),
            initialfile=default_name,
            parent=self,
        )
        if not path:
            return
        if hasattr(self.app, "ensure_project_local_path") and not self.app.ensure_project_local_path(path, "AI 访谈存档"):
            return
        try:
            saved_path = self.write_interview_archive(path, reason="manual")
        except OSError as error:
            messagebox.showerror("保存访谈存档失败", f"无法写入 AI 访谈存档：\n{error}", parent=self)
            return
        self.status_var.set(f"已保存访谈存档：{saved_path}")
        messagebox.showinfo("保存访谈存档", f"已保存 AI 访谈存档：\n{saved_path}", parent=self)

    def format_question_group_for_chat(self, question_group):
        if not isinstance(question_group, dict):
            return []
        questions = question_group.get("questions")
        if not isinstance(questions, list):
            return []
        lines = []
        for index, question in enumerate(questions[:4], start=1):
            if isinstance(question, dict):
                text = str(question.get("text", "")).strip()
            else:
                text = str(question).strip()
            if text:
                lines.append(f"{index}. {text}")
        return lines

    def assistant_message_with_questions(self, assistant_message, question_group):
        content = str(assistant_message or "").strip()
        question_lines = self.format_question_group_for_chat(question_group)
        if not question_lines:
            return content
        if any(line in content for line in question_lines):
            return content
        parts = [content] if content else []
        parts.extend(["请回答：", *question_lines])
        return "\n".join(parts)

    def chat_lines_for_messages(self, messages):
        lines = []
        turn_index = 0
        for message in messages[-80:]:
            role = message.get("role", "")
            content = str(message.get("content", "")).strip()
            content_lines = content.splitlines() if content else []
            meta = message.get("meta", {})
            question_lines = []
            if isinstance(meta, dict):
                question_lines = self.format_question_group_for_chat(meta.get("questionGroup"))

            if role == "user":
                turn_index += 1
                lines.append(f"第 {turn_index} 轮 - 你的回答：")
                lines.extend(content_lines or ["（空）"])
            elif role == "assistant":
                current_turn = max(turn_index, 1)
                if question_lines:
                    lines.append(f"第 {current_turn} 轮 - AI 提问：")
                    if any(line in content for line in question_lines):
                        lines.extend(content_lines)
                    else:
                        lines.extend(content_lines)
                        if content_lines:
                            lines.append("")
                        lines.append("请回答：")
                        lines.extend(question_lines)
                else:
                    lines.append(f"第 {current_turn} 轮 - AI 回复：")
                    lines.extend(content_lines or ["（无内容）"])
            elif role == "system":
                lines.append("系统提示：")
                lines.extend(content_lines or ["（无内容）"])
            else:
                lines.append(f"{role or '消息'}：")
                lines.extend(content_lines or ["（无内容）"])
            lines.append("")
        return lines

    def input_hint_for_state(self, ai_state):
        if self.running:
            return "AI 正在生成下一组提问，请等待。"
        if ai_state.get("awaitingUserAnswer") and str(ai_state.get("currentQuestionText", "")).strip():
            return "请回答上方“当前 AI 提问”；可以逐条回答，也可以合并说明。"
        for message in reversed(ai_state.get("messages", [])):
            role = message.get("role")
            if role == "assistant":
                meta = message.get("meta", {})
                if isinstance(meta, dict) and self.format_question_group_for_chat(meta.get("questionGroup")):
                    return "请回答上方 AI 提问；可以逐条回答，也可以合并说明。"
                return "可以继续补充你的想法，AI 会基于上下文继续追问。"
            if role == "user":
                return "你的回答已发送；如果没有看到 AI 提问，请等待或检查右侧状态。"
        return "请先描述项目方向，AI 会开始第一轮提问。"

    def latest_question_output_info(self, ai_state):
        messages = ai_state.get("messages", [])
        latest_role = messages[-1].get("role", "") if messages else ""
        current_count = int(ai_state.get("currentQuestionCount") or 0)
        if current_count:
            return {
                "questionCount": current_count,
                "turnId": ai_state.get("currentQuestionTurnId", ""),
                "latestRole": latest_role,
            }
        for message in reversed(messages):
            if message.get("role") != "assistant":
                continue
            meta = message.get("meta", {})
            if not isinstance(meta, dict):
                continue
            question_lines = self.format_question_group_for_chat(meta.get("questionGroup"))
            if question_lines:
                return {
                    "questionCount": len(question_lines),
                    "turnId": meta.get("turnId", ""),
                    "latestRole": latest_role,
                }
        return {
            "questionCount": 0,
            "turnId": "",
            "latestRole": latest_role,
        }

    def latest_question_panel_lines(self, ai_state):
        current_text = str(ai_state.get("currentQuestionText", "")).strip()
        if current_text:
            lines = current_text.splitlines()
            if not ai_state.get("awaitingUserAnswer") and ai_state.get("messages", []) and ai_state["messages"][-1].get("role") == "user":
                lines.extend(["", "状态：你已提交回答，等待 AI 下一轮提问。"])
            return lines

        messages = ai_state.get("messages", [])
        if not messages:
            return ["AI 尚未生成提问。请先在下方输入项目方向。"]

        turn_index = 0
        latest_role = messages[-1].get("role", "")
        latest_question = None
        latest_question_turn = 0
        for message in messages:
            if message.get("role") == "user":
                turn_index += 1
                continue
            if message.get("role") != "assistant":
                continue
            meta = message.get("meta", {})
            if not isinstance(meta, dict):
                continue
            question_lines = self.format_question_group_for_chat(meta.get("questionGroup"))
            if question_lines:
                latest_question = {
                    "assistantMessage": str(message.get("content", "")).strip(),
                    "questionLines": question_lines,
                }
                latest_question_turn = max(turn_index, 1)

        if not latest_question:
            if latest_role == "user":
                return ["你的回答已提交，正在等待 AI 生成下一组提问。"]
            return ["AI 尚未生成提问。请先在下方输入项目方向。"]

        content = latest_question["assistantMessage"]
        question_lines = latest_question["questionLines"]
        lines = [f"第 {latest_question_turn} 轮 - AI 提问："]
        if content:
            if any(line in content for line in question_lines):
                lines.extend(content.splitlines())
            else:
                lines.extend(content.splitlines())
                lines.append("")
                lines.append("请回答：")
                lines.extend(question_lines)
        else:
            lines.append("请回答：")
            lines.extend(question_lines)
        if latest_role == "user":
            lines.extend(["", "状态：你已提交回答，等待 AI 下一轮提问。"])
        return lines

    def answer_readiness_lines(self, ai_state):
        info = self.latest_question_output_info(ai_state)
        question_count = info.get("questionCount", 0)
        if question_count:
            output_line = f"最近输出：AI 提问已生成（{question_count} 个问题）"
        else:
            output_line = "最近输出：尚未生成 AI 提问"

        if self.running:
            ready_line = "是否可回答：否，AI 正在生成或写入本轮提问"
        elif question_count and info.get("latestRole") == "assistant":
            ready_line = "是否可回答：是，请回答上方 AI 提问"
        elif info.get("latestRole") == "user":
            ready_line = "是否可回答：否，你的回答已提交，等待 AI 下一轮提问"
        else:
            ready_line = "是否可回答：请先输入项目方向"
        return [output_line, ready_line]

    def render(self):
        self.project_state = self.app.project_state
        ai_state = ensure_ai_interview(self.project_state)
        overview = update_route_overview(self.engine, self.project_state)
        route_lines = [
            f"当前 MDA 阶段：{overview.get('currentMdaStage', '')}",
            f"追问问题组：{ai_state.get('questionGroupCount', 0)}",
            "",
            "预计覆盖领域：",
            *(f"- {item}" for item in overview.get("expectedDomains", [])[:12]),
            "",
            "已完成节点：",
            *(f"- {item}" for item in overview.get("completedNodes", [])[:12]),
            "",
            "待澄清节点：",
            *(f"- {item}" for item in overview.get("clarificationTargets", [])[:12]),
            "",
            "低适用性候选：",
            *(f"- {item}" for item in overview.get("lowApplicabilityCandidates", [])[:12]),
        ]
        self.write_text(self.route_text, route_lines)

        messages = ai_state.get("messages", [])
        chat_lines = self.chat_lines_for_messages(messages)
        if not chat_lines:
            chat_lines = [
                "第 0 轮 - AI 提问：",
                "请先描述你想做的游戏方向、目标玩家、核心体验或目前最不确定的地方。",
                "",
                "系统：AI 会按 MDA 路线追问；每组最多 4 个问题。你同意输出后，工具会自动写入高置信内容。",
            ]
        self.write_chat_messages(self.chat_text, messages)
        question_panel_lines = self.latest_question_panel_lines(ai_state)
        self.write_text(self.current_question_text, question_panel_lines)
        self.input_hint_var.set(self.input_hint_for_state(ai_state))

        self.write_text(self.diff_text, format_differences(ai_state.get("optionDifferences", [])))
        stage = ai_state.get("backendStage") or "idle"
        stage_label = BACKEND_STAGE_LABELS.get(stage, stage)
        if self.running and self.current_run_started_perf:
            stage_label = f"{stage_label}（{time.perf_counter() - self.current_run_started_perf:.1f}s）"
        session_label = ai_state.get("codexSessionId") or "未建立（首轮返回前正常）"
        last_duration = ai_state.get("lastBackendDurationSeconds")
        first_event = ai_state.get("lastFirstEventSeconds")
        api_config = project_api_config_summary(self.runtime_root)
        api_line = api_config.get("activeProfile") or "global_codex"
        if api_config.get("model"):
            api_line = f"{api_line} / {api_config.get('model')}"
        status_lines = [
            f"Codex CLI：{'可用' if codex_available() else '不可用'}",
            f"项目 API：{api_line}",
            f"访谈状态：{AI_STATUS_LABELS.get(ai_state.get('status', 'idle'), ai_state.get('status', 'idle'))}",
            f"后端阶段：{stage_label}",
            f"最近 Codex 会话：{session_label}",
            f"当前会话累计轮次：{ai_state.get('sessionTurnCount', 0)}",
            f"当前 Turn：{ai_state.get('activeTurnId') or '无'}",
            f"本轮开始：{ai_state.get('runStartedAt') or '无'}",
            f"后端启动：{ai_state.get('backendStartedAt') or '无'}",
            f"上次后端耗时：{last_duration if last_duration not in (None, '') else '无'} 秒",
            f"上次首事件：{first_event if first_event not in (None, '') else '无'} 秒",
            f"本窗口 Codex 进程：{self.process_registry.active_count()}",
            *self.answer_readiness_lines(ai_state),
        ]
        if self.running and stage == "validating" and self.process_registry.active_count() == 0:
            status_lines.extend([
                "",
                "说明：模型调用已经结束，正在校验、记录日志并更新界面。",
            ])
        if ai_state.get("lastError"):
            status_lines.extend(["", f"最近错误：{ai_state.get('lastError')}"])
        self.write_text(self.detail_text, status_lines)
        self.record_render_snapshot(ai_state, chat_lines, question_panel_lines, status_lines)
        self.status_var.set("运行中" if self.running else "就绪")

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
        record_user_correction(
            self.runtime_root,
            self.project_state,
            "用户标记上一轮 AI 回答或映射不准确。" + (f" 摘要：{last_ai[:120]}" if last_ai else ""),
            target_module="mapping",
            signal_type="explicit_user_correction",
        )
        update_conversation_summary(
            self.project_state,
            correction="用户标记上一轮 AI 回答或映射不准确。" + (f" 摘要：{last_ai[:120]}" if last_ai else ""),
        )
        self.status_var.set("已记录反馈")

    def run_ai_turn(self, user_text, force_output=False):
        ai_state = ensure_ai_interview(self.project_state)
        ensure_project_memory(self.project_state, self.runtime_root)
        turn_id = new_memory_id("turn")
        add_message(ai_state, "user", user_text, meta={"turnId": turn_id})
        ai_state["status"] = "running"
        ai_state["activeTurnId"] = turn_id
        ai_state["runStartedAt"] = now_iso()
        ai_state["backendStartedAt"] = ""
        ai_state["backendStage"] = "queued"
        ai_state["lastError"] = ""
        ai_state["awaitingUserAnswer"] = False
        self.current_run_started_perf = time.perf_counter()
        self.app.project_state = self.project_state
        self.app.render()
        self.render()
        self.auto_save_interview_archive("user_submitted")
        self.set_running(True)

        thread = threading.Thread(
            target=self.worker_run_ai_turn,
            args=(user_text, force_output, turn_id),
            daemon=True,
        )
        thread.start()

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
            prompt = build_interview_prompt(
                self.engine,
                self.project_state,
                user_text,
                force_output=should_output,
                force_readiness_check=force_readiness,
                runtime_root=self.runtime_root,
                turn_id=turn_id,
            )
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
        partition_plan = choose_output_domain_partitions(
            self.engine,
            self.project_state,
            user_text,
            runtime_root=self.runtime_root,
        )
        partitions = partition_plan.get("partitions", [])
        if not partitions:
            raise RuntimeError("没有可用于分片输出的领域。")
        partial_results = []
        started_at = time.perf_counter()
        memory = ensure_project_memory(self.project_state, self.runtime_root)
        write_turn_replay(self.runtime_root, parent_turn_id, {
            "projectMemoryId": memory.get("projectMemoryId", ""),
            "evaluationBatchId": memory.get("evaluationBatchId", ""),
            "outputPartitionPlan": {
                key: value
                for key, value in partition_plan.items()
                if key != "partitions"
            },
            "outputPartitionCount": len(partitions),
        })

        def run_partition(index, domain_ids):
            part_turn_id = f"{parent_turn_id}_part{index + 1}"
            prompt = build_output_partition_prompt(
                self.engine,
                self.project_state,
                user_text,
                domain_ids,
                partition_index=index + 1,
                partition_count=len(partitions),
                runtime_root=self.runtime_root,
                turn_id=part_turn_id,
            )
            backend = self.make_backend()
            result = backend.run_turn(prompt, session_id="", schema_mode="partial_output")
            errors = validate_partial_project_output(self.engine, result.payload, allowed_domain_ids=domain_ids)
            record_prompt_runtime(
                self.runtime_root,
                part_turn_id,
                result,
                validation_errors=errors,
                mode=result.payload.get("mode", ""),
            )
            write_turn_replay(self.runtime_root, part_turn_id, {
                "response": result.payload,
                "validationResult": {"ok": not errors, "errors": errors},
                "backend": {
                    "sessionId": result.session_id,
                    "durationSeconds": result.duration_seconds,
                    "firstEventSeconds": result.first_event_seconds,
                    "responseChars": result.response_chars,
                    "rawEventCount": len(result.raw_events or []),
                },
            })
            if errors:
                raise RuntimeError(f"分片 {index + 1} 输出校验失败：{'；'.join(errors[:6])}")
            return result

        try:
            max_workers = int(os.environ.get("AI_OUTPUT_PARTITION_MAX_WORKERS", "4"))
        except (TypeError, ValueError):
            max_workers = 4
        max_workers = max(1, min(max_workers, len(partitions)))
        self.set_backend_stage("calling_codex_partitions", parent_turn_id)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(run_partition, index, domain_ids): (index, domain_ids)
                for index, domain_ids in enumerate(partitions)
            }
            ordered = [None] * len(partitions)
            for future in as_completed(future_map):
                index, _ = future_map[future]
                ordered[index] = future.result()
        partial_results = [result for result in ordered if result is not None]
        self.set_backend_stage("merging_output", parent_turn_id)
        merged_payload, errors = merge_partial_project_outputs(
            self.engine,
            self.project_state,
            [result.payload for result in partial_results],
        )
        if errors:
            raise RuntimeError("分片输出合并失败：" + "；".join(errors[:8]))
        duration = time.perf_counter() - started_at
        first_event_values = [
            result.first_event_seconds
            for result in partial_results
            if result.first_event_seconds is not None
        ]
        return CodexRunResult(
            payload=merged_payload,
            session_id="",
            raw_output="\n".join(result.raw_output for result in partial_results if result.raw_output),
            raw_events=[event for result in partial_results for event in (result.raw_events or [])],
            duration_seconds=duration,
            first_event_seconds=min(first_event_values) if first_event_values else None,
            response_chars=sum(result.response_chars for result in partial_results),
        )

    def handle_ai_unavailable(self, detail="", turn_id=""):
        ai_state = ensure_ai_interview(self.project_state)
        self.set_backend_stage("unavailable", turn_id, schedule_render=False)
        record_backend_runtime_event(
            self.runtime_root,
            self.project_state,
            "codex_unavailable",
            "Codex 后端暂时不可用。",
            detail,
        )
        ai_state["status"] = "unavailable"
        ai_state["lastError"] = "网络问题，AI 暂时不可用。"
        add_message(ai_state, "system", "网络问题，AI 暂时不可用。")
        record_prompt_runtime(self.runtime_root, turn_id, validation_errors=["codex_unavailable"], mode="unavailable")
        write_turn_replay(self.runtime_root, turn_id, {
            "response": None,
            "validationResult": {
                "ok": False,
                "errors": ["网络问题，AI 暂时不可用。"],
            },
            "backendError": detail,
        })
        self.current_run_started_perf = None
        self.set_running(False)
        self.auto_save_interview_archive("backend_unavailable")
        self.render()
        messagebox.showwarning("AI 暂时不可用", "网络问题，AI 暂时不可用。", parent=self)

    def handle_ai_error(self, message, turn_id=""):
        ai_state = ensure_ai_interview(self.project_state)
        self.set_backend_stage("error", turn_id, schedule_render=False)
        record_backend_runtime_event(
            self.runtime_root,
            self.project_state,
            "ai_turn_error",
            "AI 处理异常。",
            message,
        )
        ai_state["status"] = "error"
        ai_state["lastError"] = message
        add_message(ai_state, "system", f"AI 处理失败：{message}")
        record_prompt_runtime(self.runtime_root, turn_id, validation_errors=[message], mode="error")
        write_turn_replay(self.runtime_root, turn_id, {
            "response": None,
            "validationResult": {
                "ok": False,
                "errors": [message],
            },
            "backendError": message,
        })
        self.current_run_started_perf = None
        self.set_running(False)
        self.auto_save_interview_archive("backend_error")
        self.render()

    def handle_ai_result(self, result, turn_id=""):
        payload = result.payload
        session_id = result.session_id
        ai_state = ensure_ai_interview(self.project_state)
        self.set_backend_stage("validating", turn_id, schedule_render=False)
        ai_state["status"] = "processing_result"
        ai_state["lastBackendDurationSeconds"] = round(float(result.duration_seconds or 0.0), 4)
        ai_state["lastFirstEventSeconds"] = (
            round(float(result.first_event_seconds), 4)
            if result.first_event_seconds is not None else None
        )
        if session_id:
            if ai_state.get("codexSessionId") == session_id:
                ai_state["sessionTurnCount"] = ai_state.get("sessionTurnCount", 0) + 1
            else:
                ai_state["sessionTurnCount"] = 1
            ai_state["codexSessionId"] = session_id
        validation_started = time.perf_counter()
        errors = validate_full_project_output(self.engine, payload)
        validation_seconds = time.perf_counter() - validation_started
        if errors:
            record_ai_payload_context(self.runtime_root, self.project_state, payload, validation_errors=errors)
            complete_evaluation_batch(self.runtime_root, self.project_state, reason="validation_failed")
            ai_state["status"] = "validation_failed"
            ai_state["backendStage"] = "validation_failed"
            ai_state["activeTurnId"] = ""
            ai_state["lastError"] = "\n".join(errors)
            add_message(ai_state, "assistant", payload.get("assistantMessage", "AI 输出需要修正。"))
            add_message(ai_state, "system", "AI 输出校验失败，未覆盖项目：\n" + "\n".join(errors))
            record_prompt_runtime(self.runtime_root, turn_id, result, validation_seconds=validation_seconds, validation_errors=errors, mode=payload.get("mode", ""))
            write_turn_replay(self.runtime_root, turn_id, {
                "response": payload,
                "validationResult": {"ok": False, "errors": errors},
                "backend": {
                    "sessionId": session_id,
                    "durationSeconds": result.duration_seconds,
                    "firstEventSeconds": result.first_event_seconds,
                    "responseChars": result.response_chars,
            },
            })
            self.current_run_started_perf = None
            self.set_running(False)
            self.auto_save_interview_archive("validation_failed")
            self.render()
            return

        validation_started = time.perf_counter()
        payload_errors = validate_ai_response_payload(payload)
        validation_seconds += time.perf_counter() - validation_started
        if payload_errors:
            record_ai_payload_context(self.runtime_root, self.project_state, payload, validation_errors=payload_errors)
            complete_evaluation_batch(self.runtime_root, self.project_state, reason="payload_validation_failed")
            ai_state["status"] = "validation_failed"
            ai_state["backendStage"] = "validation_failed"
            ai_state["activeTurnId"] = ""
            ai_state["lastError"] = "\n".join(payload_errors)
            add_message(ai_state, "system", "AI 输出校验失败，未覆盖项目：\n" + "\n".join(payload_errors))
            record_prompt_runtime(self.runtime_root, turn_id, result, validation_seconds=validation_seconds, validation_errors=payload_errors, mode=payload.get("mode", ""))
            write_turn_replay(self.runtime_root, turn_id, {
                "response": payload,
                "validationResult": {"ok": False, "errors": payload_errors},
                "backend": {
                    "sessionId": session_id,
                    "durationSeconds": result.duration_seconds,
                    "firstEventSeconds": result.first_event_seconds,
                    "responseChars": result.response_chars,
            },
            })
            self.current_run_started_perf = None
            self.set_running(False)
            self.auto_save_interview_archive("payload_validation_failed")
            self.render()
            return

        mode = payload.get("mode")
        question_group = payload.get("questionGroup")
        raw_assistant_message = payload.get("assistantMessage", "")
        assistant_content = self.assistant_message_with_questions(
            raw_assistant_message,
            question_group,
        )
        add_message(ai_state, "assistant", assistant_content, meta={
            "turnId": turn_id,
            "mode": mode,
            "questionGroup": question_group if isinstance(question_group, dict) else None,
        })
        route = payload.get("routeOverview")
        if isinstance(route, dict):
            ai_state["routeOverview"] = route
        if isinstance(payload.get("inferences"), list):
            inferences = payload["inferences"]
            ai_state["inferences"].extend(inferences)
            update_applicability_scores(self.project_state, inferences)
        if mode == "question_group" and isinstance(question_group, dict):
            question_lines = self.format_question_group_for_chat(question_group)
            ai_state["currentQuestionText"] = "\n".join([
                f"第 {ai_state.get('questionGroupCount', 0) + 1} 轮 - AI 提问：",
                assistant_content,
            ])
            ai_state["currentQuestionTurnId"] = turn_id
            ai_state["currentQuestionCount"] = len(question_lines)
            ai_state["awaitingUserAnswer"] = bool(question_lines)
            ai_state["questionGroupCount"] = ai_state.get("questionGroupCount", 0) + 1
            target_ids = []
            for question in question_group.get("questions", []) or []:
                if isinstance(question, dict):
                    target_ids.extend(str(item) for item in question.get("targetNodeIds", []) if item)
            ai_state.setdefault("recentQuestionTargets", []).append({
                "turnId": turn_id,
                "nodeIds": sorted(set(target_ids))[:12],
                "createdAt": question_group.get("id", "") or "",
            })
            ai_state["recentQuestionTargets"] = ai_state["recentQuestionTargets"][-12:]
            record_question_group_review(self.runtime_root, self.project_state, payload)
        should_correct_summary = mode == "readiness_check"
        if should_correct_summary:
            ai_state["lastReadinessCheckGroup"] = ai_state.get("questionGroupCount", 0)
        update_conversation_summary(self.project_state, payload)
        if should_correct_summary:
            self.schedule_summary_correction(turn_id)

        apply_seconds = 0.0
        differences = []
        should_schedule_mapping = False
        if mode == "full_project_output" or payload.get("fullProjectOutput"):
            self.set_backend_stage("applying", turn_id, schedule_render=False)
            apply_started = time.perf_counter()
            self.project_state, differences = apply_high_confidence_output(self.engine, self.project_state, payload)
            apply_seconds = time.perf_counter() - apply_started
            self.app.project_state = self.project_state
            ensure_ai_interview(self.project_state)["status"] = "output_applied"
            record_ai_payload_context(self.runtime_root, self.project_state, payload, differences=differences)
            complete_evaluation_batch(self.runtime_root, self.project_state, reason="full_project_output_applied")
            diff_lines = format_differences(differences, limit=40)
            add_message(
                ensure_ai_interview(self.project_state),
                "system",
                "AI 全项目输出已自动应用高置信内容。选项差异：\n" + "\n".join(diff_lines),
            )
            self.app.sync_profile_labels()
            self.app.clear_expanded_nodes()
            self.app.render()
        else:
            ai_state["status"] = "idle"
            self.app.project_state = self.project_state
            should_schedule_mapping = True

        self.project_state = self.app.project_state
        ai_state = ensure_ai_interview(self.project_state)
        if mode == "question_group" and isinstance(question_group, dict):
            question_lines = self.format_question_group_for_chat(question_group)
            if question_lines:
                messages = ai_state.setdefault("messages", [])
                has_assistant_for_turn = any(
                    message.get("role") == "assistant"
                    and message.get("meta", {}).get("turnId") == turn_id
                    for message in messages
                    if isinstance(message, dict)
                )
                if not has_assistant_for_turn:
                    add_message(ai_state, "assistant", assistant_content, meta={
                        "turnId": turn_id,
                        "mode": mode,
                        "questionGroup": question_group,
                    })
                if ai_state.get("currentQuestionTurnId") != turn_id:
                    ai_state["questionGroupCount"] = ai_state.get("questionGroupCount", 0) + 1
                display_turn = max(1, int(ai_state.get("questionGroupCount") or 1))
                ai_state["currentQuestionText"] = "\n".join([
                    f"第 {display_turn} 轮 - AI 提问：",
                    assistant_content,
                ])
                ai_state["currentQuestionTurnId"] = turn_id
                ai_state["currentQuestionCount"] = len(question_lines)
                ai_state["awaitingUserAnswer"] = True
                ai_state["status"] = "idle"
                self.app.project_state = self.project_state

        record_prompt_runtime(
            self.runtime_root,
            turn_id,
            result,
            validation_seconds=validation_seconds,
            apply_seconds=apply_seconds,
            validation_errors=[],
            mode=mode,
        )
        write_turn_replay(self.runtime_root, turn_id, {
            "response": payload,
            "validationResult": {"ok": True, "errors": []},
            "differences": differences,
            "backend": {
                "sessionId": session_id,
                "durationSeconds": result.duration_seconds,
                "firstEventSeconds": result.first_event_seconds,
                "responseChars": result.response_chars,
                "rawEventCount": len(result.raw_events or []),
            },
        })
        ai_state = ensure_ai_interview(self.project_state)
        ai_state["backendStage"] = "completed"
        ai_state["activeTurnId"] = ""
        self.current_run_started_perf = None
        self.set_running(False)
        self.auto_save_interview_archive("turn_completed")
        self.render()
        if should_schedule_mapping:
            self.schedule_background_mapping_if_needed(turn_id)

    def schedule_background_mapping_if_needed(self, turn_id):
        ai_state = ensure_ai_interview(self.project_state)
        user_text = ""
        for message in reversed(ai_state.get("messages", [])):
            if message.get("role") == "user" and message.get("meta", {}).get("turnId") == turn_id:
                user_text = message.get("content", "")
                break
        if not should_schedule_mapping(self.engine, self.project_state, user_text, force_output=False):
            return
        job_id = f"{turn_id}_mapping"
        if job_id in self.mapping_jobs:
            return
        state_hash = project_state_hash(self.engine, self.project_state)
        self.mapping_jobs[job_id] = {
            "basedOnTurnId": turn_id,
            "projectStateHash": state_hash,
        }
        thread = threading.Thread(
            target=self.worker_run_background_mapping,
            args=(job_id, turn_id, user_text, state_hash),
            daemon=True,
        )
        thread.start()

    def worker_run_background_mapping(self, job_id, turn_id, user_text, state_hash):
        try:
            prompt = build_mapping_prompt(
                self.engine,
                self.project_state,
                user_text,
                self.runtime_root,
                turn_id=job_id,
            )
            result = self.make_backend(timeout_seconds=60).run_turn(
                prompt,
                session_id="",
                schema_mode="mapping",
            )
            self.safe_after(lambda: self.handle_background_mapping_result(job_id, turn_id, state_hash, result))
        except Exception as error:
            detail = str(error)
            self.safe_after(lambda detail=detail: self.handle_background_mapping_error(job_id, turn_id, detail))

    def handle_background_mapping_error(self, job_id, turn_id, message):
        self.mapping_jobs.pop(job_id, None)
        record_prompt_runtime(self.runtime_root, job_id, validation_errors=[message], mode="mapping_error")
        write_turn_replay(self.runtime_root, job_id, {
            "basedOnTurnId": turn_id,
            "response": None,
            "validationResult": {"ok": False, "errors": [message]},
            "backendError": message,
        })

    def handle_background_mapping_result(self, job_id, turn_id, state_hash, result):
        self.mapping_jobs.pop(job_id, None)
        current_hash = project_state_hash(self.engine, self.project_state)
        stale = current_hash != state_hash
        errors = validate_mapping_payload(self.engine, result.payload)
        record_prompt_runtime(
            self.runtime_root,
            job_id,
            result,
            validation_errors=(["stale_mapping_result"] if stale else errors),
            mode=result.payload.get("mode", "mapping"),
        )
        write_turn_replay(self.runtime_root, job_id, {
            "basedOnTurnId": turn_id,
            "projectStateHash": state_hash,
            "currentProjectStateHash": current_hash,
            "stale": stale,
            "response": result.payload,
            "validationResult": {"ok": (not stale and not errors), "errors": (["stale_mapping_result"] if stale else errors)},
            "backend": {
                "sessionId": result.session_id,
                "durationSeconds": result.duration_seconds,
                "firstEventSeconds": result.first_event_seconds,
                "responseChars": result.response_chars,
                "rawEventCount": len(result.raw_events or []),
            },
        })
        if stale or errors:
            return
        inferences = result.payload.get("inferences", [])
        if not inferences:
            return
        ai_state = ensure_ai_interview(self.project_state)
        ai_state["inferences"].extend(inferences)
        update_applicability_scores(self.project_state, inferences)
        update_conversation_summary(self.project_state, result.payload)
        record_ai_payload_context(self.runtime_root, self.project_state, result.payload)
        self.app.project_state = self.project_state
        self.app.render()
        self.render()

    def schedule_summary_correction(self, turn_id):
        job_id = f"{turn_id}_summary"
        state_hash = project_state_hash(self.engine, self.project_state)
        thread = threading.Thread(
            target=self.worker_run_summary_correction,
            args=(job_id, turn_id, state_hash),
            daemon=True,
        )
        thread.start()

    def worker_run_summary_correction(self, job_id, turn_id, state_hash):
        try:
            prompt = build_summary_correction_prompt(self.project_state, self.runtime_root, job_id)
            result = self.make_backend(timeout_seconds=60).run_turn(
                prompt,
                session_id="",
                schema_mode="summary",
            )
            self.safe_after(lambda: self.handle_summary_correction_result(job_id, turn_id, state_hash, result))
        except Exception as error:
            detail = str(error)
            self.safe_after(lambda detail=detail: self.handle_summary_correction_error(job_id, turn_id, detail))

    def handle_summary_correction_error(self, job_id, turn_id, message):
        record_prompt_runtime(self.runtime_root, job_id, validation_errors=[message], mode="summary_error")
        write_turn_replay(self.runtime_root, job_id, {
            "basedOnTurnId": turn_id,
            "response": None,
            "validationResult": {"ok": False, "errors": [message]},
            "backendError": message,
        })

    def handle_summary_correction_result(self, job_id, turn_id, state_hash, result):
        current_hash = project_state_hash(self.engine, self.project_state)
        stale = current_hash != state_hash
        errors = validate_summary_payload(result.payload)
        record_prompt_runtime(
            self.runtime_root,
            job_id,
            result,
            validation_errors=(["stale_summary_result"] if stale else errors),
            mode=result.payload.get("mode", "summary_correction"),
        )
        write_turn_replay(self.runtime_root, job_id, {
            "basedOnTurnId": turn_id,
            "projectStateHash": state_hash,
            "currentProjectStateHash": current_hash,
            "stale": stale,
            "response": result.payload,
            "validationResult": {"ok": (not stale and not errors), "errors": (["stale_summary_result"] if stale else errors)},
            "backend": {
                "sessionId": result.session_id,
                "durationSeconds": result.duration_seconds,
                "firstEventSeconds": result.first_event_seconds,
                "responseChars": result.response_chars,
                "rawEventCount": len(result.raw_events or []),
            },
        })
        if stale or errors:
            return
        ai_state = ensure_ai_interview(self.project_state)
        ai_state.setdefault("summary", {})["v1"] = result.payload.get("summary", {})
        self.app.project_state = self.project_state
        self.app.render()
        self.render()
