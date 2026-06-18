#!/usr/bin/env python3
"""
配置数据校验器
读取 config_schema.json/config_schema.md 和对应的 CSV 文件，进行严格校验。
校验通过返回成功，失败则输出错误报告并熔断。
"""

import csv
import sys
from pathlib import Path
from tools.structured_md import data_to_text, read_structured_or_text


def load_schema(schema_path):
    return read_structured_or_text(Path(schema_path))


def validate_table(table_def, csv_path):
    """
    校验单个 CSV 文件是否符合表定义。
    返回 (passed: bool, errors: list, warnings: list)
    """
    errors = []
    warnings = []

    # 读取 CSV
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            columns = reader.fieldnames or []
    except Exception as e:
        return False, [f"无法读取 CSV 文件：{e}"], []

    # 检查列
    for col_def in table_def['columns']:
        col_name = col_def['name']
        # 必填列是否存在
        if col_def.get('required') and col_name not in columns:
            errors.append(f"缺少必填列：{col_name}")
        # 废弃列警告
        if col_def.get('deprecated') and col_name in columns:
            warnings.append(f"使用了已废弃的列：{col_name}（{col_def['deprecated']}）")

    # 逐行检查值
    unique_values = {}
    for row_idx, row in enumerate(rows, start=1):
        for col_def in table_def['columns']:
            col_name = col_def['name']
            if col_name not in row:
                continue
            value = row[col_name]
            # 类型校验
            expected_type = col_def.get('type', 'string')
            if value:
                if expected_type == 'int':
                    try:
                        int(value)
                    except ValueError:
                        errors.append(f"表 {table_def['name']} 行 {row_idx} 列 {col_name}：期望 int，实际 '{value}'")
                elif expected_type == 'float':
                    try:
                        float(value)
                    except ValueError:
                        errors.append(f"表 {table_def['name']} 行 {row_idx} 列 {col_name}：期望 float，实际 '{value}'")
                elif expected_type == 'bool':
                    if value.lower() not in ('true', 'false', '0', '1'):
                        errors.append(f"表 {table_def['name']} 行 {row_idx} 列 {col_name}：期望 bool，实际 '{value}'")
            # 必填检查
            if col_def.get('required') and not value:
                errors.append(f"表 {table_def['name']} 行 {row_idx} 列 {col_name}：必填，但为空")
            # 唯一性检查
            if col_def.get('unique'):
                if col_name not in unique_values:
                    unique_values[col_name] = {}
                if value in unique_values[col_name]:
                    errors.append(f"表 {table_def['name']} 行 {row_idx} 列 {col_name}：值 '{value}' 重复（唯一约束）")
                unique_values[col_name][value] = row_idx
            # 范围检查
            if expected_type in ('int', 'float') and value:
                val = int(value) if expected_type == 'int' else float(value)
                if 'min' in col_def and val < col_def['min']:
                    errors.append(f"表 {table_def['name']} 行 {row_idx} 列 {col_name}：{val} < min({col_def['min']})")
                if 'max' in col_def and val > col_def['max']:
                    errors.append(f"表 {table_def['name']} 行 {row_idx} 列 {col_name}：{val} > max({col_def['max']})")
    # 外键检查（稍后统一处理）
    return len(errors) == 0, errors, warnings


def validate_all(schema_path, tables_dir):
    """
    校验 schema 中定义的所有表。
    返回 (all_passed, report)
    """
    schema = load_schema(schema_path)
    tables = schema.get('tables', [])
    report = {
        'status': 'UNKNOWN',
        'tables': []
    }
    all_passed = True

    for table_def in tables:
        table_name = table_def['name']
        csv_file = Path(tables_dir) / f"{table_name}.csv"
        if not csv_file.exists():
            report['tables'].append({
                'name': table_name,
                'passed': False,
                'errors': [f"CSV 文件不存在：{csv_file}"],
                'warnings': []
            })
            all_passed = False
            continue
        passed, errors, warnings = validate_table(table_def, csv_file)
        report['tables'].append({
            'name': table_name,
            'passed': passed,
            'errors': errors,
            'warnings': warnings
        })
        if not passed:
            all_passed = False

    report['status'] = 'PASS' if all_passed else 'FAIL'
    return all_passed, report


if __name__ == "__main__":
    # 示例用法：python config_validator.py
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent
    schema_path = BASE_DIR / "source_artifacts" / "config_schema.json"
    if not schema_path.exists():
        schema_path = BASE_DIR / "source_artifacts" / "config_schema.md"
    tables_dir = BASE_DIR / "source_artifacts" / "config_tables"

    if not schema_path.exists():
        print("config_schema.json/config_schema.md 未找到，跳过校验。")
        sys.exit(0)

    passed, report = validate_all(schema_path, tables_dir)
    print(data_to_text(report))
    if not passed:
        print("❌ 配置校验失败，请修正 CSV 后重试。")
        sys.exit(1)
    else:
        print("✅ 配置校验通过。")
