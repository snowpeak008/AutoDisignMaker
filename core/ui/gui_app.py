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
    import threading

    from core.config.integrity import validate_data_integrity
    from core.paths import DRAFT_DIR, PROJECT_ROOT
    from core.save.manager import (
        current_save_id_readonly,
        load_save,
        prune_draft_snapshots,
        prune_old_drafts,
    )

    startup_error_status: tuple[str, str] | None = None
    try:
        validate_data_integrity()
    except RuntimeError as exc:
        logging.getLogger(__name__).warning("启动检查异常: %s", exc)
        startup_error_status = (f"系统: 启动检查异常 {exc}", "#FF6B6B")
        try:
            from core.ui.main_window import _current_main_window

            if _current_main_window is not None:
                _current_main_window.set_system_status_override(*startup_error_status)
        except Exception:
            logging.getLogger(__name__).debug("Failed to show startup warning", exc_info=True)
    prune_old_drafts(PROJECT_ROOT, keep_count=5)
    prune_draft_snapshots(PROJECT_ROOT, keep_per_draft=0)
    if not (DRAFT_DIR / "draft_file_map.json").exists():
        save_id = current_save_id_readonly(PROJECT_ROOT)
        if save_id:
            from core.ui.main_window import _current_main_window

            win = _current_main_window
            if win is not None:
                win.after(0, lambda: win.set_system_status_override("系统: 恢复上次存档中…"))

            def _do_load() -> None:
                try:
                    load_save(PROJECT_ROOT, save_id)
                except Exception as exc:
                    logging.getLogger(__name__).warning("自动加载存档失败: %s", exc)
                finally:
                    if win is not None:
                        try:
                            if startup_error_status is not None:
                                win.after(
                                    0,
                                    lambda: win.set_system_status_override(*startup_error_status),
                                )
                            else:
                                win.after(0, win.clear_system_status_override)
                        except Exception:
                            logging.getLogger(__name__).debug(
                                "Failed to clear auto-load status", exc_info=True
                            )

            threading.Thread(target=_do_load, daemon=True).start()


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
