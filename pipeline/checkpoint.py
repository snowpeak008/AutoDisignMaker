"""Checkpoint helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from pipeline.state import OUTPUTS_DIR, ROOT, now_iso


def create_checkpoint(name: str) -> Path:
    checkpoint_dir = OUTPUTS_DIR / "checkpoints" / f"{name}_{now_iso().replace(':', '')}"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    artifacts = OUTPUTS_DIR / "artifacts"
    if artifacts.exists():
        shutil.copytree(artifacts, checkpoint_dir / "artifacts", dirs_exist_ok=True)
    state_file = OUTPUTS_DIR / "state" / "project_state.json"
    if state_file.exists():
        shutil.copy2(state_file, checkpoint_dir / "project_state.json")
    marker = checkpoint_dir / "root.txt"
    marker.write_text(str(ROOT), encoding="utf-8")
    return checkpoint_dir
