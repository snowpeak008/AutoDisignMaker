from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ucos.engines.memory_engine import MemoryEngine, MemoryTier


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tier", choices=[item.value for item in MemoryTier])
    parser.add_argument("keywords", nargs="*")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    engine = MemoryEngine(Path.cwd())
    entries = engine.query(MemoryTier(args.tier), args.keywords, args.top_k)
    print(json.dumps([entry.content for entry in entries], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
