#!/usr/bin/env python3
"""Small YAML compatibility layer.

PyYAML is optional in this repo. When it is unavailable, we read and write
JSON-compatible YAML. JSON is a valid YAML subset, so the .yaml file contract
remains usable without adding a new runtime dependency.
"""

from __future__ import annotations

import json
from typing import Any

try:
    import yaml as _pyyaml  # type: ignore
except ModuleNotFoundError:
    _pyyaml = None


class YAMLError(ValueError):
    pass


if _pyyaml is not None:
    YAMLError = _pyyaml.YAMLError


def safe_load(text: str) -> Any:
    if _pyyaml is not None:
        return _pyyaml.safe_load(text)
    content = str(text or "").strip()
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise YAMLError(
            "PyYAML is not installed and this file is not JSON-compatible YAML."
        ) from exc


def safe_dump(data: Any, *, allow_unicode: bool = True,
              sort_keys: bool = False, **_kwargs) -> str:
    if _pyyaml is not None:
        return _pyyaml.safe_dump(data, allow_unicode=allow_unicode, sort_keys=sort_keys)
    return json.dumps(data, ensure_ascii=not allow_unicode, sort_keys=sort_keys, indent=2)


def dump(data: Any, *, allow_unicode: bool = True,
         sort_keys: bool = False, **kwargs) -> str:
    return safe_dump(data, allow_unicode=allow_unicode, sort_keys=sort_keys, **kwargs)
