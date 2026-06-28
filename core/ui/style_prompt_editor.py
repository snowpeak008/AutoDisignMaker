from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Any

from core.adapters.base import ModelTask
from core.io import now_iso, write_json
from core.paths import ARTIFACTS_DIR
from core.ui.theme import COLORS, FONT_BODY, FONT_SECTION, FONT_SMALL


STYLE_PROMPT_OVERRIDE_FILENAME = "prompt_override.json"
PROMPT_START = "PROMPT_START"
PROMPT_END = "PROMPT_END"


def parse_style_prompt_response(
    response: str, valid_style_ids: set[str] | None = None
) -> tuple[str, dict[str, str]]:
    text = str(response or "").strip()
    explanation = text.split(PROMPT_START, 1)[0].strip()
    prompts: dict[str, str] = {}
    if PROMPT_START not in text or PROMPT_END not in text:
        return explanation, prompts
    block = text.split(PROMPT_START, 1)[1].split(PROMPT_END, 1)[0]
    for raw_line in block.splitlines():
        line = raw_line.strip().strip("`")
        if not line or line.startswith("```") or ":" not in line:
            continue
        style_id, _, prompt = line.partition(":")
        style_id = style_id.strip().lstrip("-*").strip()
        prompt = prompt.strip()
        if not style_id or not prompt:
            continue
        if valid_style_ids is not None and style_id not in valid_style_ids:
            continue
        prompts[style_id] = prompt
    return explanation, prompts


def _style_option_context(options: list[dict[str, Any]]) -> str:
    lines = []
    for option in options:
        style_id = str(option.get("style_id") or "")
        title = str(option.get("title") or "")
        description = str(option.get("description") or "")
        prompt = str(option.get("prompt") or "")
        lines.append(
            f"{style_id}\nTitle: {title}\nIntent: {description}\nCurrent prompt:\n{prompt}"
        )
    return "\n\n".join(lines)


def build_style_prompt_messages(
    options: list[dict[str, Any]], history: list[dict[str, str]]
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a game art prompt engineer. "
        "You help users refine image generation prompts for game art style reference images. "
        "When the user describes their vision, output TWO things:\n"
        "1. A brief explanation of what you changed in Chinese.\n"
        "2. The refined prompts for each style, in this exact format:\n"
        "PROMPT_START\n"
        "STYLE-01-xxx: <full refined prompt>\n"
        "STYLE-02-xxx: <full refined prompt>\n"
        "...\n"
        "PROMPT_END\n"
        "Keep prompts in English, keep every existing STYLE id, and keep each prompt under 200 words.\n\n"
        f"Current style options:\n{_style_option_context(options)}"
    )
    return [{"role": "system", "content": system_prompt}, *history]


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user").upper()
        content = str(message.get("content") or "")
        parts.append(f"{role}:\n{content}")
    parts.append("ASSISTANT:")
    return "\n\n".join(parts)


def run_style_prompt_completion(messages: list[dict[str, str]]) -> str:
    try:
        from core.adapters.registry import get_adapter
        from core.config.ai_config import (
            AI_CONFIG_PATH,
            AIProfile,
            get_active_completion_entry,
            image_config_from_entry,
            llm_config_from_entry,
        )

        if AI_CONFIG_PATH.exists():
            entry = get_active_completion_entry()
            adapter_name, llm = llm_config_from_entry(entry)
            profile = AIProfile(
                id=getattr(entry, "id", "completion"),
                name=getattr(entry, "label", "Completion"),
                adapter=adapter_name,
                llm=llm,
                image=image_config_from_entry(None),
            )
            adapter = get_adapter(adapter_name, profile=profile)
            timeout_seconds = int(getattr(llm, "timeout", 300) or 300)
        else:
            from core.config.loader import get_pipeline_adapter

            adapter = get_pipeline_adapter()
            timeout_seconds = 300
    except Exception as exc:  # noqa: BLE001 - config boundary
        raise RuntimeError(f"无法加载 AI 补全配置：{exc}") from exc

    task = ModelTask(
        task_id="style_prompt_editor",
        prompt=_messages_to_prompt(messages),
        timeout_seconds=timeout_seconds,
    )
    result = adapter.generate(task)
    if result.status != "success":
        detail = "; ".join(result.errors) or result.text or "unknown error"
        raise RuntimeError(detail)
    return result.text


def write_style_prompt_override(
    output_dir,
    options: list[dict[str, Any]],
    refined_prompts: dict[str, str],
    count: int,
) -> Any:
    try:
        requested_count = int(count)
    except (TypeError, ValueError):
        requested_count = len(options)
    requested_count = max(1, min(5, requested_count))
    final_options: list[dict[str, Any]] = []
    for option in options[:requested_count]:
        style_id = str(option.get("style_id") or "")
        if not style_id:
            continue
        final_option = dict(option)
        refined = str(refined_prompts.get(style_id) or "").strip()
        final_option["prompt_refined"] = bool(refined)
        if refined:
            final_option["prompt"] = refined
        final_options.append(final_option)
    if not final_options:
        raise ValueError("没有可用于生成的风格提示词。")
    payload = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": "style_prompt_editor",
        "requested_count": requested_count,
        "count": len(final_options),
        "options": final_options,
    }
    return write_json(output_dir / STYLE_PROMPT_OVERRIDE_FILENAME, payload)


class StylePromptEditorDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        options: list[dict[str, Any]],
        pipeline_panel: Any,
        *,
        output_dir=None,
    ) -> None:
        super().__init__(parent)
        self.title("风格图提示词编辑")
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()
        self.options = [
            dict(option)
            for option in options
            if isinstance(option, dict) and option.get("style_id")
        ]
        self.panel = pipeline_panel
        self.output_dir = output_dir or (ARTIFACTS_DIR / "stage_07")
        self._refined_prompts: dict[str, str] = {}
        self._history: list[dict[str, str]] = []
        self._images: list[tk.PhotoImage] = []
        self._count_var = tk.IntVar(value=max(1, min(5, len(self.options) or 1)))
        self._preview_visible = False
        self._pending = False
        self._build_ui()
        self._send_initial_greeting()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.geometry("900x760")
        self.minsize(760, 620)

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=COLORS["surface"], padx=16, pady=12)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="风格图提示词编辑",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONT_SECTION,
        ).pack(anchor=tk.W)

        body = tk.Frame(self, bg=COLORS["bg"], padx=16, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        preview_bar = tk.Frame(body, bg=COLORS["bg"])
        preview_bar.pack(fill=tk.X)
        self._preview_button = ttk.Button(
            preview_bar, text="展开当前提示词", command=self._toggle_preview
        )
        self._preview_button.pack(anchor=tk.W)
        self._preview = scrolledtext.ScrolledText(
            body,
            height=8,
            wrap=tk.WORD,
            font=FONT_SMALL,
            bg=COLORS["surface"],
            fg=COLORS["muted"],
        )
        self._preview.configure(state=tk.DISABLED)
        self._refresh_preview()

        tk.Label(
            body,
            text="对话记录",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=FONT_BODY,
        ).pack(anchor=tk.W, pady=(10, 4))
        self._conversation = scrolledtext.ScrolledText(
            body,
            height=14,
            wrap=tk.WORD,
            font=FONT_BODY,
            bg=COLORS["surface"],
            fg=COLORS["text"],
        )
        self._conversation.tag_configure("assistant", foreground=COLORS["primary"])
        self._conversation.tag_configure("user", foreground=COLORS["text"])
        self._conversation.configure(state=tk.DISABLED)
        self._conversation.pack(fill=tk.BOTH, expand=True)

        input_row = tk.Frame(body, bg=COLORS["bg"])
        input_row.pack(fill=tk.X, pady=(10, 0))
        self._input_box = tk.Text(input_row, height=3, wrap=tk.WORD, font=FONT_BODY)
        self._input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._send_button = ttk.Button(input_row, text="发送", command=self._on_send)
        self._send_button.pack(side=tk.LEFT, padx=(8, 0), anchor=tk.S)

        count_frame = tk.Frame(body, bg=COLORS["bg"])
        count_frame.pack(anchor=tk.W, pady=(10, 0))
        tk.Label(
            count_frame,
            text="生成张数：",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=FONT_SMALL,
        ).pack(side=tk.LEFT)
        for value in range(1, max(1, min(5, len(self.options))) + 1):
            tk.Radiobutton(
                count_frame,
                text=str(value),
                value=value,
                variable=self._count_var,
                bg=COLORS["bg"],
                fg=COLORS["text"],
                activebackground=COLORS["bg"],
                font=FONT_SMALL,
            ).pack(side=tk.LEFT)

        actions = tk.Frame(self, bg=COLORS["surface"], padx=12, pady=10)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="取消", command=self._on_cancel).pack(side=tk.LEFT)
        self._confirm_button = ttk.Button(
            actions, text="确认生成", command=self._on_confirm
        )
        self._confirm_button.pack(side=tk.RIGHT)

    def _send_initial_greeting(self) -> None:
        summaries = "\n".join(
            f"- {option.get('style_id')}: {option.get('title', '')} - "
            f"{str(option.get('prompt') or '')[:100]}..."
            for option in self.options
        )
        greeting = (
            f"当前已有 {len(self.options)} 个风格方向：\n{summaries}\n\n"
            "请告诉我你想要的美术风格，或者指出已有风格哪些不满意，我来修改提示词。"
        )
        self._append_message("assistant", greeting)

    def _append_message(self, role: str, content: str) -> None:
        label = "你" if role == "user" else "AI"
        tag = "user" if role == "user" else "assistant"
        self._conversation.configure(state=tk.NORMAL)
        self._conversation.insert(tk.END, f"{label}: ", tag)
        self._conversation.insert(tk.END, f"{content.strip()}\n\n")
        self._conversation.see(tk.END)
        self._conversation.configure(state=tk.DISABLED)

    def _current_options_for_prompt(self) -> list[dict[str, Any]]:
        current = []
        for option in self.options:
            item = dict(option)
            style_id = str(item.get("style_id") or "")
            refined = self._refined_prompts.get(style_id)
            if refined:
                item["prompt"] = refined
            current.append(item)
        return current

    def _refresh_preview(self) -> None:
        text = _style_option_context(self._current_options_for_prompt())
        self._preview.configure(state=tk.NORMAL)
        self._preview.delete("1.0", tk.END)
        self._preview.insert(tk.END, text)
        self._preview.configure(state=tk.DISABLED)

    def _toggle_preview(self) -> None:
        self._preview_visible = not self._preview_visible
        if self._preview_visible:
            self._preview.pack(fill=tk.X, pady=(6, 0))
            self._preview_button.configure(text="折叠当前提示词")
        else:
            self._preview.pack_forget()
            self._preview_button.configure(text="展开当前提示词")

    def _set_pending(self, pending: bool) -> None:
        self._pending = pending
        state = tk.DISABLED if pending else tk.NORMAL
        self._send_button.configure(state=state)
        self._confirm_button.configure(state=state)

    def _on_send(self) -> None:
        if self._pending:
            return
        user_text = self._input_box.get("1.0", tk.END).strip()
        if not user_text:
            return
        self._input_box.delete("1.0", tk.END)
        self._append_message("user", user_text)
        self._history.append({"role": "user", "content": user_text})
        self._set_pending(True)
        threading.Thread(target=self._call_ai, daemon=True).start()

    def _call_ai(self) -> None:
        messages = build_style_prompt_messages(
            self._current_options_for_prompt(), self._history
        )
        try:
            response = run_style_prompt_completion(messages)
        except Exception as exc:  # noqa: BLE001 - UI boundary
            self.after(0, lambda error=exc: self._handle_ai_error(error))
            return
        self.after(0, lambda: self._handle_ai_response(response))

    def _handle_ai_error(self, exc: Exception) -> None:
        self._append_message("assistant", f"AI 调用失败：{exc}\n请检查 AI 配置。")
        self._set_pending(False)

    def _handle_ai_response(self, response: str) -> None:
        self._history.append({"role": "assistant", "content": response})
        valid_ids = {str(option.get("style_id")) for option in self.options}
        explanation, prompts = parse_style_prompt_response(response, valid_ids)
        if explanation:
            self._append_message("assistant", explanation)
        if prompts:
            self._refined_prompts.update(prompts)
            self._refresh_preview()
            self._append_message(
                "assistant",
                f"已更新 {len(prompts)} 个风格的提示词。可以继续描述调整方向，或点击“确认生成”。",
            )
        elif not explanation:
            self._append_message("assistant", response)
        self._set_pending(False)

    def _on_confirm(self) -> None:
        try:
            write_style_prompt_override(
                self.output_dir,
                self.options,
                self._refined_prompts,
                self._count_var.get(),
            )
            self.panel._clear_style_confirmation()
            self.destroy()
            self.panel._exec_range(7, 7)
        except Exception as exc:  # noqa: BLE001 - UI boundary
            messagebox.showerror("无法生成", str(exc), parent=self)

    def _on_cancel(self) -> None:
        self.destroy()
