#!/usr/bin/env python3
from steps.common import run_audit_step, run_step_cli


def run(context=None):
    return run_audit_step(context)


if __name__ == "__main__":
    raise SystemExit(run_step_cli(15))
