from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class SkillSpec:
    skill_id: str
    name: str
    type: str
    level: int
    version: str
    status: str
    domain: str
    description: str
    capabilities: list[str]
    dependencies: list[str]
    trigger_rule: dict[str, Any]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    anti_patterns: list[str]
    episode_refs: list[str]


@dataclass
class SkillResult:
    skill_id: str
    ok: bool
    output: Any
    error: str = ""


class SkillEngine:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = self._find_root(Path(root) if root else Path.cwd())
        self.capability_dir = self.root / "ucos" / "capability"
        self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    @staticmethod
    def _find_root(start: Path) -> Path:
        """Walk up from *start* until we find a directory containing ucos/."""
        candidate = start.resolve()
        for path in [candidate, *candidate.parents]:
            if (path / "ucos").is_dir():
                return path
        return candidate

    def register(self, spec: SkillSpec, handler: Callable[[dict[str, Any]], Any]) -> None:
        self.handlers[spec.skill_id] = handler

    def discover(self, context_tags: list[str], inputs: dict[str, Any]) -> list[SkillSpec]:
        tags = set(context_tags)
        matches = []
        for spec in self._load_specs():
            if spec.status != "active":
                continue
            rule = spec.trigger_rule or {}
            required_tags = set(rule.get("required_context_tags", []))
            required_inputs = set(rule.get("required_inputs", []))
            if required_tags.issubset(tags) and required_inputs.issubset(inputs.keys()):
                matches.append(spec)
        return matches

    def execute(self, skill_id: str, inputs: dict[str, Any]) -> SkillResult:
        handler = self.handlers.get(skill_id)
        if handler is None:
            return SkillResult(skill_id=skill_id, ok=False, output=None, error="handler not registered")
        try:
            return SkillResult(skill_id=skill_id, ok=True, output=handler(inputs))
        except Exception as exc:
            return SkillResult(skill_id=skill_id, ok=False, output=None, error=str(exc))

    def get_dependency_graph(self, skill_id: str) -> dict[str, Any]:
        graph_path = self.capability_dir / "dependency_graph.json"
        with graph_path.open("r", encoding="utf-8") as handle:
            graph = json.load(handle)
        return {
            "skill_id": skill_id,
            "dependencies": graph.get("edges", {}).get(skill_id, []),
            "has_cycle": self._has_cycle(graph.get("edges", {}), skill_id),
        }

    def get_version_history(self, skill_id: str) -> list[SkillSpec]:
        prefix = skill_id.rsplit("_v", 1)[0]
        return [spec for spec in self._load_specs() if spec.skill_id.startswith(prefix)]

    def _load_specs(self) -> list[SkillSpec]:
        known_fields = {f.name for f in SkillSpec.__dataclass_fields__.values()}
        specs = []
        # Load from capability/skills/
        skills_dir = self.capability_dir / "skills"
        if skills_dir.exists():
            for path in sorted(skills_dir.rglob("*.json")):
                spec = self._parse_skill_file(path, known_fields)
                if spec:
                    specs.append(spec)
        # Load from plugins/*/skills/
        plugins_dir = self.root / "ucos" / "plugins"
        if plugins_dir.exists():
            for path in sorted(plugins_dir.glob("*/skills/*.json")):
                spec = self._parse_skill_file(path, known_fields)
                if spec:
                    specs.append(spec)
        return specs

    @staticmethod
    def _parse_skill_file(path: Path, known_fields: set[str]) -> "SkillSpec | None":
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return None
        if "skill_id" not in data:
            return None
        # Strip unknown fields (e.g. created_at) so SkillSpec(**data) doesn't fail
        filtered = {k: v for k, v in data.items() if k in known_fields}
        try:
            return SkillSpec(**filtered)
        except TypeError:
            return None

    @staticmethod
    def _has_cycle(edges: dict[str, list[str]], start: str) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dep in edges.get(node, []):
                if visit(dep):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return visit(start)
