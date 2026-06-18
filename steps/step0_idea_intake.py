#!/usr/bin/env python3
from steps.common import SourceGroup, run_import_step, run_step_cli
from tools.development_plan_artifacts import apply_development_plan_outputs


def run(context=None):
    report = run_import_step(
        0,
        [SourceGroup("concept", ("devflow_Concept_*",), "latest", False, ("Concept",))],
        context=context,
    )
    return apply_development_plan_outputs(0, report)


if __name__ == "__main__":
    raise SystemExit(run_step_cli(0))
