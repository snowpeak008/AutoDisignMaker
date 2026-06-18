#!/usr/bin/env python3
"""
配置数据编译器
将校验通过的 CSV 编译为紧凑 JSON（或二进制），并生成强类型数据类。
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from tools.structured_md import read_structured_or_text


def load_schema(schema_path):
    return read_structured_or_text(Path(schema_path))


def compile_table(table_def, csv_path, output_dir, lang='csharp'):
    """
    编译单张表，生成数据文件和代码文件。
    返回 (data_file, code_file) 路径。
    """
    table_name = table_def['name']
    # 读取 CSV
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # 生成紧凑 JSON（实际可改为二进制）
    data = []
    for row in rows:
        item = {}
        for col_def in table_def['columns']:
            col_name = col_def['name']
            value = row.get(col_name, '')
            col_type = col_def.get('type', 'string')
            if col_type == 'int':
                value = int(value) if value else 0
            elif col_type == 'float':
                value = float(value) if value else 0.0
            elif col_type == 'bool':
                value = value.lower() in ('true', '1')
            item[col_name] = value
        data.append(item)

    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"{table_name}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 生成强类型数据类（以 C# 为例）
    code_path = os.path.join(output_dir, f"{table_name}Data.cs")
    class_name = table_name.capitalize() + "Data"
    code = f"// 自动生成，请勿手动修改\n// 生成时间：{datetime.now()}\n\n"
    code += "using System;\nusing System.Collections.Generic;\n\n"
    code += "[Serializable]\n"
    code += f"public struct {class_name}\n{{\n"
    for col_def in table_def['columns']:
        col_name = col_def['name']
        col_type = col_def.get('type', 'string')
        if col_type == 'int':
            cs_type = 'int'
        elif col_type == 'float':
            cs_type = 'float'
        elif col_type == 'bool':
            cs_type = 'bool'
        else:
            cs_type = 'string'
        code += f"    public {cs_type} {col_name};\n"
    code += "}\n"

    with open(code_path, 'w', encoding='utf-8') as f:
        f.write(code)

    return json_path, code_path


def compile_all(schema_path, tables_dir, output_dir, lang='csharp'):
    schema = load_schema(schema_path)
    tables = schema.get('tables', [])
    compiled = []
    for table_def in tables:
        csv_file = Path(tables_dir) / f"{table_def['name']}.csv"
        if csv_file.exists():
            data_file, code_file = compile_table(table_def, csv_file, output_dir, lang)
            compiled.append({
                'table': table_def['name'],
                'data_file': data_file,
                'code_file': code_file
            })
    return compiled


if __name__ == "__main__":
    # 示例：python config_compiler.py
    BASE_DIR = Path(__file__).parent.parent
    schema_path = BASE_DIR / "source_artifacts" / "config_schema.json"
    if not schema_path.exists():
        schema_path = BASE_DIR / "source_artifacts" / "config_schema.md"
    tables_dir = BASE_DIR / "source_artifacts" / "config_tables"
    output_dir = BASE_DIR / "outputs" / "runtime" / "Configs"

    if schema_path.exists():
        compiled = compile_all(schema_path, tables_dir, output_dir)
        print(f"编译完成，生成 {len(compiled)} 个数据文件。")
    else:
        print("config_schema.json/config_schema.md 未找到，跳过编译。")
