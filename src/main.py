"""Command-line entry point for AutoDesignMaker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT_FOR_BOOTSTRAP = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT_FOR_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_BOOTSTRAP))

from src.core.context import StageContext
from src.core.config_loader import load_config
from src.core.data_integrity import validate_data_integrity
from src.core.plugin_manager import PluginManager


def main(argv: list[str] | None = None) -> int:
    load_config()
    validate_data_integrity()
    parser = argparse.ArgumentParser(description="AutoDesignMaker command line")
    parser.add_argument("--stage", help="Run a registered stage, for example D1 or 00")
    parser.add_argument("--list-stages", action="store_true")
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--skip-actual-dev-preflight", action="store_true")
    args = parser.parse_args(argv)

    manager = PluginManager()
    if args.list_stages:
        for stage_id in manager.list_stages():
            print(stage_id)
        return 0
    if not args.stage:
        parser.print_help()
        return 0

    plugin = manager.load_stage(args.stage)
    context = StageContext(
        stage_id=args.stage,
        test_mode=args.test_mode,
        metadata={"skip_actual_dev_preflight": args.skip_actual_dev_preflight},
    )
    result = plugin.run(context)
    if result.message:
        print(result.message)
    if result.errors:
        for error in result.errors:
            print(error, file=sys.stderr)
    print(f"{args.stage}: {result.status}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
