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


def _deferred_startup() -> None:
    import logging

    from core.config.integrity import validate_data_integrity
    from core.paths import DRAFT_DIR, PROJECT_ROOT
    from core.save.manager import (
        current_save_id_readonly,
        load_save,
        prune_draft_snapshots,
        prune_old_drafts,
    )

    try:
        validate_data_integrity()
    except RuntimeError as exc:
        logging.getLogger(__name__).warning("启动检查异常: %s", exc)
        try:
            from core.ui.main_window import _current_main_window

            if _current_main_window is not None:
                _current_main_window._system_status_label.configure(
                    text=f"系统: 启动检查异常 {exc}",
                    fg="#FF6B6B",
                )
        except Exception:
            logging.getLogger(__name__).debug("Failed to show startup warning", exc_info=True)
    prune_old_drafts(PROJECT_ROOT, keep_count=5)
    prune_draft_snapshots(PROJECT_ROOT, keep_per_draft=0)
    if not (DRAFT_DIR / "draft_file_map.json").exists():
        save_id = current_save_id_readonly(PROJECT_ROOT)
        if save_id:
            try:
                load_save(PROJECT_ROOT, save_id)
            except Exception as exc:
                logging.getLogger(__name__).warning("自动加载存档失败: %s", exc)


def main() -> int:
    from core.config.loader import load_config
    from core.ui.main_window import MainWindow

    load_config()
    app = MainWindow()
    app.after_idle(_deferred_startup)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
