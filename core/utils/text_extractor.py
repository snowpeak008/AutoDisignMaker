#!/usr/bin/env python3
"""文本提取工具 — 从 ui_graph 和配置表提取用户可见文本，生成翻译表模板。"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from core.utils.structured_md import read_structured_or_text, write_data


def extract_from_ui_graph(ui_graph_path: str) -> dict[str, str]:
    texts: dict[str, str] = {}
    if not os.path.exists(ui_graph_path):
        return texts
    graph = read_structured_or_text(Path(ui_graph_path))
    for panel in graph.get("registry", {}).get("panels", []):
        pid = panel["id"]
        texts[f"{pid}.title"] = pid.split(".")[-1]
    return texts


def extract_from_config_schema(schema_path: str) -> dict[str, str]:
    texts: dict[str, str] = {}
    if not os.path.exists(schema_path):
        return texts
    schema = read_structured_or_text(Path(schema_path))
    for table in schema.get("tables", []):
        for col in table.get("columns", []):
            if col.get("type") == "string" and "name" in col:
                texts[f"{table['name']}.{col['name']}"] = ""
    return texts


def generate_strings_file(texts: dict, output_path: str, language: str = "zh-CN") -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    write_data(Path(output_path), texts, title=f"Translation Strings ({language})")


def run_text_extraction(plans_dir: str, output_dir: str) -> str | None:
    ui_graph = os.path.join(plans_dir, "ui_graph.json")
    if not os.path.exists(ui_graph):
        ui_graph = os.path.join(plans_dir, "ui_graph.md")
    config_schema = os.path.join(plans_dir, "config_schema.json")
    if not os.path.exists(config_schema):
        config_schema = os.path.join(plans_dir, "config_schema.md")
    texts: dict[str, str] = {}
    texts.update(extract_from_ui_graph(ui_graph))
    texts.update(extract_from_config_schema(config_schema))
    if not texts:
        return None
    lang_file = os.path.join(output_dir, "zh-CN.md")
    generate_strings_file(texts, lang_file)
    return lang_file
