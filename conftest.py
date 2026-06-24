from __future__ import annotations

import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path


PYTEST_BASETEMP_PATTERN = re.compile(r"^pytest_\d{8}_\d{6}_\d{6}$")


def _cleanup_old_pytest_dirs(sandbox: Path, max_age_days: int = 7) -> None:
    """Remove old timestamped pytest basetemp directories from sandbox."""
    if not sandbox.exists():
        return
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for path in sandbox.iterdir():
        if not path.is_dir() or not PYTEST_BASETEMP_PATTERN.fullmatch(path.name):
            continue
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            continue


def pytest_configure(config) -> None:
    """Bind pytest basetemp to sandbox/pytest_<timestamp> under the project root.

    Rule: {project_root}/sandbox/pytest_<timestamp>/
    A fresh timestamped directory is used each run so pytest never needs to
    scan or delete a previously-created basetemp — this avoids the Windows
    extended-path permission lock that occurs when pytest tries to clean up a
    directory created through Windows extended-path handling.
    Accumulated sandbox/pytest_* dirs are gitignored via sandbox/ and can be
    cleaned manually at any time.
    """
    if config.getoption("basetemp", default=None):
        return  # respect explicit --basetemp override

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / ".project_root").exists():
            sandbox = candidate / "sandbox"
            _cleanup_old_pytest_dirs(sandbox)
            config.option.basetemp = str(sandbox / f"pytest_{ts}")
            return

    sandbox = here / "sandbox"
    _cleanup_old_pytest_dirs(sandbox)
    config.option.basetemp = str(sandbox / f"pytest_{ts}")
