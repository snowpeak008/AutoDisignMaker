"""Unified GUI entry point.

The first integrated release reuses the migrated design workbench UI. DevFlow's
legacy GUI remains available at the project root as `gui_app.py` if copied later.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT_FOR_BOOTSTRAP = Path(__file__).resolve().parents[2]
PYTHON_PYCACHE_PREFIX = PROJECT_ROOT_FOR_BOOTSTRAP / ".cache" / "pycache"
os.environ.setdefault("PYTHONPYCACHEPREFIX", str(PYTHON_PYCACHE_PREFIX))
sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]

if str(PROJECT_ROOT_FOR_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_BOOTSTRAP))


def main() -> int:
    from core.paths import PROJECT_ROOT
    from core.config.loader import load_config
    from core.config.integrity import validate_data_integrity
    from core.save.manager import prune_draft_snapshots, prune_old_drafts
    from core.ui.main_window import MainWindow

    load_config()
    validate_data_integrity()
    prune_old_drafts(PROJECT_ROOT, keep_count=5)
    prune_draft_snapshots(PROJECT_ROOT, keep_per_draft=0)
    app = MainWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
