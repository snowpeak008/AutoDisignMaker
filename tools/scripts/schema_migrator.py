#!/usr/bin/env python3
"""Schema migration helper for Markdown/JSON structured files."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

from core.utils.structured_md import read_structured_or_text, write_data


def load_data(path):
    return read_structured_or_text(Path(path))


def save_data(path, data):
    write_data(Path(path), data, title="Data")


def apply_migration(data, rules):
    for rule in rules:
        if rule["action"] == "wrap_to_object":
            field = rule["field"]
            new_field = rule["new_field"]
            structure = rule["structure"]
            if "unified_assets" in data:
                for asset in data["unified_assets"]:
                    if field in asset:
                        old_val = asset.pop(field)
                        new_val = {}
                        for key, value in structure.items():
                            if isinstance(value, str) and value.startswith("$"):
                                ref = value[1:]
                                new_val[key] = old_val if ref == "old_frames" else value
                            else:
                                new_val[key] = value
                        asset[new_field] = new_val
    return data


def main(input_path, schema_path, output_path):
    old_data = load_data(input_path)
    schema = load_data(schema_path)
    migration_rules = schema.get("schema_migration", {}).get("migration_rules", [])
    if not migration_rules:
        print("No migration rules found; copying data.")
        new_data = deepcopy(old_data)
    else:
        old_version = old_data.get("alignment_version", "2.0")
        applicable_rules = [r for r in migration_rules if r["from"] == old_version]
        if not applicable_rules:
            print(f"Warning: no migration rules from version {old_version}; output may be incompatible.")
            new_data = deepcopy(old_data)
        else:
            new_data = apply_migration(deepcopy(old_data), applicable_rules)
        new_data["alignment_version"] = schema.get("contract_version", "2.1")

    save_data(output_path, new_data)
    print(f"Migration complete: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.input, args.schema, args.output)
