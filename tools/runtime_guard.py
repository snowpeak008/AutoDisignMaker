#!/usr/bin/env python3
"""Fail if runtime files reference a removed external agent runtime."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from steps.common import forbidden_runtime_matches


def main() -> int:
    matches = forbidden_runtime_matches()
    if matches:
        print(json.dumps(matches, ensure_ascii=False, indent=2))
        return 1
    print("no forbidden external agent runtime references found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

