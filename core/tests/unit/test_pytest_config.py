from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from core.paths import PROJECT_ROOT


def load_root_conftest():
    module_path = PROJECT_ROOT / "conftest.py"
    spec = importlib.util.spec_from_file_location("root_pytest_conftest", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cleanup_old_pytest_dirs_only_removes_timestamped_dirs(tmp_path: Path) -> None:
    root_conftest = load_root_conftest()
    old_dir = tmp_path / "pytest_20260601_010203_123456"
    fresh_dir = tmp_path / "pytest_20260624_010203_123456"
    cache_dir = tmp_path / "pytest_cache"
    tmp_dir = tmp_path / "pytest_tmp"
    other_dir = tmp_path / "pytest_notes"
    for path in (old_dir, fresh_dir, cache_dir, tmp_dir, other_dir):
        path.mkdir()

    old_time = (datetime.now() - timedelta(days=10)).timestamp()
    fresh_time = datetime.now().timestamp()
    os.utime(old_dir, (old_time, old_time))
    os.utime(fresh_dir, (fresh_time, fresh_time))
    os.utime(cache_dir, (old_time, old_time))
    os.utime(tmp_dir, (old_time, old_time))
    os.utime(other_dir, (old_time, old_time))

    root_conftest._cleanup_old_pytest_dirs(tmp_path, max_age_days=7)

    assert not old_dir.exists()
    assert fresh_dir.exists()
    assert cache_dir.exists()
    assert tmp_dir.exists()
    assert other_dir.exists()
