#!/usr/bin/env python3
"""Unified deterministic orchestrator for steps 0-15."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from steps.common import STEP_SPECS, append_gate_log, finalize_migration_audit_with_self_layer, stage_dir
from tools.artifact_layer import (
    emit_dependency_graph,
    preflight_stage_contract,
    run_artifact_validators,
    run_review_pipeline,
    topological_step_order,
)
from tools import save_manager
from tools.actual_development_preflight import assert_actual_development_preflight, run_actual_development_preflight
from tools import runtime_control
from tools.runtime_control import PipelineStopRequested


BASE_DIR = Path(__file__).resolve().parent

STEP_MODULES = {
    0: "steps.step0_idea_intake",
    1: "steps.step1_demo",
    2: "steps.step2_design_review",
    3: "steps.step3_program_requirements",
    4: "steps.step4_art_requirements",
    5: "steps.step5_program_review",
    6: "steps.step6_art_review",
    7: "steps.step7_design_to_plan",
    8: "steps.step8_art_plan",
    9: "steps.step9_asset_alignment",
    10: "steps.step10_dev_execution",
    11: "steps.step11_art_production",
    12: "steps.step12_integration_validation",
    13: "steps.step13_build_package",
    14: "steps.step14_delta_patch",
    15: "steps.step15_migration_audit",
}


def base_context(*, auto_approve: bool) -> dict[str, Any]:
    return {
        "base_dir": BASE_DIR,
        "auto_approve": auto_approve,
    }


def _manual_gate(step_number: int, auto_approve: bool) -> None:
    if auto_approve:
        return
    spec = STEP_SPECS[step_number]
    answer = input(f"Run step {step_number:02d} ({spec.slug})? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise RuntimeError(f"Step {step_number:02d} was not approved.")


def run_step(step_number: int, *, context: dict[str, Any]) -> dict[str, Any]:
    module_name = STEP_MODULES[step_number]
    module = importlib.import_module(module_name)
    if not hasattr(module, "run"):
        raise RuntimeError(f"{module_name} does not expose run(context).")
    print(f"== step {step_number:02d}: {STEP_SPECS[step_number].slug} ==")
    return module.run(context)


def run_range(
    from_step: int = 0,
    stop_step: int = 15,
    *,
    auto_approve: bool = False,
    skip_actual_dev_preflight: bool = False,
    run_id: str | None = None,
) -> int:
    if from_step < 0 or stop_step > 15 or from_step > stop_step:
        raise ValueError("Step range must be within 0-15 and from_step <= stop_step.")
    if not skip_actual_dev_preflight:
        try:
            assert_actual_development_preflight(BASE_DIR, write_report=True)
        except Exception as exc:
            print(f"Actual development preflight blocked: {exc}", file=sys.stderr)
            return 1
    run_id = run_id or runtime_control.new_run_id()
    runtime_control.clear_stale_stop_request(BASE_DIR, run_id)
    runtime_control.write_run_state(
        BASE_DIR,
        status="running",
        run_id=run_id,
        from_step=from_step,
        stop_step=stop_step,
        current_step=None,
    )
    save_manager.ensure_current_save(BASE_DIR)
    emit_dependency_graph()
    selected_steps = topological_step_order(from_step, stop_step)
    context = base_context(auto_approve=auto_approve)
    for index, step_number in enumerate(selected_steps):
        try:
            runtime_control.write_run_state(
                BASE_DIR,
                status="running",
                run_id=run_id,
                from_step=from_step,
                stop_step=stop_step,
                current_step=step_number,
            )
            if runtime_control.stop_requested(BASE_DIR):
                runtime_control.mark_stopped(
                    BASE_DIR,
                    current_step=step_number,
                    next_step=step_number,
                    boundary="before_stage",
                    reason="operator_stop",
                )
                save_manager.retry_sync(
                    BASE_DIR,
                    event="run_stage_stopped",
                    stage=step_number,
                    message="Operator requested soft stop before stage start.",
                    log=lambda text: print(text, end=""),
                )
                print(json.dumps({
                    "step": step_number,
                    "status": "stopped",
                    "boundary": "before_stage",
                }, ensure_ascii=False))
                return 130
            save_manager.retry_sync(
                BASE_DIR,
                event="run_stage_start",
                stage=step_number,
                log=lambda text: print(text, end=""),
            )
            preflight_stage_contract(step_number)
            _manual_gate(step_number, auto_approve)
            result = run_step(step_number, context=context)
            review_report = run_review_pipeline(step_number)
            artifact_validation = run_artifact_validators(step_number)
            if step_number == 15:
                finalize_migration_audit_with_self_layer()
            save_manager.retry_sync(
                BASE_DIR,
                event="run_stage_success",
                stage=step_number,
                message=json.dumps({
                    "status": result.get("status"),
                    "artifact_review": review_report.get("status"),
                    "artifact_validation": artifact_validation.get("status"),
                }, ensure_ascii=False),
                log=lambda text: print(text, end=""),
            )
            print(json.dumps({
                "step": step_number,
                "status": result.get("status"),
                "artifact_review": review_report.get("status"),
                "artifact_validation": artifact_validation.get("status"),
                "artifacts_dir": str(stage_dir(step_number)),
            }, ensure_ascii=False))
            if runtime_control.stop_requested(BASE_DIR):
                next_step = selected_steps[index + 1] if index + 1 < len(selected_steps) else None
                runtime_control.mark_stopped(
                    BASE_DIR,
                    current_step=step_number,
                    next_step=next_step,
                    boundary="after_stage",
                    reason="operator_stop",
                )
                save_manager.retry_sync(
                    BASE_DIR,
                    event="run_stage_stopped",
                    stage=step_number,
                    message="Operator requested soft stop after current stage.",
                    log=lambda text: print(text, end=""),
                )
                print(json.dumps({
                    "step": step_number,
                    "status": "stopped",
                    "boundary": "after_stage",
                    "next_step": next_step,
                }, ensure_ascii=False))
                return 130
        except PipelineStopRequested as exc:
            append_gate_log(step_number, "stopped", imported=False, message=str(exc))
            runtime_control.mark_stopped(
                BASE_DIR,
                current_step=step_number,
                boundary="inside_stage",
                reason=str(exc) or "operator_stop",
            )
            try:
                save_manager.retry_sync(
                    BASE_DIR,
                    event="run_stage_stopped",
                    stage=step_number,
                    message=str(exc),
                    log=lambda text: print(text, end=""),
                )
            except Exception as sync_exc:
                print(f"Save sync failed after stage stop: {sync_exc}", file=sys.stderr)
            print(json.dumps({
                "step": step_number,
                "status": "stopped",
                "message": str(exc),
                "artifacts_dir": str(stage_dir(step_number)),
            }, ensure_ascii=False))
            return 130
        except Exception as exc:
            append_gate_log(step_number, "failed", imported=False, message=str(exc))
            try:
                save_manager.retry_sync(
                    BASE_DIR,
                    event="run_stage_failed",
                    stage=step_number,
                    message=str(exc),
                    log=lambda text: print(text, end=""),
                )
            except Exception as sync_exc:
                print(f"Save sync failed after stage failure: {sync_exc}", file=sys.stderr)
            print(f"Step {step_number:02d} failed: {exc}", file=sys.stderr)
            return 1
    runtime_control.write_run_state(
        BASE_DIR,
        status="success",
        run_id=run_id,
        from_step=from_step,
        stop_step=stop_step,
        current_step=stop_step,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run migrated deterministic pipeline steps 0-15.")
    parser.add_argument("--from-step", type=int, default=0)
    parser.add_argument("--stop-step", type=int, default=15)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--skip-actual-dev-preflight", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.list:
        for step_number, spec in STEP_SPECS.items():
            print(f"{step_number:02d} {spec.slug} - {spec.title}")
        return 0
    if args.preflight_only:
        report = run_actual_development_preflight(BASE_DIR, write_report=True)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("status") == "passed" else 1

    return run_range(
        args.from_step,
        args.stop_step,
        auto_approve=args.auto_approve,
        skip_actual_dev_preflight=args.skip_actual_dev_preflight,
        run_id=args.run_id or None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
