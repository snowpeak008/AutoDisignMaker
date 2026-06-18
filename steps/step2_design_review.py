#!/usr/bin/env python3
from steps.common import SourceGroup, run_import_step, run_step_cli
from tools.development_plan_artifacts import apply_development_plan_outputs


def run(context=None):
    report = run_import_step(
        2,
        [
            SourceGroup("2a_subsystem_design", ("devflow_SubsystemDesign_*",), "latest", True, ("SubsystemDesign",)),
            SourceGroup("2b_ai_design_script", ("devflow_AIDesignScript_*",), "latest", True, ("AIDesignScript",)),
            SourceGroup("2c_design_package", ("devflow_Design_*",), "latest", True, ("Design",)),
            SourceGroup("2c_development_design", ("devflow_DevelopmentDesign_*",), "latest", True, ("DevelopmentDesign",)),
        ],
        context=context,
    )
    return apply_development_plan_outputs(2, report)


if __name__ == "__main__":
    raise SystemExit(run_step_cli(2))
