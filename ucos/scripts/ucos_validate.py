from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


VALIDATION_TARGETS = [
    ("identity/profile.json", "working_memory.schema.json", False),
    ("knowledge/working/context.json", "working_memory.schema.json", True),
    ("knowledge/short_term/entries/*.json", "stm_entry.schema.json", True),
    ("knowledge/episodic/episodes/*.json", "episode.schema.json", True),
    ("knowledge/semantic/staging/*.json", "semantic_fact.schema.json", True),
    ("knowledge/patterns/entries/*.json", "pattern.schema.json", True),
    ("knowledge/failures/entries/*.json", "failure.schema.json", True),
    ("capability/skills/**/*.json", "skill.schema.json", True),
    ("execution/plans/*.json", "plan.schema.json", True),
    ("execution/goals/*.json", "goal.schema.json", True),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    report = validate(root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["checks"]:
            status = "OK" if item["ok"] else "FAIL"
            print(f"[{status}] {item['path']} ({item['schema']}) {item.get('error', '')}")
        print(f"[ucos_validate] ok={report['ok']} checked={len(report['checks'])}")
    return 0 if report["ok"] else 1


def validate(root: Path) -> dict[str, Any]:
    ucos_dir = root / "ucos"
    checks = []
    for pattern, schema_name, schema_check in VALIDATION_TARGETS:
        schema_path = ucos_dir / "schemas" / schema_name
        if not schema_path.exists():
            checks.append({"path": str(schema_path), "schema": schema_name, "ok": False, "error": "schema missing"})
            continue
        schema = _read_json(schema_path)
        validator = Draft202012Validator(schema)
        matches = sorted(ucos_dir.glob(pattern))
        if not matches and "*" not in pattern:
            checks.append({"path": str(ucos_dir / pattern), "schema": schema_name, "ok": False, "error": "target missing"})
            continue
        for target in matches:
            data = _read_json(target)
            if target.name == "profile.json":
                # profile has no dedicated schema in the V1.2 plan; check shape explicitly.
                required = {"schema_version", "identity_id", "role", "principles", "philosophy", "updated_at"}
                missing = sorted(required - set(data))
                checks.append({"path": str(target), "schema": "identity_profile", "ok": not missing, "error": f"missing {missing}" if missing else ""})
                continue
            if not schema_check:
                continue
            errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
            checks.append({"path": str(target), "schema": schema_name, "ok": not errors, "error": "; ".join(error.message for error in errors[:3])})
    semantic_schema_path = ucos_dir / "schemas" / "semantic_fact.schema.json"
    if semantic_schema_path.exists():
        semantic_validator = Draft202012Validator(_read_json(semantic_schema_path))
        for facts_file in sorted((ucos_dir / "knowledge" / "semantic" / "facts").glob("domain_*.json")):
            data = _read_json(facts_file)
            for index, fact in enumerate(data.get("facts", [])):
                errors = sorted(semantic_validator.iter_errors(fact), key=lambda err: list(err.path))
                checks.append(
                    {
                        "path": f"{facts_file}#facts[{index}]",
                        "schema": "semantic_fact.schema.json",
                        "ok": not errors,
                        "error": "; ".join(error.message for error in errors[:3]),
                    }
                )
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    raise SystemExit(main())
