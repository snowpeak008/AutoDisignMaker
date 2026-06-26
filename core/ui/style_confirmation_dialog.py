from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from core.io import now_iso
from core.paths import PROJECT_ROOT
from core.ui.theme import COLORS, FONT_BODY, FONT_SECTION, FONT_SMALL


def _resolve_image_path(path_text: str) -> Path:
    path = Path(str(path_text))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def write_style_confirmation(
    output_dir: Path,
    selected_option: dict[str, Any],
    notes: str,
    *,
    status: str = "approved",
    mode: str = "manual",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": status,
        "mode": mode,
        "selected_style_id": selected_option.get("style_id", ""),
        "selected_title": selected_option.get("title", ""),
        "selected_image_path": selected_option.get("image_path", ""),
        "notes": notes.strip(),
        "selected_option": selected_option,
    }
    path = output_dir / "style_confirmation.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class StyleConfirmationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        style_options: dict[str, Any],
        output_dir: Path,
    ) -> None:
        super().__init__(parent)
        self.title("美术风格确认")
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()
        self._output_dir = output_dir
        self._options = [
            item
            for item in style_options.get("options", [])
            if isinstance(item, dict) and item.get("style_id")
        ]
        self._result = "cancelled"
        self._selected = tk.StringVar(
            value=str(self._options[0].get("style_id")) if self._options else ""
        )
        self._images: list[tk.PhotoImage] = []
        self._notes: tk.Text | None = None
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.geometry("980x720")
        self.minsize(760, 560)

    def _build(self) -> None:
        header = tk.Frame(self, bg=COLORS["surface"], padx=16, pady=12)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="美术风格确认",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONT_SECTION,
        ).pack(anchor=tk.W)
        tk.Label(
            header,
            text="选择一个风格方向并记录批注后继续流水线。",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
        ).pack(anchor=tk.W, pady=(4, 0))

        body = tk.Frame(self, bg=COLORS["bg"], padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        grid = tk.Frame(body, bg=COLORS["bg"])
        grid.pack(fill=tk.BOTH, expand=True)
        for index, option in enumerate(self._options):
            self._build_option_card(grid, option, index)

        notes_frame = tk.Frame(body, bg=COLORS["bg"])
        notes_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Label(
            notes_frame,
            text="批注",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=FONT_BODY,
        ).pack(anchor=tk.W)
        self._notes = tk.Text(notes_frame, height=4, wrap=tk.WORD, font=FONT_BODY)
        self._notes.pack(fill=tk.X, pady=(4, 0))

        actions = tk.Frame(self, bg=COLORS["surface"], padx=12, pady=10)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="确认选择", command=self._confirm).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(actions, text="重新生成", command=self._regenerate).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(actions, text="取消", command=self._cancel).pack(side=tk.RIGHT)

    def _build_option_card(
        self, parent: tk.Widget, option: dict[str, Any], index: int
    ) -> None:
        row = index // 3
        col = index % 3
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
        parent.grid_rowconfigure(row, weight=1)

        image_label = tk.Label(card, bg=COLORS["surface"])
        image_label.pack(fill=tk.BOTH, expand=True)
        image_path = _resolve_image_path(str(option.get("image_path") or ""))
        try:
            image = tk.PhotoImage(file=str(image_path))
            while image.width() > 220 or image.height() > 150:
                image = image.subsample(2, 2)
            self._images.append(image)
            image_label.configure(image=image)
        except tk.TclError:
            image_label.configure(
                text="图片不可用",
                fg=COLORS["danger"],
                font=FONT_SMALL,
                width=24,
                height=8,
            )

        ttk.Radiobutton(
            card,
            text=f"{option.get('style_id')}  {option.get('title', '')}",
            value=str(option.get("style_id")),
            variable=self._selected,
        ).pack(anchor=tk.W, pady=(6, 2))
        tk.Label(
            card,
            text=str(option.get("description") or ""),
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=FONT_SMALL,
            wraplength=240,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _selected_option(self) -> dict[str, Any] | None:
        selected_id = self._selected.get()
        for option in self._options:
            if str(option.get("style_id")) == selected_id:
                return option
        return None

    def _confirm(self) -> None:
        option = self._selected_option()
        if option is None:
            messagebox.showwarning("无法确认", "请先选择一个风格方案。", parent=self)
            return
        notes = self._notes.get("1.0", tk.END) if self._notes is not None else ""
        write_style_confirmation(self._output_dir, option, notes)
        self._result = "confirmed"
        self.destroy()

    def _regenerate(self) -> None:
        self._result = "regenerate"
        self.destroy()

    def _cancel(self) -> None:
        self._result = "cancelled"
        self.destroy()

    def wait_result(self) -> str:
        self.wait_window(self)
        return self._result
