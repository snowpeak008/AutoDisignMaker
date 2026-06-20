from __future__ import annotations

from pathlib import Path
from typing import Any

from ucos.adapters.base import UCOSContext, UCOSRuntimeAdapter
from ucos.output.context_builder import build
from ucos.scripts import ucos_sync


class ClaudeCodeAdapter(UCOSRuntimeAdapter):
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()

    def on_session_start(self) -> UCOSContext:
        context = build(self.root)
        return UCOSContext(sections=context, token_estimate=context.get("token_estimate", 0))

    def on_session_end(self) -> None:
        ucos_sync.handle_event(self.root, "session_end")

    def on_tool_end(self, tool: str, result: dict[str, Any]) -> None:
        ucos_sync.handle_event(self.root, "post_tool", {"tool": tool, "result": result})

    def on_tool_start(self, tool: str, inputs: dict[str, Any]) -> None:
        ucos_sync.handle_event(self.root, "pre_tool", {"tool": tool, "inputs": inputs})

