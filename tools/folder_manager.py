#!/usr/bin/env python3
"""
文件夹版本管理器

命名规则: {项目名}_{阶段名}_{日期}_v{版本号}
- 每个阶段独立版本递增
- 下游只查上游最高版本号
- Correction_* 是临时文件夹，放行后合并删除
"""

import shutil
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


SOURCE_DIR = Path(__file__).parent.parent / "source_artifacts"
PROJECT_NAME = "devflow"


def _sanitize_project_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    value = value.strip("_-")
    return value or PROJECT_NAME


def _default_project_name() -> str:
    configured = os.getenv("PIPELINE_PROJECT_NAME") or os.getenv("PROJECT_NAME")
    if configured:
        return _sanitize_project_name(configured)
    return PROJECT_NAME


DEFAULT_PROJECT = _default_project_name()


def _parse_version(dirname: str) -> int:
    """从文件夹名提取版本号，如 '<Project>_Design_20260530_v3' -> 3。"""
    parts = dirname.rsplit("_v", 1)
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 0


def project_glob(prefix: str, project: str = DEFAULT_PROJECT) -> str:
    return f"{project}_{prefix}_*"


def stage_globs(prefix: str, project: str = DEFAULT_PROJECT, *,
                include_legacy: bool = False) -> list[str]:
    _ = include_legacy
    return [project_glob(prefix, project)]


def find_latest(prefix: str, project: str = DEFAULT_PROJECT, *,
                include_legacy: bool = True) -> Optional[Path]:
    """查找某阶段最高版本文件夹。

    prefix: 阶段前缀，如 'Design', 'Idea', 'ProgReq'
    project: 项目名
    """
    candidates = []
    for pattern in stage_globs(prefix, project, include_legacy=include_legacy):
        candidates.extend(SOURCE_DIR.glob(pattern))
    candidates = sorted(candidates, reverse=True)
    if not candidates:
        return None
    # 按版本号排序，取最高
    candidates.sort(key=lambda p: _parse_version(p.name), reverse=True)
    return candidates[0]


def find_latest_design(project: str = DEFAULT_PROJECT) -> Optional[Path]:
    return find_latest("Design", project)


def find_latest_idea(project: str = DEFAULT_PROJECT) -> Optional[Path]:
    return find_latest("Idea", project)


def find_latest_prog_req(project: str = DEFAULT_PROJECT) -> Optional[Path]:
    return find_latest("ProgReq", project)


def make_folder(prefix: str, project: str = DEFAULT_PROJECT) -> Path:
    """创建新版本文件夹。

    自动查找当前最高版本并 +1，日期用今天。
    """
    today = datetime.now().strftime("%Y%m%d")
    latest = find_latest(prefix, project, include_legacy=False)
    next_version = (_parse_version(latest.name) + 1) if latest else 1
    folder_name = f"{project}_{prefix}_{today}_v{next_version}"
    folder = SOURCE_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def make_correction_folder(project: str = DEFAULT_PROJECT) -> Path:
    """创建临时修正增量文件夹。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = SOURCE_DIR / f"Correction_{timestamp}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def is_temp_folder(path: Path) -> bool:
    """判断是否为临时文件夹（仅 Correction_*）。"""
    return path.name.startswith("Correction_")


def list_temp_folders(project: str = DEFAULT_PROJECT) -> list[Path]:
    """列出所有临时文件夹。"""
    result = []
    for p in SOURCE_DIR.iterdir():
        if p.is_dir() and is_temp_folder(p):
            result.append(p)
    return sorted(result)


def merge_correction_to_permanent(correction_dir: Path, target_stage: str,
                                   project: str = DEFAULT_PROJECT) -> Path:
    """将修正增量合并到永久文件夹。

    策略：创建新的永久文件夹（版本 +1），从上一个永久文件夹复制内容，
    然后用 correction_dir 中的更新文件覆盖。
    """
    latest_perm = find_latest(target_stage, project)

    # 创建新版本永久文件夹
    today = datetime.now().strftime("%Y%m%d")
    next_v = (_parse_version(latest_perm.name) + 1) if latest_perm else 1
    new_folder = SOURCE_DIR / f"{project}_{target_stage}_{today}_v{next_v}"
    new_folder.mkdir(parents=True, exist_ok=True)

    # 复制上一版本内容
    if latest_perm:
        for item in latest_perm.iterdir():
            dest = new_folder / item.name
            if item.is_dir():
                if not dest.exists():
                    shutil.copytree(item, dest)
            else:
                if not dest.exists():
                    shutil.copy2(item, dest)

    # 用修正内容覆盖
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
    """删除所有临时文件夹，返回已删除列表。"""
    removed = []
    for folder in list_temp_folders(project):
        try:
            shutil.rmtree(folder)
            removed.append(folder)
        except OSError:
            pass
    return removed


def resolve_design_path(explicit: Optional[str] = None,
                         project: str = DEFAULT_PROJECT) -> Path:
    """解析设计文档路径。

    优先用显式指定，否则查最新 Design_* 文件夹，
    都没有则返回明确错误。
    """
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

    raise FileNotFoundError(
        "未找到当前项目设计文档。请先提交 devflow_Design_* 源资料。"
    )
