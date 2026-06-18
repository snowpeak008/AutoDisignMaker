#!/usr/bin/env python3
"""Markdown parser for LLM-produced structured output.

Convention:
  # Title           -> document title stored as _title
  ## Section        -> top-level key
  ### Item: name    -> list entry in parent section
  ### SubSection    -> nested dict in parent section
  - **key**: value  -> key-value pair
  - plain text      -> list item
  | col1 | col2 |   -> table rows as list of dicts
  ```json ... ```   -> JSON fallback
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from tools import yaml_compat as yaml

from tools.output_validator import (
    AgentOutputValidationError,
    _validate_text_content,
    extract_fenced_text,
)


def normalize_section_keys(parsed: dict) -> dict:
    result = {}
    for key, value in parsed.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            result.update(value)
        else:
            flat_key = key.lower().replace(" ", "_").replace("-", "_")
            result[flat_key] = value
    return result


_ITEM_RE = re.compile(r"^###\s+Item:\s*(.+)")
_KV_RE = re.compile(r"^(\s*)-\s+\*\*([^*]+)\*\*:\s*(.*)")
_LIST_RE = re.compile(r"^(\s*)-\s+(.*)")
_H1_RE = re.compile(r"^#\s+")
_H2_RE = re.compile(r"^##\s+")
_H3_RE = re.compile(r"^###\s+")
_TABLE_SEP_RE = re.compile(r"^[-:\s|]+$")
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)
_YAML_FENCE_RE = re.compile(r"```(?:yaml|yml)\s*\n(.*?)\n```", re.DOTALL)


class MarkdownParser:
    def __init__(self, text: str, *, output_name: str = "Agent output"):
        self.text = text
        self.output_name = output_name

    def parse(self) -> dict:
        result: dict[str, Any] = {}
        section_name: str | None = None
        section_kv: dict[str, Any] = {}
        section_list: list[str] = []
        section_has_kv = False
        section_has_list = False
        subsection_list: list[dict] = []
        current_item: dict | None = None
        in_table = False
        table_headers: list[str] = []
        table_rows: list[dict] = []

        def flush_section():
            nonlocal section_kv, section_list, section_has_kv, section_has_list
            nonlocal table_headers, table_rows, in_table, subsection_list, current_item
            if section_name is None:
                return
            if current_item is not None:
                subsection_list.append(current_item)
                current_item = None
            if subsection_list:
                result[section_name] = subsection_list
            elif in_table and table_headers and table_rows:
                result[section_name] = table_rows
            elif section_has_kv and section_has_list:
                section_kv["_items"] = section_list
                result[section_name] = section_kv
            elif section_has_kv:
                result[section_name] = section_kv
            elif section_has_list:
                result[section_name] = section_list
            else:
                result[section_name] = {}
            section_kv = {}
            section_list = []
            section_has_kv = False
            section_has_list = False
            subsection_list = []
            current_item = None
            in_table = False
            table_headers = []
            table_rows = []

        for line in self.text.split("\n"):
            stripped = line.strip()
            if not stripped:
                in_table = False
                continue

            if _H1_RE.match(line) and not _H2_RE.match(line):
                result["_title"] = line.split("# ", 1)[1].strip()
                continue

            if _H2_RE.match(line) and not _H3_RE.match(line):
                flush_section()
                section_name = line.split("## ", 1)[1].strip()
                continue

            if _H3_RE.match(line):
                in_table = False
                if current_item is not None:
                    subsection_list.append(current_item)
                    current_item = None
                heading = line.split("### ", 1)[1].strip()
                match = _ITEM_RE.match(line)
                if match:
                    current_item = {"_name": match.group(1).strip()}
                else:
                    section_kv[heading] = {}
                    current_item = section_kv[heading]
                continue

            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped[1:-1].split("|")]
                if all(_TABLE_SEP_RE.match(c) for c in cells):
                    in_table = True
                    continue
                if in_table and table_headers:
                    row = {}
                    for i, cell in enumerate(cells):
                        if i < len(table_headers):
                            row[table_headers[i]] = cell
                    table_rows.append(row)
                elif not in_table:
                    table_headers = cells
                    in_table = True
                continue

            if in_table and not stripped.startswith("|"):
                in_table = False

            match = _KV_RE.match(line)
            if match:
                key = match.group(2).strip()
                value = match.group(3).strip()
                if current_item is not None:
                    current_item[key] = value
                else:
                    section_kv[key] = value
                    section_has_kv = True
                continue

            match = _LIST_RE.match(line)
            if match:
                value = match.group(2).strip()
                if current_item is not None:
                    current_item.setdefault("_items", []).append(value)
                else:
                    section_list.append(value)
                    section_has_list = True
                continue

        flush_section()
        return result

    def parse_sections(self) -> dict[str, Any]:
        return self.parse()

    def parse_table(self, section_name: str) -> list[dict]:
        section = self.parse().get(section_name, [])
        return section if isinstance(section, list) else []

    def parse_list(self, section_name: str) -> list[Any]:
        section = self.parse().get(section_name, [])
        if isinstance(section, list):
            return section
        if isinstance(section, dict):
            return section.get("_items", [])
        return []

    def extract_json_block(self) -> str | None:
        match = _JSON_FENCE_RE.search(self.text)
        return match.group(1).strip() if match else None

    def extract_yaml_block(self) -> str | None:
        match = _YAML_FENCE_RE.search(self.text)
        return match.group(1).strip() if match else None


def parse_md_output(
    text: str,
    *,
    output_name: str = "Agent output",
    required_keys: Iterable[str] | None = None,
    allowed_types: tuple[type, ...] = (dict, list),
    last_block: bool = False,
    require_mapping: bool = False,
    flatten_sections: bool = False,
) -> Any:
    if require_mapping:
        allowed_types = (dict,)

    _validate_text_content(text, output_name)

    parsed: Any = {}
    if last_block:
        json_text = extract_fenced_text(text, lang="json", last_block=True, output_name=output_name)
        if json_text and json_text.strip() != str(text).strip():
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError:
                parsed = {}
        if parsed:
            if allowed_types and not isinstance(parsed, allowed_types):
                expected = ", ".join(t.__name__ for t in allowed_types)
                raise AgentOutputValidationError(
                    f"{output_name} must parse as {expected}, got {type(parsed).__name__}."
                )
            if required_keys:
                if not isinstance(parsed, dict):
                    raise AgentOutputValidationError(f"{output_name} must be an object with keys {list(required_keys)}.")
                missing = [key for key in required_keys if key not in parsed]
                if missing:
                    raise AgentOutputValidationError(f"{output_name} missing required fields: {', '.join(missing)}")
            return parsed

    parser = MarkdownParser(text, output_name=output_name)
    parsed = parser.parse()
    parsed.pop("_title", None)

    if flatten_sections and isinstance(parsed, dict):
        parsed = normalize_section_keys(parsed)

    if not parsed:
        try:
            parsed = json.loads(str(text).strip())
        except json.JSONDecodeError:
            pass

    if not parsed:
        json_text = parser.extract_json_block()
        if json_text:
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError:
                pass

    if not parsed:
        yaml_text = parser.extract_yaml_block()
        if yaml_text:
            try:
                parsed = yaml.safe_load(yaml_text)
            except yaml.YAMLError:
                pass

    if not parsed:
        json_text = extract_fenced_text(text, lang="json", last_block=last_block, output_name=output_name)
        if json_text and json_text.strip() != text.strip():
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError:
                pass

    if not parsed:
        try:
            raw_yaml = yaml.safe_load(str(text).strip())
            if isinstance(raw_yaml, allowed_types or (dict, list)):
                parsed = raw_yaml
        except yaml.YAMLError:
            pass

    if not parsed:
        return {"raw": text}

    if allowed_types and not isinstance(parsed, allowed_types):
        expected = ", ".join(t.__name__ for t in allowed_types)
        raise AgentOutputValidationError(
            f"{output_name} must parse as {expected}, got {type(parsed).__name__}."
        )

    if required_keys:
        if not isinstance(parsed, dict):
            raise AgentOutputValidationError(f"{output_name} must be an object with keys {list(required_keys)}.")
        missing = [key for key in required_keys if key not in parsed]
        if missing:
            raise AgentOutputValidationError(f"{output_name} missing required fields: {', '.join(missing)}")

    return parsed
