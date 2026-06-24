"""Root-level GUI compatibility wrapper."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT_FOR_CACHE = Path(__file__).resolve().parent
PYTHON_PYCACHE_PREFIX = PROJECT_ROOT_FOR_CACHE / ".cache" / "pycache"
os.environ.setdefault("PYTHONPYCACHEPREFIX", str(PYTHON_PYCACHE_PREFIX))
sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]

from core.ui.gui_app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
