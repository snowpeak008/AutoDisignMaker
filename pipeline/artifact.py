"""Artifact layer primitives."""

from __future__ import annotations

from pathlib import Path

from pipeline.contracts import ArtifactSpec


class ArtifactRegistry:
    def __init__(self, artifacts: list[ArtifactSpec]) -> None:
        self._artifacts = {item.artifact_id: item for item in artifacts}

    def all(self) -> list[ArtifactSpec]:
        return list(self._artifacts.values())

    def get(self, artifact_id: str) -> ArtifactSpec:
        return self._artifacts[artifact_id]

    def exists(self, artifact_id: str) -> bool:
        spec = self.get(artifact_id)
        return Path(spec.path).exists()
