#!/usr/bin/env python3
"""Create the standard directory structure for a new pipeline step."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = PROJECT_ROOT / "pipeline"


PLUGIN_TEMPLATE = """from __future__ import annotations

from core.context import StageContext, StageResult
from core.engines.generation import apply_development_plan_outputs
from core.source.groups import SourceGroup
from core.source.importer import run_import_step
from core.stage_plugin import StagePlugin


class Plugin(StagePlugin):
    stage_id = "{stage_id}"
    _source_groups = [
        SourceGroup("design", ("devflow_*",), "latest", True, ("Concept", "Design"))
    ]

    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.test_mode:
            return StageResult(status="success", outputs={{"stage_id": self.stage_id}})
        report = run_import_step(int(self.stage_id), self._source_groups, context=ctx)
        result = apply_development_plan_outputs(int(self.stage_id), report)
        return StageResult(status=result.get("status", "success"), outputs=result)
"""


HELPERS_TEMPLATE = '''from __future__ import annotations

from typing import Any


def build_report(parsed: dict[str, Any]) -> dict[str, Any]:
    """Build this step's structured report."""
    return {{"schema_version": 1, "source": str(parsed.get("source", ""))}}
'''


def _step_dir(step: int, name: str) -> Path:
    slug = name.strip().lower().replace(" ", "_").replace("-", "_")
    return PIPELINE_ROOT / f"step_{step:02d}_{slug}"


def scaffold_step(step: int, name: str, *, force: bool = False) -> Path:
    """Create a step folder with plugin, helper, prompt, and data placeholders."""
    target = _step_dir(step, name)
    if target.exists() and not force:
        raise FileExistsError(f"{target} already exists; pass --force to add missing files.")
    (target / "data").mkdir(parents=True, exist_ok=True)
    (target / "prompts").mkdir(parents=True, exist_ok=True)

    files = {
        target / "__init__.py": "",
        target / "plugin.py": PLUGIN_TEMPLATE.format(stage_id=f"{step:02d}"),
        target / "helpers.py": HELPERS_TEMPLATE,
        target / "prompts" / "README.md": "# Prompts\n",
        target / "data" / "README.md": "# Data\n",
    }
    for path, content in files.items():
        if path.exists() and not force:
            continue
        path.write_text(content, encoding="utf-8")
    return target


def main() -> int:
    """Parse CLI arguments and scaffold a pipeline step."""
    parser = ArgumentParser(description="Create a pipeline step scaffold.")
    parser.add_argument("--step", type=int, required=True, help="Numeric stage id, for example 16.")
    parser.add_argument("--name", required=True, help="Step slug, for example new_stage.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    args = parser.parse_args()
    target = scaffold_step(args.step, args.name, force=args.force)
    print(target.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
