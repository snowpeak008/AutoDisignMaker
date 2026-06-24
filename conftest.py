from __future__ import annotations

from datetime import datetime
from pathlib import Path


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
            config.option.basetemp = str(candidate / "sandbox" / f"pytest_{ts}")
            return

    config.option.basetemp = str(here / "sandbox" / f"pytest_{ts}")
