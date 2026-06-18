#!/usr/bin/env python3
"""Compatibility wrapper for the official deterministic orchestrator.

The supported runtime is `orchestrator.py`. This file exists only so older
operator habits such as `python pipeline.py status` cannot accidentally route
into the removed experimental `pipeline/` and `stages/` state machine.
"""

from __future__ import annotations

import sys

from orchestrator import main as orchestrator_main


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    if not args or args[0] in {"status", "list", "--list"}:
        return orchestrator_main(["--list"])
    if args[0] in {"run", "run-all", "resume", "retry"}:
        return orchestrator_main(["--from-step", "0", "--stop-step", "15", "--auto-approve"])
    print("Unsupported legacy pipeline command. Use orchestrator.py or DevFlow.exe.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
