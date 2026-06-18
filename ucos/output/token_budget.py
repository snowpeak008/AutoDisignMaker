from __future__ import annotations

import json
from typing import Any


MAX_TOKENS = 2000
PRIORITIES = [
    ("working", 200, False),
    ("identity", 150, False),
    ("active_skills", 300, False),
    ("short_term", 400, True),
    ("episodic", 500, True),
    ("semantic", 450, True),
]


def estimate_tokens(value: Any) -> int:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return max(1, len(text) // 4)


def enforce_budget(sections: dict[str, Any], max_tokens: int = MAX_TOKENS) -> dict[str, Any]:
    result = dict(sections)
    result["token_estimate"] = estimate_tokens(result)
    if result["token_estimate"] <= max_tokens:
        return result

    while result["token_estimate"] > max_tokens:
        changed = False
        for key, minimum, trim_allowed in reversed(PRIORITIES):
            if not trim_allowed or key not in result:
                continue
            current_tokens = estimate_tokens(result[key])
            if current_tokens <= minimum:
                continue
            trimmed = _trim_value(result[key])
            if trimmed != result[key]:
                result[key] = trimmed
                changed = True
                result["token_estimate"] = estimate_tokens(result)
                if result["token_estimate"] <= max_tokens:
                    return result
        if not changed:
            break
    return result


def _trim_value(value: Any) -> Any:
    if isinstance(value, list):
        if len(value) <= 1:
            return value
        return value[: max(1, len(value) // 2)]
    if isinstance(value, dict):
        # If the dict has multiple keys, remove the latter half
        keys = list(value.keys())
        if len(keys) > 1:
            keep = keys[: max(1, len(keys) // 2)]
            return {key: value[key] for key in keep}
        # Single-key dict: recursively trim the value inside
        if len(keys) == 1:
            inner = _trim_value(value[keys[0]])
            if inner != value[keys[0]]:
                return {keys[0]: inner}
        return value
    if isinstance(value, str):
        if len(value) <= 200:
            return value
        return value[: max(200, len(value) // 2)]
    return value
