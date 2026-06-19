"""Artifact dependency graph and topological ordering."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from core.io import now_iso, write_json
from core.paths import OUTPUTS_DIR, PROJECT_ROOT
from core.artifact.registry_loader import artifacts_by_id, load_registry

GRAPH_PATH = PROJECT_ROOT / "artifact_layer" / "dependency_graph.json"
OUTPUT_GRAPH_PATH = OUTPUTS_DIR / "dependency_graph.json"
LAYER_OUTPUT_DIR = OUTPUTS_DIR / "artifact_layer"


def topological_artifact_order(registry: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    registry = registry or load_registry()
    by_id = artifacts_by_id(registry)
    indegree = {aid: 0 for aid in by_id}
    dependents: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []

    for artifact_id, artifact in by_id.items():
        for dep_id in artifact.get("depends_on", []):
            if dep_id not in by_id:
                errors.append(f"{artifact_id} depends on unknown artifact {dep_id}")
                continue
            dependents[dep_id].append(artifact_id)
            indegree[artifact_id] += 1

    def sort_key(aid: str) -> tuple[int, str]:
        return int(by_id[aid].get("stage", 9999)), aid

    ready = deque(sorted((a for a, d in indegree.items() if d == 0), key=sort_key))
    order: list[str] = []
    while ready:
        aid = ready.popleft()
        order.append(aid)
        for child in sorted(dependents[aid], key=sort_key):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready = deque(sorted(ready, key=sort_key))

    if len(order) != len(by_id):
        cycle_nodes = sorted(a for a, d in indegree.items() if d > 0)
        errors.append(f"Dependency cycle detected: {cycle_nodes}")
    return order, errors


def build_dependency_graph(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    by_id = artifacts_by_id(registry)
    nodes, edges, errors = [], [], []
    for artifact in registry["artifacts"]:
        aid = artifact["id"]
        nodes.append({"id": aid, "stage": artifact["stage"],
                      "kind": artifact.get("kind", "artifact"),
                      "tasks": [t.get("id") for t in artifact.get("tasks", [])]})
        for dep_id in artifact.get("depends_on", []):
            if dep_id not in by_id:
                errors.append(f"{aid} depends on unknown artifact {dep_id}")
            edges.append({"from": dep_id, "to": aid})
    order, topo_errors = topological_artifact_order(registry)
    errors.extend(topo_errors)
    return {
        "version": registry.get("version", 1),
        "nodes": sorted(nodes, key=lambda n: (int(n["stage"]), n["id"])),
        "edges": sorted(edges, key=lambda e: (e["from"], e["to"])),
        "topological_order": order,
        "errors": errors,
    }


def topological_step_order(from_step: int, stop_step: int) -> list[int]:
    registry = load_registry()
    order, errors = topological_artifact_order(registry)
    if errors:
        raise RuntimeError("Artifact dependency graph is invalid: " + "; ".join(errors))
    by_id = artifacts_by_id(registry)
    steps: list[int] = []
    seen: set[int] = set()
    for aid in order:
        n = int(by_id[aid]["stage"])
        if from_step <= n <= stop_step and n not in seen:
            steps.append(n)
            seen.add(n)
    return steps


def emit_dependency_graph() -> dict[str, Any]:
    graph = build_dependency_graph()
    write_json(GRAPH_PATH, graph)
    write_json(OUTPUT_GRAPH_PATH, graph)
    if graph["errors"]:
        raise RuntimeError("Artifact dependency graph is invalid: " + "; ".join(graph["errors"]))
    return graph
