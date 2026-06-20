from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class IdentityProfile:
    identity_id: str
    role: str
    principles: list[str]
    philosophy: str


class IdentityEngine:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = self._find_root(Path(root) if root else Path.cwd())
        self.identity_dir = self.root / "ucos" / "identity"
        self._profile: dict[str, Any] | None = None
        self._constraints: dict[str, Any] | None = None
        self._policy: dict[str, Any] | None = None

    @staticmethod
    def _find_root(start: Path) -> Path:
        """Walk up from *start* until we find a directory containing ucos/."""
        candidate = start.resolve()
        for path in [candidate, *candidate.parents]:
            if (path / "ucos").is_dir():
                return path
        # Fallback: return as-is and let callers surface FileNotFoundError
        return candidate

    def load(self, profile_path: str | Path | None = None) -> IdentityProfile:
        path = Path(profile_path) if profile_path else self.identity_dir / "profile.json"
        data = self._read_json(path)
        self._profile = data
        return IdentityProfile(
            identity_id=data.get("identity_id", ""),
            role=data.get("role", ""),
            principles=list(data.get("principles", [])),
            philosophy=data.get("philosophy", ""),
        )

    def get_principles(self) -> list[str]:
        if self._profile is None:
            self.load()
        assert self._profile is not None
        return list(self._profile.get("principles", []))

    def validate_action(self, action: dict[str, Any]) -> tuple[bool, str]:
        constraints = self._load_constraints()
        target = str(action.get("target", "") or action.get("path", ""))
        action_type = str(action.get("type", "") or action.get("action", ""))

        for rule in constraints.get("forbidden_actions", []):
            rule_action = str(rule.get("action", ""))
            targets = [str(item) for item in rule.get("targets", [])]
            if rule_action == "edit_generated_files" and action_type in {"edit", "write", "delete"}:
                if self._matches_any(target, targets):
                    return False, str(rule.get("reason", "forbidden generated file edit"))
            if rule_action == "delete_registry" and action_type == "delete":
                if self._matches_any(target, targets):
                    return False, str(rule.get("reason", "forbidden registry deletion"))
            if rule_action == "restore_deprecated" and action_type in {"create", "restore", "write"}:
                if self._matches_any(target, targets):
                    return False, str(rule.get("reason", "forbidden deprecated runtime restore"))
            if rule_action == "bypass_orchestrator" and action_type in {"write", "edit", "create"}:
                if self._matches_any(target, targets):
                    return False, str(rule.get("reason", "forbidden orchestrator bypass"))

        return True, "allowed"

    def get_autonomy_level(self) -> int:
        if self._policy is None:
            self._policy = self._read_json(self.identity_dir / "policy.json")
        return int(self._policy.get("autonomy_level", 0))

    def _load_constraints(self) -> dict[str, Any]:
        if self._constraints is None:
            self._constraints = self._read_json(self.identity_dir / "constraints.json")
        return self._constraints

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _matches_any(target: str, patterns: list[str]) -> bool:
        normalized = target.replace("\\", "/")
        name = Path(target).name
        for pattern in patterns:
            p = pattern.replace("\\", "/")
            if fnmatch.fnmatch(normalized, p) or fnmatch.fnmatch(name, p):
                return True
            if normalized.endswith(p):
                return True
        return False
