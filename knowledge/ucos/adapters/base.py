from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class UCOSContext:
    """Runtime context assembled for an AI session."""

    sections: dict[str, Any] = field(default_factory=dict)
    token_estimate: int = 0


class UCOSRuntimeAdapter(ABC):
    @abstractmethod
    def on_session_start(self) -> UCOSContext:
        raise NotImplementedError

    @abstractmethod
    def on_session_end(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_tool_end(self, tool: str, result: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_tool_start(self, tool: str, inputs: dict[str, Any]) -> None:
        raise NotImplementedError

