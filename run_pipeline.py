#!/usr/bin/env python3
"""Compatibility command for the migrated orchestrator."""

from __future__ import annotations

import argparse

from orchestrator import main as orchestrator_main
from tools.pipeline_registry import iter_steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Run migrated pipeline steps.")
    parser.add_argument("--step", type=int)
    parser.add_argument("--from-step", type=int, default=0)
    parser.add_argument("--to-step", type=int)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--auto-approve", action="store_true")
    args = parser.parse_args()

    if args.list or args.dry_run:
        for step in iter_steps():
            print(f"{step.number:02d} {step.name}: {step.command}")
        return 0

    if args.step is not None:
        from_step = args.step
        stop_step = args.step
    else:
        from_step = args.from_step
        stop_step = args.to_step if args.to_step is not None else 15

    argv = ["--from-step", str(from_step), "--stop-step", str(stop_step)]
    if args.auto_approve:
        argv.append("--auto-approve")
    return orchestrator_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
