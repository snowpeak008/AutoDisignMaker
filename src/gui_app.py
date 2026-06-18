"""Unified GUI entry point.

The first integrated release reuses the migrated design workbench UI. DevFlow's
legacy GUI remains available at the project root as `gui_app.py` if copied later.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT_FOR_BOOTSTRAP = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT_FOR_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_BOOTSTRAP))


def main() -> int:
    from src.core.config_loader import load_config
    from src.core.data_integrity import validate_data_integrity
    from design_tool.ui.app_window import CommercialDesignApp

    load_config()
    validate_data_integrity()
    app = CommercialDesignApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
