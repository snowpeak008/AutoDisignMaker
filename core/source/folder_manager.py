"""Source artifact folder version manager.

Naming convention: {project}_{stage}_{date}_v{version}
- Each stage has an independent version counter.
- Downstream stages only read the highest version of upstream stages.
- Correction_* folders are temporary; merge then delete.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.paths import SOURCE_ARTIFACTS_DIR

PROJECT_NAME = "devflow"


def _sanitize_project_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    return value.strip("_-") or PROJECT_NAME


def _default_project_name() -> str:
    configured = os.getenv("PIPELINE_PROJECT_NAME") or os.getenv("PROJECT_NAME")
    return _sanitize_project_name(configured) if configured else PROJECT_NAME


DEFAULT_PROJECT = _default_project_name()


def _parse_version(dirname: str) -> int:
    parts = dirname.rsplit("_v", 1)
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 0


def project_glob(prefix: str, project: str = DEFAULT_PROJECT) -> str:
    return f"{project}_{prefix}_*"


def stage_globs(prefix: str, project: str = DEFAULT_PROJECT, *, include_legacy: bool = False) -> list[str]:
    _ = include_legacy
    return [project_glob(prefix, project)]


def find_latest(prefix: str, project: str = DEFAULT_PROJECT, *, include_legacy: bool = True) -> Optional[Path]:
    candidates: list[Path] = []
    for pattern in stage_globs(prefix, project, include_legacy=include_legacy):
        candidates.extend(SOURCE_ARTIFACTS_DIR.glob(pattern))
    if not candidates:
        return None
    candidates.sort(key=lambda p: _parse_version(p.name), reverse=True)
    return candidates[0]


def find_latest_design(project: str = DEFAULT_PROJECT) -> Optional[Path]:
    return find_latest("Design", project)


def find_latest_idea(project: str = DEFAULT_PROJECT) -> Optional[Path]:
    return find_latest("Idea", project)


def find_latest_prog_req(project: str = DEFAULT_PROJECT) -> Optional[Path]:
    return find_latest("ProgReq", project)


def make_folder(prefix: str, project: str = DEFAULT_PROJECT) -> Path:
    today = datetime.now().strftime("%Y%m%d")
    latest = find_latest(prefix, project, include_legacy=False)
    next_version = (_parse_version(latest.name) + 1) if latest else 1
    folder_name = f"{project}_{prefix}_{today}_v{next_version}"
    folder = SOURCE_ARTIFACTS_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def make_correction_folder(project: str = DEFAULT_PROJECT) -> Path:
    _ = project
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = SOURCE_ARTIFACTS_DIR / f"Correction_{timestamp}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def is_temp_folder(path: Path) -> bool:
    return path.name.startswith("Correction_")


def list_temp_folders(project: str = DEFAULT_PROJECT) -> list[Path]:
    _ = project
    return sorted(p for p in SOURCE_ARTIFACTS_DIR.iterdir() if p.is_dir() and is_temp_folder(p))


def merge_correction_to_permanent(
    correction_dir: Path, target_stage: str, project: str = DEFAULT_PROJECT
) -> Path:
    latest_perm = find_latest(target_stage, project)
    today = datetime.now().strftime("%Y%m%d")
    next_v = (_parse_version(latest_perm.name) + 1) if latest_perm else 1
    new_folder = SOURCE_ARTIFACTS_DIR / f"{project}_{target_stage}_{today}_v{next_v}"
    new_folder.mkdir(parents=True, exist_ok=True)
    if latest_perm:
        for item in latest_perm.iterdir():
            dest = new_folder / item.name
            if item.is_dir():
                if not dest.exists():
                    shutil.copytree(item, dest)
            else:
                if not dest.exists():
                    shutil.copy2(item, dest)
    if correction_dir.exists():
        for item in correction_dir.iterdir():
            dest = new_folder / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
    return new_folder


def cleanup_temp_folders(project: str = DEFAULT_PROJECT) -> list[Path]:
    removed = []
    for folder in list_temp_folders(project):
        try:
            shutil.rmtree(folder)
            removed.append(folder)
        except OSError:
            pass
    return removed


def resolve_design_path(explicit: Optional[str] = None, project: str = DEFAULT_PROJECT) -> Path:
    if explicit:
        p = Path(explicit)
        if p.is_dir():
            design_md = p / "frozen_game_design.md"
            if design_md.exists():
                return design_md
        elif p.exists():
            return p
        raise FileNotFoundError(f"指定路径不存在: {explicit}")
    latest = find_latest_design(project)
    if latest:
        design_md = latest / "frozen_game_design.md"
        if design_md.exists():
            return design_md
    raise FileNotFoundError("未找到当前项目设计文档。请先提交 devflow_Design_* 源资料。")
