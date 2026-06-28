from __future__ import annotations

from core.context import StageContext, StageResult
from core.engines.generation import (
    LEGACY_ART_STYLE_CONFIRMATION_STAGE,
    STYLE_CONFIRMATION_FILENAME,
    apply_development_plan_outputs,
)
from core.io import read_json, write_json
from core.source.importer import run_import_step
from core.stage import stage_dir
from core.stage_plugin import StagePlugin


class Plugin(StagePlugin):
    stage_id = "07"
    _source_groups = []

    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.test_mode:
            return StageResult(
                status="success", outputs={"stage_id": self.stage_id, "mode": "test"}
            )

        current_dir = stage_dir(int(self.stage_id))
        legacy_dir = stage_dir(LEGACY_ART_STYLE_CONFIRMATION_STAGE)
        confirmation_path = current_dir / STYLE_CONFIRMATION_FILENAME
        style_options_path = current_dir / "style_options.json"

        confirmation = read_json(confirmation_path, {})
        if not (
            isinstance(confirmation, dict)
            and confirmation.get("status") == "approved"
        ):
            legacy_confirmation = read_json(legacy_dir / STYLE_CONFIRMATION_FILENAME, {})
            if (
                isinstance(legacy_confirmation, dict)
                and legacy_confirmation.get("status") == "approved"
                and style_options_path.is_file()
            ):
                confirmation = legacy_confirmation
                write_json(confirmation_path, confirmation)

        preserved_confirmation = (
            confirmation
            if isinstance(confirmation, dict)
            and confirmation.get("status") == "approved"
            else None
        )
        if (
            preserved_confirmation is not None
            and style_options_path.is_file()
        ):
            report = {"status": "confirmation_resume"}
        else:
            report = run_import_step(int(self.stage_id), self._source_groups, context=ctx)
            if preserved_confirmation is not None:
                write_json(confirmation_path, preserved_confirmation)
        result = apply_development_plan_outputs(int(self.stage_id), report)
        if isinstance(result, dict):
            status = result.get("status", "success")
            return StageResult(status=status, outputs=result)
        return result
