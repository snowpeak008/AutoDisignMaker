"""Small dependency graph utility for stage-local artifact DAGs."""

from __future__ import annotations

from pipeline.contracts import ArtifactSpec


def topological_order(artifacts: list[ArtifactSpec]) -> list[ArtifactSpec]:
    by_id = {item.artifact_id: item for item in artifacts}
    visited: set[str] = set()
    visiting: set[str] = set()
    ordered: list[ArtifactSpec] = []

    def visit(artifact_id: str) -> None:
        if artifact_id in visited:
            return
        if artifact_id in visiting:
            raise ValueError(f"Dependency cycle at {artifact_id}")
        visiting.add(artifact_id)
        item = by_id[artifact_id]
        for dep in item.dependencies:
            if dep not in by_id:
                raise ValueError(f"{artifact_id} depends on unknown artifact {dep}")
            visit(dep)
        visiting.remove(artifact_id)
        visited.add(artifact_id)
        ordered.append(item)

    for artifact_id in by_id:
        visit(artifact_id)
    return ordered
