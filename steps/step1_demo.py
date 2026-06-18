#!/usr/bin/env python3
from steps.common import SourceGroup, run_import_step, run_step_cli
from tools.development_plan_artifacts import apply_development_plan_outputs


def run(context=None):
    report = run_import_step(
        1,
        [SourceGroup("gameplay_framework_history", ("devflow_GameplayFramework_*",), "all", True, ("GameplayFramework",))],
        context=context,
        notes=["Current-project framework revisions are imported; downstream should use the latest version by artifact_index ordering."],
    )
    return apply_development_plan_outputs(1, report)


if __name__ == "__main__":
    raise SystemExit(run_step_cli(1))
