from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from core.ui.theme import COLORS, FONT_BODY, FONT_SMALL


class BottomPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, log_queue: queue.Queue):
        super().__init__(parent, bg=COLORS["surface"])
        self._log_queue = log_queue
        self._context = "design"
        self._messages: list[dict] = []
        self._build()
        self._poll_log_queue()

    def _build(self):
        # Tab bar
        bar = tk.Frame(self, bg=COLORS["surface"], pady=4)
        bar.pack(fill=tk.X, side=tk.TOP)

        self._log_btn = tk.Label(bar, text="📋 日志", bg=COLORS["primary_soft"], fg=COLORS["primary"], font=FONT_SMALL, padx=10, pady=3, cursor="hand2")
        self._log_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._log_btn.bind("<Button-1>", lambda _: self._show_log())

        self._chat_btn = tk.Label(bar, text="🤖 AI 对话", bg=COLORS["surface"], fg=COLORS["muted"], font=FONT_SMALL, padx=10, pady=3, cursor="hand2")
        self._chat_btn.pack(side=tk.LEFT, padx=2)
        self._chat_btn.bind("<Button-1>", lambda _: self._show_chat())

        # Content area
        self._content = tk.Frame(self, bg=COLORS["surface"])
        self._content.pack(fill=tk.BOTH, expand=True)

        self._log_pane = self._build_log_pane(self._content)
        self._chat_pane = self._build_chat_pane(self._content)
        self._log_pane.pack(fill=tk.BOTH, expand=True)

    def _build_log_pane(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=COLORS["surface"])
        self._log_text = tk.Text(frame, bg=COLORS["dark"], fg="#D0E8C0", font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        sb = ttk.Scrollbar(frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(fill=tk.BOTH, expand=True)
        return frame

    def _build_chat_pane(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=COLORS["surface"])

        self._msg_canvas = tk.Canvas(frame, bg=COLORS["surface"], highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._msg_canvas.yview)
        self._msg_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._msg_canvas.pack(fill=tk.BOTH, expand=True)

        self._msg_frame = tk.Frame(self._msg_canvas, bg=COLORS["surface"])
        self._msg_win = self._msg_canvas.create_window((0, 0), window=self._msg_frame, anchor=tk.NW)
        self._msg_canvas.bind("<Configure>", lambda e: self._msg_canvas.itemconfig(self._msg_win, width=e.width))
        self._msg_frame.bind("<Configure>", lambda e: self._msg_canvas.configure(scrollregion=self._msg_canvas.bbox("all")))

        input_row = tk.Frame(frame, bg=COLORS["surface"], pady=4)
        input_row.pack(fill=tk.X, side=tk.BOTTOM, padx=8)
        self._input_var = tk.StringVar()
        entry = ttk.Entry(input_row, textvariable=self._input_var, font=FONT_BODY)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Return>", lambda _: self._send())
        ttk.Button(input_row, text="发送", command=self._send).pack(side=tk.LEFT, padx=(6, 0))
        return frame

    def set_context(self, context: str):
        self._context = context

    def append_log(self, line: str):
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, line)
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _poll_log_queue(self):
        try:
            while True:
                line = self._log_queue.get_nowait()
                self.append_log(line)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _show_log(self):
        self._chat_pane.pack_forget()
        self._log_pane.pack(fill=tk.BOTH, expand=True)
        self._log_btn.configure(bg=COLORS["primary_soft"], fg=COLORS["primary"])
        self._chat_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])

    def _show_chat(self):
        self._log_pane.pack_forget()
        self._chat_pane.pack(fill=tk.BOTH, expand=True)
        self._chat_btn.configure(bg=COLORS["primary_soft"], fg=COLORS["primary"])
        self._log_btn.configure(bg=COLORS["surface"], fg=COLORS["muted"])

    def _add_bubble(self, text: str, role: str):
        is_user = role == "user"
        bg = COLORS["user_message_bg"] if is_user else COLORS["ai_message_bg"]
        border = COLORS["user_message_border"] if is_user else COLORS["ai_message_border"]
        anchor = tk.E if is_user else tk.W
        label = f"{'你' if is_user else 'AI'}："

        row = tk.Frame(self._msg_frame, bg=COLORS["surface"], pady=3)
        row.pack(fill=tk.X, padx=8)
        bubble = tk.Frame(row, bg=bg, padx=8, pady=5, bd=1, relief=tk.SOLID,
                          highlightbackground=border, highlightthickness=1)
        bubble.pack(anchor=anchor, side=tk.RIGHT if is_user else tk.LEFT)
        tk.Label(bubble, text=label + text, bg=bg, fg=COLORS["text"], font=FONT_SMALL,
                 wraplength=400, justify=tk.LEFT).pack()

        self._msg_canvas.update_idletasks()
        self._msg_canvas.yview_moveto(1.0)

    def _send(self):
        text = self._input_var.get().strip()
        if not text:
            return
        self._input_var.set("")
        self._add_bubble(text, "user")
        self._messages.append({"role": "user", "content": text})
        threading.Thread(target=self._call_ai, args=(text,), daemon=True).start()

    def _call_ai(self, user_text: str):
        try:
            from core.config.loader import get_api_config
            import openai
            cfg = get_api_config()
            client = openai.OpenAI(base_url=cfg.get("base_url"), api_key=cfg.get("api_key") or "none")
            system_prompt = (
                "你是游戏设计顾问，回答设计相关问题。" if self._context == "design"
                else "你是流水线辅助助手，解答当前开发步骤的制品内容和常见问题。"
            )
            response = client.chat.completions.create(
                model=cfg.get("default_model", "gpt-4"),
                messages=[{"role": "system", "content": system_prompt}] + self._messages[-10:],
                max_tokens=512,
            )
            reply = response.choices[0].message.content or "(无回复)"
        except Exception as exc:
            reply = f"[错误] {exc}"
        self._messages.append({"role": "assistant", "content": reply})
        self.after(0, lambda: self._add_bubble(reply, "assistant"))
