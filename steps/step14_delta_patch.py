#!/usr/bin/env python3
from steps.common import SourceGroup, run_import_step, run_step_cli
from tools.development_plan_artifacts import apply_development_plan_outputs


def run(context=None):
    report = run_import_step(
        14,
        [
            SourceGroup(
                "delta_patch",
                (
                    "devflow_DeltaPatch_*",
                ),
                "latest",
                True,
                ("DeltaPatch",),
            ),
        ],
        context=context,
    )
    return apply_development_plan_outputs(14, report)


if __name__ == "__main__":
    raise SystemExit(run_step_cli(14))
