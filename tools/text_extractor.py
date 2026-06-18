#!/usr/bin/env python3
"""
文本提取工具
扫描 ui_graph.json/ui_graph.md 和配置表，提取所有用户可见文本，生成翻译表模板。
"""

import os
from datetime import datetime
from pathlib import Path
from tools.structured_md import read_structured_or_text, write_data


def extract_from_ui_graph(ui_graph_path):
    """
    从 UI 状态图中提取文本 key。
    假设 ui_graph 中包含一个 texts 字段或从状态描述中提取。
    """
    texts = {}
    if not os.path.exists(ui_graph_path):
        return texts

    graph = read_structured_or_text(Path(ui_graph_path))

    # 从 registry.panels 提取面板名称作为文本 key
    panels = graph.get('registry', {}).get('panels', [])
    for panel in panels:
        pid = panel['id']
        # 为每个面板生成默认文本 key
        texts[f"{pid}.title"] = pid.split('.')[-1]

    return texts


def extract_from_config_schema(schema_path):
    """
    从配置表 schema 中提取文本字段。
    """
    texts = {}
    if not os.path.exists(schema_path):
        return texts

    schema = read_structured_or_text(Path(schema_path))

    for table in schema.get('tables', []):
        for col in table.get('columns', []):
            if col.get('type') == 'string' and 'name' in col:
                # 假设名称字段需要翻译
                key = f"{table['name']}.{col['name']}"
                texts[key] = ""

    return texts


def generate_strings_file(texts, output_path, language='zh-CN'):
    """
    生成指定语言的翻译文件。
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    write_data(Path(output_path), texts, title=f"Translation Strings ({language})")


def run_text_extraction(plans_dir, output_dir):
    """
    执行文本提取流水线：
    1. 从 ui_graph.json/ui_graph.md 提取
    2. 从 config_schema.json/config_schema.md 提取
    3. 生成默认语言文件
    """
    ui_graph = os.path.join(plans_dir, "ui_graph.json")
    if not os.path.exists(ui_graph):
        ui_graph = os.path.join(plans_dir, "ui_graph.md")
    config_schema = os.path.join(plans_dir, "config_schema.json")
    if not os.path.exists(config_schema):
        config_schema = os.path.join(plans_dir, "config_schema.md")

    texts = {}
    texts.update(extract_from_ui_graph(ui_graph))
    texts.update(extract_from_config_schema(config_schema))

    if not texts:
        return None

    # 生成默认语言文件
    default_lang = "zh-CN"
    lang_file = os.path.join(output_dir, default_lang + ".md")
    generate_strings_file(texts, lang_file, default_lang)

    return lang_file
