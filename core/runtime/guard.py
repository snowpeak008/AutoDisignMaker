"""Fail if runtime files reference a removed external agent runtime."""

from __future__ import annotations

import sys
from pathlib import Path

from core.paths import PROJECT_ROOT
from core.source.importer import forbidden_runtime_matches


def main() -> int:
    matches = forbidden_runtime_matches(PROJECT_ROOT)
    if matches:
        import json
        print(json.dumps(matches, ensure_ascii=False, indent=2))
        return 1
    print("No forbidden runtime references found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
