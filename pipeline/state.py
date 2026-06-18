"""Project state read/write helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT / "outputs"
STATE_DIR = OUTPUTS_DIR / "state"
STATE_PATH = STATE_DIR / "project_state.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_state() -> dict[str, Any]:
    return {
        "project_id": ROOT.name,
        "current_stage": 3,
        "status": "ready",
        "frozen_stages": [0, 1, 2],
        "rollback": {"active": False, "target_stage": None},
        "stages": {},
        "artifacts": {},
        "last_checkpoint": "",
        "updated_at": now_iso(),
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return default_state()
    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    base = default_state()
    base.update(data)
    base.setdefault("stages", {})
    base.setdefault("artifacts", {})
    return base


def save_state(state: dict[str, Any]) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return STATE_PATH
