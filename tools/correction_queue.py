#!/usr/bin/env python3
"""Correction queue helpers using strict Markdown."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_KV_RE = re.compile(r"^\s*-\s+\*\*(?P<key>[^*]+)\*\*:\s*(?P<value>.*)\s*$")
_ITEM_SPLIT_RE = re.compile(r"(?m)^###\s+Item:\s*")
_SECTION_PATTERN = r"(?ms)^####\s+{name}\s*\n(?P<body>.*?)(?=^####\s+|\Z)"
_SYS_ID_RE = re.compile(r"\bSYS_[A-Z][A-Z0-9_]*\b")
_ASSET_ID_RE = re.compile(r"\b(?:ILL|UI|VFX|ART|ENV|CHAR|PROP|FX)_[A-Z0-9_]+\b")


PROGREQ_TYPES = {
    "missing_contract",
    "event_missing_contract",
    "contract_not_bound",
    "role_mismatch",
    "method_mismatch",
    "subscription_mismatch",
    "signature_mismatch",
    "dangling_reference",
    "missing_interface",
    "wrong_assignment",
}

DESIGN_TYPES = {
    "undefined_entity",
    "missing_field",
    "unresolved_dependency",
    "resource_location_mismatch",
    "item_mismatch",
    "clarify_design",
}

ARTREQ_TYPES = {
    "category_gap",
    "missing_category",
    "missing_asset",
    "missing_art_asset",
    "missing_art_category",
    "spec_quality",
    "incomplete_spec",
    "missing_art_field",
    "vague_description",
    "style_drift",
    "drift_exceeded",
    "fix_art_req",
    "clarify_art_requirement",
}

HUMAN_GAP_TYPES = {
    "authority_conflict",
    "multi_authority",
}


@dataclass
class CorrectionItem:
    """One correction selected by a review gate."""

    item_id: str
    conflict_type: str
    severity: str
    detail: str
    source_system: str = ""
    target_system: str = ""
    correction_type: str = ""
    entities: list[str] = field(default_factory=list)
    suggested_action: str = ""
    selected: bool = True
    target_stage: str = ""
    affected_systems: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)


@dataclass
class CorrectionQueue:
    """A correction queue produced by a review step."""

    generated_at: str = ""
    source_review: str = ""
    source_review_protocol: str = ""
    source_review_report: str = ""
    reviewed_contract: str = ""
    rerun_plan: dict[str, Any] = field(default_factory=dict)
    blocked_items: list[dict[str, Any]] = field(default_factory=list)
    items: list[CorrectionItem] = field(default_factory=list)


def _snake(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _stringify(value).lower()
    if text in {"false", "0", "no", "n", "off"}:
        return False
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    return default


def _split_csv(value: Any) -> list[str]:
    if isinstance(value, list):
        values = value
    else:
        values = re.split(r"[,;\n]", _stringify(value))
    return [str(v).strip() for v in values if str(v).strip() and str(v).strip() != "-"]


def infer_affected_systems(*values: Any) -> list[str]:
    found: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            text = " ".join(_stringify(v) for v in value)
        else:
            text = _stringify(value)
        found.update(_SYS_ID_RE.findall(text))
    return sorted(found)


def infer_affected_assets(*values: Any) -> list[str]:
    found: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            text = " ".join(_stringify(v) for v in value)
        else:
            text = _stringify(value)
        found.update(_ASSET_ID_RE.findall(text))
    return sorted(found)


def infer_target_stage(conflict_type: str, correction_type: str = "", detail: str = "",
                       suggested_action: str = "") -> str:
    ct = _stringify(conflict_type).lower()
    corr = _stringify(correction_type).lower()
    text = " ".join([ct, corr, _stringify(detail), _stringify(suggested_action)])

    if ct in HUMAN_GAP_TYPES or corr in HUMAN_GAP_TYPES:
        return "human_gap"
    if ct in PROGREQ_TYPES or corr in PROGREQ_TYPES:
        return "progreq"
    if "CT_" in text or "EVT_" in text or "contract" in text.lower():
        return "progreq"
    if ct in ARTREQ_TYPES or corr in ARTREQ_TYPES:
        return "artreq"
    lowered = text.lower()
    if any(marker in lowered for marker in ("asset", "illustration", "vfx", "ui", "visualdna", "artreq")):
        return "artreq"
    if ct in DESIGN_TYPES or corr in DESIGN_TYPES:
        return "design"
    return "unmapped"


def infer_affected_files(target_stage: str, conflict_type: str,
                         correction_type: str = "", *hints: Any) -> list[str]:
    stage = _stringify(target_stage).lower()
    ct = _stringify(conflict_type).lower()
    corr = _stringify(correction_type).lower()
    kind = corr or ct
    hint_text = " ".join(_stringify(hint) for hint in hints).lower()

    if stage == "design":
        return ["frozen_game_design.md"]
    if stage == "artreq":
        text = " ".join([kind, ct, corr, hint_text]).lower()
        files: list[str] = []
        if any(marker in text for marker in ("illustration", "ill_", "原画")):
            files.append("原画需求.md")
        if any(marker in text for marker in ("ui", "hud", "menu")):
            files.append("UI需求.md")
        if any(marker in text for marker in ("vfx", "fx_", "effect", "特效")):
            files.append("特效需求.md")
        if "drift" in text or "style" in text:
            files.append("drift_analysis.md")
        return files or ["原画需求.md", "UI需求.md", "特效需求.md"]
    if stage != "progreq":
        return []
    if kind in {"missing_contract", "event_missing_contract", "method_mismatch"}:
        return ["contracts.md", "events.md"]
    if kind in {"role_mismatch", "contract_not_bound", "signature_mismatch", "missing_interface"}:
        return ["contracts.md", "systems.md"]
    if kind in {"undefined_entity", "missing_field"}:
        return ["systems.md", "entities.md"]
    if kind in {"authority_conflict", "multi_authority"}:
        return ["authority.md", "entities.md"]
    return ["contracts.md", "systems.md", "events.md"]


def complete_item_routing(item: CorrectionItem) -> CorrectionItem:
    if not item.target_stage:
        item.target_stage = infer_target_stage(
            item.conflict_type,
            item.correction_type,
            item.detail,
            item.suggested_action,
        )
    if not item.affected_systems:
        systems = infer_affected_systems(
            item.source_system,
            item.target_system,
            item.entities,
            item.detail,
            item.suggested_action,
        )
        item.affected_systems = systems or infer_affected_assets(
            item.source_system,
            item.target_system,
            item.entities,
            item.detail,
            item.suggested_action,
        )
    if not item.affected_files:
        item.affected_files = infer_affected_files(
            item.target_stage,
            item.conflict_type,
            item.correction_type,
            item.detail,
            item.suggested_action,
            item.entities,
            item.affected_systems,
        )
    return item


def classify_conflicts(conflicts: list, completeness: dict,
                       consistency: dict) -> tuple[list[CorrectionItem], list[dict]]:
    """Classify review findings into automatic corrections and design gaps."""
    correctable: list[CorrectionItem] = []
    design_gaps: list[dict] = []
    idx = 0

    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue

        conflict_type = _stringify(conflict.get("conflict_type", "unknown")).lower()
        severity = _stringify(conflict.get("severity", "major")).lower()
        detail = _stringify(conflict.get("detail", conflict.get("original_conflict", "")))

        if conflict_type in HUMAN_GAP_TYPES:
            design_gaps.append(conflict)
            continue

        if conflict_type in PROGREQ_TYPES or conflict_type in DESIGN_TYPES:
            idx += 1
            item = CorrectionItem(
                item_id=f"CORR_{idx:03d}",
                conflict_type=conflict_type,
                severity=severity,
                detail=detail,
                source_system=_stringify(conflict.get("entity_a", conflict.get("source_system", ""))),
                target_system=_stringify(conflict.get("entity_b", conflict.get("target_system", ""))),
                correction_type=_map_correction_type(conflict_type),
                entities=[
                    _stringify(conflict.get("entity_a", "")),
                    _stringify(conflict.get("entity_b", "")),
                ],
                suggested_action=_generate_suggestion(conflict_type, conflict),
            )
            correctable.append(complete_item_routing(item))
        else:
            design_gaps.append(conflict)

    return correctable, design_gaps


def _map_correction_type(conflict_type: str) -> str:
    mapping = {
        "missing_interface": "add_interface",
        "undefined_entity": "add_entity",
        "wrong_assignment": "fix_interface_assignment",
        "missing_field": "add_field",
        "signature_mismatch": "fix_interface_signature",
        "unresolved_dependency": "clarify_dependency",
        "resource_location_mismatch": "clarify_data_flow",
        "item_mismatch": "clarify_item_definition",
        "contract_not_bound": "bind_contract",
        "authority_conflict": "resolve_authority",
        "event_missing_contract": "add_contract_for_event",
        "missing_contract": "add_contract",
        "role_mismatch": "fix_contract_role",
        "method_mismatch": "fix_contract_method",
        "subscription_mismatch": "fix_event_subscription",
    }
    return mapping.get(conflict_type, "clarify_design")


def _generate_suggestion(conflict_type: str, item: dict) -> str:
    detail = _stringify(item.get("detail", item.get("original_conflict", "")))
    if conflict_type == "missing_interface":
        return f"Add a cross-system interface for: {detail[:120]}"
    if conflict_type == "undefined_entity":
        return f"Define the missing entity: {detail[:120]}"
    if conflict_type == "wrong_assignment":
        return f"Move the interface to the correct owning system: {detail[:120]}"
    if conflict_type == "unresolved_dependency":
        return f"Clarify dependency or create the referenced feature: {detail[:120]}"
    if conflict_type == "contract_not_bound":
        return f"Bind the contract to its provider or consumer system: {detail[:120]}"
    if conflict_type == "event_missing_contract":
        return f"Add an event contract for: {detail[:120]}"
    if conflict_type == "missing_contract":
        return f"Add the missing contract to the contract registry: {detail[:120]}"
    if conflict_type == "role_mismatch":
        return f"Fix the provider/consumer binding role: {detail[:120]}"
    if conflict_type == "method_mismatch":
        return f"Fix the contract method or split command/query/event contracts: {detail[:120]}"
    if conflict_type == "subscription_mismatch":
        return f"Fix event subscribers to match contract targets: {detail[:120]}"
    return f"Clarify design intent: {detail[:120]}"


def _parse_meta(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    in_meta = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_meta = line.strip().lower() == "## meta"
            continue
        if not in_meta:
            continue
        match = _KV_RE.match(line)
        if match:
            meta[_snake(match.group("key"))] = match.group("value").strip()
    return meta


def _extract_named_section(body: str, name: str) -> str:
    match = re.compile(_SECTION_PATTERN.format(name=re.escape(name))).search(body)
    return match.group("body").strip() if match else ""


def _parse_item_block(item_id: str, body: str) -> CorrectionItem:
    values: dict[str, str] = {}
    for line in body.splitlines():
        match = _KV_RE.match(line)
        if match:
            values[_snake(match.group("key"))] = match.group("value").strip()

    detail = _extract_named_section(body, "Detail") or values.get("detail", "")
    suggested = _extract_named_section(body, "Suggested Action") or values.get("suggested_action", "")

    item = CorrectionItem(
        item_id=item_id.strip(),
        conflict_type=values.get("conflict_type", "unknown"),
        severity=values.get("severity", "major"),
        detail=detail,
        source_system=values.get("source_system", ""),
        target_system=values.get("target_system", ""),
        correction_type=values.get("correction_type", ""),
        entities=_split_csv(values.get("entities", "")),
        suggested_action=suggested,
        selected=values.get("selected", "true").strip().lower() not in {"false", "0", "no"},
        target_stage=values.get("target_stage", ""),
        affected_systems=_split_csv(values.get("affected_systems", "")),
        affected_files=_split_csv(values.get("affected_files", "")),
    )
    return complete_item_routing(item)


def _load_markdown_queue(raw: str) -> CorrectionQueue:
    parts = _ITEM_SPLIT_RE.split(raw)
    meta = _parse_meta(parts[0] if parts else raw)
    queue = CorrectionQueue(
        generated_at=meta.get("generated_at", ""),
        source_review=meta.get("source_review", ""),
        source_review_protocol=meta.get("source_review_protocol", ""),
        source_review_report=meta.get("source_review_report", ""),
        reviewed_contract=meta.get("reviewed_contract", ""),
    )

    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        item_id = lines[0].strip()
        body = "\n".join(lines[1:])
        queue.items.append(_parse_item_block(item_id, body))

    return queue


def load_queue(path: Path) -> CorrectionQueue:
    """Read a correction queue from strict Markdown or JSON."""
    if not path.exists():
        return CorrectionQueue()
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8")) or {}
        queue = CorrectionQueue(
            generated_at=_stringify(raw.get("generated_at", "")),
            source_review=_stringify(raw.get("source_review", "")),
            source_review_protocol=_stringify(raw.get("source_review_protocol", "")),
            source_review_report=_stringify(raw.get("source_review_report", "")),
            reviewed_contract=_stringify(raw.get("reviewed_contract", "")),
            rerun_plan=raw.get("rerun_plan", {}) if isinstance(raw.get("rerun_plan"), dict) else {},
            blocked_items=raw.get("blocked_items", []) if isinstance(raw.get("blocked_items"), list) else [],
        )
        for index, item in enumerate(raw.get("corrections", []) or [], 1):
            if not isinstance(item, dict):
                continue
            correction = CorrectionItem(
                item_id=_stringify(item.get("correction_id") or item.get("item_id") or f"CORR_{index:03d}"),
                conflict_type=_stringify(item.get("conflict_type") or item.get("correction_type") or "unknown"),
                severity=_stringify(item.get("severity") or "major"),
                detail=_stringify(item.get("detail") or item.get("required_change") or ""),
                source_system=_stringify(item.get("source_system", "")),
                target_system=_stringify(item.get("target_system", "")),
                correction_type=_stringify(item.get("correction_type", "")),
                entities=_split_csv(item.get("entities", [])),
                suggested_action=_stringify(item.get("suggested_action") or item.get("required_change") or ""),
                selected=_to_bool(item.get("selected", True)),
                target_stage=_stringify(item.get("target_stage", "")),
                affected_systems=_split_csv(item.get("affected_systems") or item.get("affected_ids") or []),
                affected_files=_split_csv(item.get("affected_files", [])),
            )
            queue.items.append(complete_item_routing(correction))
        return queue
    raw = path.read_text(encoding="utf-8")
    return _load_markdown_queue(raw)


def _write_csv(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


def save_queue(queue: CorrectionQueue, path: Path):
    """Save a correction queue as strict Markdown."""
    lines = [
        "# Correction Queue",
        "",
        "## Meta",
        f"- **generated_at**: {queue.generated_at}",
        f"- **source_review**: {queue.source_review}",
        f"- **source_review_protocol**: {queue.source_review_protocol or '-'}",
        f"- **source_review_report**: {queue.source_review_report or '-'}",
        f"- **reviewed_contract**: {queue.reviewed_contract or '-'}",
        "",
        "## Items",
        "",
    ]

    for raw_item in queue.items:
        item = complete_item_routing(raw_item)
        lines.extend([
            f"### Item: {item.item_id}",
            f"- **conflict_type**: {item.conflict_type}",
            f"- **severity**: {item.severity}",
            f"- **target_stage**: {item.target_stage}",
            f"- **source_system**: {item.source_system or '-'}",
            f"- **target_system**: {item.target_system or '-'}",
            f"- **correction_type**: {item.correction_type}",
            f"- **affected_systems**: {_write_csv(item.affected_systems)}",
            f"- **affected_files**: {_write_csv(item.affected_files)}",
            f"- **entities**: {_write_csv(item.entities)}",
            f"- **selected**: {'true' if item.selected else 'false'}",
            "",
            "#### Detail",
            item.detail or "-",
            "",
            "#### Suggested Action",
            item.suggested_action or "-",
            "",
        ])

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def queue_to_dict(queue: CorrectionQueue) -> dict[str, Any]:
    corrections = []
    for raw_item in queue.items:
        item = complete_item_routing(raw_item)
        affected_ids = list(dict.fromkeys((item.affected_systems or []) + (item.entities or [])))
        corrections.append({
            "correction_id": item.item_id,
            "selected": item.selected,
            "target_stage": item.target_stage,
            "conflict_type": item.conflict_type,
            "severity": item.severity,
            "correction_type": item.correction_type,
            "source_finding_id": "",
            "affected_ids": affected_ids,
            "affected_systems": item.affected_systems,
            "affected_files": item.affected_files,
            "entities": item.entities,
            "source_system": item.source_system,
            "target_system": item.target_system,
            "required_change": item.suggested_action or item.detail,
            "forbidden_change": "",
            "detail": item.detail,
        })
    return {
        "schema_version": "2.0",
        "generated_at": queue.generated_at,
        "source_review_protocol": queue.source_review_protocol,
        "source_review": queue.source_review,
        "source_review_report": queue.source_review_report,
        "reviewed_contract": queue.reviewed_contract,
        "corrections": corrections,
        "rerun_plan": queue.rerun_plan or {
            "required_stages": [],
            "commands": [],
            "reason": "",
        },
        "blocked_items": queue.blocked_items,
    }


def save_queue_json(queue: CorrectionQueue, path: Path):
    path.write_text(
        json.dumps(queue_to_dict(queue), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_known_gaps(gaps: list[dict], path: Path):
    """Write known design gaps as Markdown."""
    lines = [
        "# Known Design Gaps",
        "",
        f"> generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
    ]
    if not gaps:
        lines.append("_No known design gaps._")
    else:
        for i, gap in enumerate(gaps, 1):
            if isinstance(gap, dict):
                lines.append(f"## Gap {i}: {gap.get('conflict_type', 'unknown')}")
                lines.append(f"- **detail**: {gap.get('detail', gap.get('description', 'N/A'))}")
                lines.append(f"- **severity**: {gap.get('severity', 'N/A')}")
                lines.append(f"- **related**: {gap.get('entity_a', '')} / {gap.get('entity_b', '')}")
                lines.append("")
            else:
                lines.append(f"## Gap {i}")
                lines.append(str(gap))
                lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
