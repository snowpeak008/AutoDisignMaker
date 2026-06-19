#!/usr/bin/env python3
"""更新 freshness.json 哈希快照。

用法：python tools/memory/update_freshness.py
作用：扫描项目所有关键 Python 文件，更新 freshness.json 中的 SHA256 哈希值。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRESHNESS_PATH = PROJECT_ROOT / "knowledge/ai_memory/project_understanding/freshness.json"

KEY_FILES = [
    "core/main.py",
    "core/engines/generation.py",
    "core/registry.py",
    "core/paths.py",
    "core/plugin_manager.py",
    "core/stage_plugin.py",
    "core/context.py",
    "core/io.py",
    "core/stage.py",
    "core/adapters/base.py",
    "core/adapters/registry.py",
    "core/adapters/openai_adapter.py",
    "core/adapters/codex_adapter.py",
    "core/artifact/graph.py",
    "core/artifact/preflight.py",
    "core/artifact/reviewer.py",
    "core/artifact/validator.py",
    "core/source/importer.py",
    "core/source/groups.py",
    "core/config/loader.py",
    "core/config/integrity.py",
    "core/runtime/control.py",
    "core/runtime/preflight.py",
    "core/runtime/pipeline_state.py",
    "core/save/manager.py",
    "core/design/engine.py",
    "core/design/exporter.py",
    "core/design/ai_backend.py",
    "core/ui/gui_app.py",
    "core/ui/app_window.py",
    "core/ui/theme.py",
    "core/ui/ai_interview_window.py",
    "pipeline/_registry.json",
    "artifact_layer/registry.json",
]


def compute_file_hash(path: Path) -> dict[str, str | int]:
    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    size = path.stat().st_size
    return {"sha256": sha256, "size": size}


def main() -> int:
    files_data = {}
    missing = []

    for rel_path in KEY_FILES:
        full_path = PROJECT_ROOT / rel_path
        if full_path.exists():
            files_data[rel_path] = compute_file_hash(full_path)
        else:
            missing.append(rel_path)

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": files_data,
    }

    FRESHNESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRESHNESS_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ Updated freshness.json with {len(files_data)} files")
    if missing:
        print(f"⚠ Missing files: {', '.join(missing)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
