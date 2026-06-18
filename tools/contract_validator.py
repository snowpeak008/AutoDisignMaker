#!/usr/bin/env python3
"""Lightweight validators for pipeline handoff contracts.

This intentionally supports only the JSON Schema subset used by the local
pipeline schemas: type, required, properties, items, and enum.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import yaml_compat as yaml


TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def _matches_type(data: Any, expected_type: str) -> bool:
    if expected_type == "null":
        return data is None
    if expected_type == "integer":
        return isinstance(data, int) and not isinstance(data, bool)
    if expected_type == "number":
        return isinstance(data, (int, float)) and not isinstance(data, bool)
    allowed = TYPE_MAP.get(expected_type)
    return bool(allowed and isinstance(data, allowed))


def load_structured_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text) or {}
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return json.loads(text)


def validate_contract(data: Any, schema: dict[str, Any], *,
                      path: str = "$") -> list[str]:
    errors: list[str] = []
    if "anyOf" in schema:
        branch_errors = [
            validate_contract(data, branch, path=path)
            for branch in schema.get("anyOf", [])
            if isinstance(branch, dict)
        ]
        if any(not item for item in branch_errors):
            return []
        flat_errors = [error for branch in branch_errors for error in branch]
        errors.append(f"{path}: did not match any allowed schema")
        errors.extend(flat_errors)
        return errors

    expected_type = schema.get("type")
    if expected_type:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(data, item) for item in expected_types):
            errors.append(f"{path}: expected {expected_type}, got {type(data).__name__}")
            return errors

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}, got {data!r}")

    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}.{key}: required field missing")
        properties = schema.get("properties", {})
        for key, child in data.items():
            if key in properties:
                errors.extend(validate_contract(child, properties[key], path=f"{path}.{key}"))

    if isinstance(data, list) and "items" in schema:
        item_schema = schema["items"]
        for index, item in enumerate(data):
            errors.extend(validate_contract(item, item_schema, path=f"{path}[{index}]"))

    return errors


def validate_contract_file(contract_path: Path, schema_path: Path) -> list[str]:
    data = load_structured_file(contract_path)
    schema = load_structured_file(schema_path)
    return validate_contract(data, schema)


def write_validation_report(report_path: Path, *, contract_path: Path,
                            schema_path: Path, errors: list[str]) -> None:
    report = {
        "contract": str(contract_path).replace("\\", "/"),
        "schema": str(schema_path).replace("\\", "/"),
        "valid": not errors,
        "errors": errors,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
