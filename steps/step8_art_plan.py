#!/usr/bin/env python3
from steps.common import SourceGroup, run_import_step, run_step_cli
from tools.development_plan_artifacts import apply_development_plan_outputs


def run(context=None):
    report = run_import_step(
        8,
        [SourceGroup("art_plans", ("devflow_ArtPlans_*",), "latest", True, ("ArtPlans",))],
        context=context,
    )
    return apply_development_plan_outputs(8, report)


if __name__ == "__main__":
    raise SystemExit(run_step_cli(8))
