#!/usr/bin/env python3
"""Lint CONTEXT.md grouping and ADR backlink coverage."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = [
    "Core Pipeline And Save Boundaries",
    "Art Governance And Asset Contracts",
    "Execution Objects And GUI Gates",
    "Stage Sequence And Runtime Integration",
]


def lint_context(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections = {section: 0 for section in REQUIRED_SECTIONS}
    current_section = ""
    terms = 0
    terms_with_adr = 0
    last_term_has_adr = False
    errors: list[str] = []

    for line in lines:
        if line.startswith("## "):
            current_section = line[3:].strip()
        term_match = re.match(r"^\*\*[^*]+\*\*:", line)
        if term_match:
            if terms and not last_term_has_adr:
                errors.append("term missing _ADR_ before next term")
            terms += 1
            last_term_has_adr = False
            if current_section in sections:
                sections[current_section] += 1
            else:
                errors.append(f"term outside required sections: {line}")
        elif line.startswith("_ADR_:"):
            if terms:
                terms_with_adr += 1
                last_term_has_adr = True

    if terms and not last_term_has_adr:
        errors.append("last term missing _ADR_")
    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"missing section: {section}")
        if sections[section] == 0:
            errors.append(f"section has no terms: {section}")

    coverage = (terms_with_adr / terms) if terms else 0.0
    if coverage < 0.8:
        errors.append(f"ADR coverage below threshold: {coverage:.3f}")
    return {
        "path": str(path),
        "valid": not errors,
        "terms": terms,
        "terms_with_adr": terms_with_adr,
        "adr_coverage": round(coverage, 3),
        "sections": sections,
        "errors": errors,
    }


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2] / "CONTEXT.md"
    result = lint_context(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
