from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class WorldModelEngine:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.world_dir = self.root / "ucos" / "execution" / "world_model"

    def get_dependencies(self, node_id: str) -> list[str]:
        path = self.world_dir / "dependency_map.json"
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return list(data.get("dependencies", {}).get(node_id, []))

    def isolated_nodes(self) -> list[str]:
        path = self.world_dir / "causal_graph.json"
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        nodes = set(data.get("nodes", []))
        connected = set()
        for edge in data.get("edges", []):
            connected.add(edge.get("from"))
            connected.add(edge.get("to"))
        return sorted(nodes - connected)

    def load_domain_model(self, domain: str) -> dict[str, Any]:
        path = self.world_dir / "domain_models" / f"{domain}_model.json"
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

