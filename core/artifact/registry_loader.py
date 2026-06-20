"""Artifact registry loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT


REGISTRY_PATH = PROJECT_ROOT / "pipeline" / "artifact_layer" / "registry.json"

KNOWN_REVIEWERS = {
    "structure_reviewer", "source_trace_reviewer", "task_reviewer", "dependency_reviewer",
}
KNOWN_VALIDATORS = {
    "validator_first_contract", "stage_files_validator", "review_report_validator",
    "manifest_validator", "schema_contract_validator", "knowledge_refs_validator",
    "dependency_status_validator",
}


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing artifact layer registry: {REGISTRY_PATH}")
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    artifacts = data.get("artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("artifact_layer/registry.json must declare a non-empty artifacts list.")
    return data


def artifacts_by_id(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry or load_registry()
    result: dict[str, dict[str, Any]] = {}
    for artifact in registry["artifacts"]:
        artifact_id = artifact.get("id")
        if not artifact_id:
            raise RuntimeError("Every artifact must have an id.")
        if artifact_id in result:
            raise RuntimeError(f"Duplicate artifact id: {artifact_id}")
        result[artifact_id] = artifact
    return result


def artifacts_for_step(step_number: int, registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    registry = registry or load_registry()
    return [a for a in registry["artifacts"] if int(a.get("stage", -1)) == step_number]
