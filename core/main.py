"""AutoDesignMaker — 唯一程序入口。

合并自 src/main.py + orchestrator.py + run_pipeline.py
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import sys

from core.paths import PROJECT_ROOT
from core.context import StageContext
from core.config.loader import load_config
from core.config.integrity import validate_data_integrity
from core.plugin_manager import PluginManager
from core.artifact.graph import topological_step_order, emit_dependency_graph
from core.artifact.preflight import preflight_stage_contract
from core.artifact.reviewer import run_review_pipeline
from core.artifact.validator import run_artifact_validators
from core.save.manager import (
    ensure_current_save,
    prune_old_drafts,
    prune_sibling_draft_outputs,
    reset_current_draft_outputs,
    retry_sync,
)
from core.runtime.control import (
    PipelineStopRequested,
    new_run_id,
    stop_requested,
    write_run_state,
    mark_stopped,
    clear_stale_stop_request,
)
from core.runtime.preflight import assert_actual_development_preflight
from core.registry import STEP_SPECS, max_step_number


@contextmanager
def _manual_gate_overrides(
    *, skip_all_gates: bool = False, skip_gates: set[int] | None = None
):
    previous_all = os.environ.get("AUTODESIGNMAKER_SKIP_ALL_GATES")
    previous_steps = os.environ.get("AUTODESIGNMAKER_SKIP_GATES")
    try:
        if skip_all_gates:
            os.environ["AUTODESIGNMAKER_SKIP_ALL_GATES"] = "1"
        if skip_gates:
            os.environ["AUTODESIGNMAKER_SKIP_GATES"] = ",".join(
                f"{step:02d}" for step in sorted(skip_gates)
            )
        yield
    finally:
        if previous_all is None:
            os.environ.pop("AUTODESIGNMAKER_SKIP_ALL_GATES", None)
        else:
            os.environ["AUTODESIGNMAKER_SKIP_ALL_GATES"] = previous_all
        if previous_steps is None:
            os.environ.pop("AUTODESIGNMAKER_SKIP_GATES", None)
        else:
            os.environ["AUTODESIGNMAKER_SKIP_GATES"] = previous_steps


def run_range(
    from_step: int = 0,
    stop_step: int | None = None,
    *,
    auto_approve: bool = False,
    skip_preflight: bool = False,
    run_id: str | None = None,
    skip_all_gates: bool = False,
    skip_gates: set[int] | None = None,
) -> int:
    max_step = max_step_number()
    stop_step = max_step if stop_step is None else stop_step
    if from_step < 0 or stop_step > max_step or from_step > stop_step:
        raise ValueError(
            f"Step range must be within 0-{max_step} and from_step <= stop_step."
        )
    if not skip_preflight:
        try:
            assert_actual_development_preflight(PROJECT_ROOT, write_report=True)
        except Exception as exc:
            print(f"Preflight blocked: {exc}", file=sys.stderr)
            return 1
    if from_step == 0:
        reset_current_draft_outputs(PROJECT_ROOT, stage_from=0)
        prune_sibling_draft_outputs(PROJECT_ROOT, stage_from=0)
    run_id = run_id or new_run_id()
    clear_stale_stop_request(PROJECT_ROOT, run_id)
    write_run_state(PROJECT_ROOT, status="running", run_id=run_id,
                    from_step=from_step, stop_step=stop_step, current_step=None)
    ensure_current_save(PROJECT_ROOT)
    emit_dependency_graph()
    manager = PluginManager()
    steps = topological_step_order(from_step, stop_step)

    with _manual_gate_overrides(
        skip_all_gates=skip_all_gates, skip_gates=skip_gates or set()
    ):
        for step_num in steps:
            spec = STEP_SPECS[step_num]
            try:
                write_run_state(PROJECT_ROOT, status="running", run_id=run_id,
                                from_step=from_step, stop_step=stop_step, current_step=step_num)
                if stop_requested(PROJECT_ROOT):
                    mark_stopped(PROJECT_ROOT, current_step=step_num, boundary="before_stage")
                    retry_sync(PROJECT_ROOT, event="run_stage_stopped", stage=step_num,
                               message="Operator stop before stage.", log=lambda t: print(t, end=""))
                    return 130
                if not auto_approve:
                    ans = input(f"Run step {step_num:02d} ({spec.slug})? [y/N] ").strip().lower()
                    if ans not in {"y", "yes"}:
                        raise RuntimeError(f"Step {step_num:02d} not approved.")
                retry_sync(PROJECT_ROOT, event="run_stage_start", stage=step_num,
                           log=lambda t: print(t, end=""))
                preflight_stage_contract(step_num)
                plugin = manager.load_stage(f"{step_num:02d}")
                ctx = StageContext(stage_id=f"{step_num:02d}")
                result = plugin.run(ctx)
                if result.status == "waiting_confirmation":
                    payload = {
                        "status": result.status,
                        "confirmation_ui": result.outputs.get("confirmation_ui", ""),
                        "stage": step_num,
                    }
                    write_run_state(
                        PROJECT_ROOT,
                        status="waiting_confirmation",
                        run_id=run_id,
                        from_step=from_step,
                        stop_step=stop_step,
                        current_step=step_num,
                        confirmation_ui=payload["confirmation_ui"],
                    )
                    retry_sync(
                        PROJECT_ROOT,
                        event="run_stage_waiting_confirmation",
                        stage=step_num,
                        message=json.dumps(payload),
                        log=lambda t: print(t, end=""),
                    )
                    print(json.dumps({"step": step_num, "status": result.status}))
                    return 0
                run_review_pipeline(step_num)
                run_artifact_validators(step_num)
                retry_sync(PROJECT_ROOT, event="run_stage_success", stage=step_num,
                           message=json.dumps({"status": result.status}),
                           log=lambda t: print(t, end=""))
                print(json.dumps({"step": step_num, "status": result.status}))
                if stop_requested(PROJECT_ROOT):
                    mark_stopped(PROJECT_ROOT, current_step=step_num, boundary="after_stage")
                    return 130
            except PipelineStopRequested as exc:
                mark_stopped(PROJECT_ROOT, current_step=step_num, boundary="inside_stage")
                try:
                    retry_sync(PROJECT_ROOT, event="run_stage_stopped", stage=step_num,
                               message=str(exc), log=lambda t: print(t, end=""))
                except Exception:
                    pass
                return 130
            except Exception as exc:
                try:
                    retry_sync(PROJECT_ROOT, event="run_stage_failed", stage=step_num,
                               message=str(exc), log=lambda t: print(t, end=""))
                except Exception:
                    pass
                print(f"Step {step_num:02d} failed: {exc}", file=sys.stderr)
                return 1

    write_run_state(PROJECT_ROOT, status="success", run_id=run_id,
                    from_step=from_step, stop_step=stop_step, current_step=stop_step)
    return 0


def main(argv: list[str] | None = None) -> int:
    load_config()
    validate_data_integrity()
    prune_old_drafts(PROJECT_ROOT, keep_count=5)
    parser = argparse.ArgumentParser(description="AutoDesignMaker")
    parser.add_argument("--from-step", type=int, default=0)
    parser.add_argument("--stop-step", type=int, default=max_step_number())
    parser.add_argument("--step", type=int, help="Run single step")
    parser.add_argument("--stage", help="Run design stage by ID (D1/D2/00/01...)")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--skip-all-gates", action="store_true")
    parser.add_argument("--skip-gate-07", action="store_true")
    parser.add_argument(
        "--skip-gate-08",
        action="store_true",
        help=(
            "(Deprecated) Legacy alias for --skip-gate-07. "
            "After the Step07/08 merge, art style confirmation is at Step07."
        ),
    )
    args = parser.parse_args(argv)
    if args.skip_gate_08:
        print(
            "Warning: --skip-gate-08 is deprecated; use --skip-gate-07 instead. "
            "After the Step07/08 merge, art style confirmation is at Step07.",
            file=sys.stderr,
        )

    if args.list:
        for num, spec in STEP_SPECS.items():
            print(f"{num:02d} {spec.slug} - {spec.title}")
        return 0

    if args.preflight_only:
        from core.runtime.preflight import run_actual_development_preflight
        report = run_actual_development_preflight(PROJECT_ROOT, write_report=True)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("status") == "passed" else 1

    if args.stage:
        manager = PluginManager()
        plugin = manager.load_stage(args.stage)
        ctx = StageContext(stage_id=args.stage)
        result = plugin.run(ctx)
        print(json.dumps({"stage": args.stage, "status": result.status}))
        return 0 if result.ok else 1

    from_step = args.step if args.step is not None else args.from_step
    stop_step = args.step if args.step is not None else args.stop_step
    return run_range(
        from_step, stop_step,
        auto_approve=args.auto_approve,
        skip_preflight=args.skip_preflight,
        run_id=args.run_id or None,
        skip_all_gates=args.skip_all_gates,
        skip_gates={7} if (args.skip_gate_07 or args.skip_gate_08) else set(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
