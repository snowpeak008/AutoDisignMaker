from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT_FOR_CACHE = Path(__file__).resolve().parents[1]
PYTHON_PYCACHE_PREFIX = PROJECT_ROOT_FOR_CACHE / ".cache" / "pycache"
os.environ.setdefault("PYTHONPYCACHEPREFIX", str(PYTHON_PYCACHE_PREFIX))
sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]
