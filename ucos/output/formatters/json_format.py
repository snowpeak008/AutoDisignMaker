from __future__ import annotations

import json
from typing import Any


def format_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2)

