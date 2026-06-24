from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_pycache_prefix() -> Path | None:
    """Redirect project Python bytecode caches into .cache/pycache."""
    project_root = Path(__file__).resolve().parent
    if not (project_root / ".project_root").exists():
        return None
    prefix = Path(
        os.environ.get("PYTHONPYCACHEPREFIX") or project_root / ".cache" / "pycache"
    )
    os.environ.setdefault("PYTHONPYCACHEPREFIX", str(prefix))
    sys.pycache_prefix = str(prefix)
    return prefix


configure_pycache_prefix()
