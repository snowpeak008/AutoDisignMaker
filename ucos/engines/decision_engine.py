from __future__ import annotations

from pathlib import Path
from typing import Any

from ucos.engines.identity_engine import IdentityEngine


class DecisionEngine:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.identity = IdentityEngine(self.root)

    def decide(self, options: list[dict[str, Any]]) -> dict[str, Any] | None:
        allowed = []
        for option in options:
            # Pass the full option dict so validate_action can read 'target' and 'type'/'action'
            ok, reason = self.identity.validate_action(option)
            item = dict(option)
            item["identity_allowed"] = ok
            item["identity_reason"] = reason
            if ok:
                allowed.append(item)
        if not allowed:
            return None
        allowed.sort(key=lambda item: item.get("score", 0), reverse=True)
        return allowed[0]

