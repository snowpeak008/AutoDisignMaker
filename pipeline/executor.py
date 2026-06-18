"""Task executor for artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pipeline.contracts import ArtifactSpec
from pipeline.controller import ProjectController
from pipeline.reviewer import Reviewer
from pipeline.validator import ValidatorRegistry


Producer = Callable[[ArtifactSpec], None]


class TaskExecutor:
    def __init__(self, controller: ProjectController, validators: ValidatorRegistry) -> None:
        self.controller = controller
        self.validators = validators
        self.reviewer = Reviewer()

    def run_artifact(self, spec: ArtifactSpec, producer: Producer) -> list[str]:
        self.controller.logger.info(f"artifact start: {spec.artifact_id}")
        producer(spec)
        path = Path(spec.path)
        review_errors = self.reviewer.review(spec.artifact_id, path) if spec.generated_by_ai else []
        validate_errors = self.validators.validate(spec.validator_name, path)
        errors = review_errors + validate_errors
        if errors:
            self.controller.mark_artifact(spec.artifact_id, "failed", str(path), errors)
            self.controller.logger.error(f"artifact failed: {spec.artifact_id}: {errors}")
            return errors
        self.controller.mark_artifact(spec.artifact_id, "validated", str(path), [])
        self.controller.logger.info(f"artifact validated: {spec.artifact_id}")
        return []
