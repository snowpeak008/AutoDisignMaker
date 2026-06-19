"""Source package discovery and matching."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from core.io import read_json
from core.paths import SOURCE_ARTIFACTS_DIR
from core.source.groups import SOURCE_MARKERS, SOURCE_TYPES, SourceGroup


def _norm_source_id(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _source_ids_from_patterns(patterns: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for pattern in patterns:
        for source_type in SOURCE_TYPES:
            if f"_{source_type}_" in pattern or pattern.startswith(f"{source_type}_"):
                result.append(source_type)
    return tuple(dict.fromkeys(result))


def _parse_version(path: Path) -> int:
    match = re.search(r"_v(\d+)$", path.name)
    return int(match.group(1)) if match else 0


def _parse_date(path: Path) -> str:
    match = re.search(r"_(\d{8})(?:_|$)", path.name)
    return match.group(1) if match else ""


def source_package_metadata(path: Path) -> dict[str, Any]:
    manifest = read_json(path / "package_manifest.json", {})
    if isinstance(manifest, dict) and manifest:
        return manifest
    submission = read_json(path / "operator_submission.json", {})
    return submission if isinstance(submission, dict) else {}


def infer_source_ids(path: Path) -> tuple[str, ...]:
    ids: list[str] = []
    metadata = source_package_metadata(path)
    for key in ("source_id", "package_id", "package_type", "package_type_id", "prefix"):
        value = metadata.get(key)
        if value:
            ids.append(str(value))
    if metadata.get("source_ids"):
        raw_ids = metadata.get("source_ids")
        if isinstance(raw_ids, list):
            ids.extend(str(item) for item in raw_ids)
    for marker, source_type in SOURCE_MARKERS.items():
        if (path / marker).exists():
            ids.append(source_type)
    for source_type in SOURCE_TYPES:
        if f"_{source_type}_" in path.name or path.name.startswith(f"{source_type}_"):
            ids.append(source_type)
    return tuple(dict.fromkeys(ids))


def source_matches_ids(path: Path, expected_ids: Iterable[str]) -> bool:
    expected = {_norm_source_id(item) for item in expected_ids if item}
    if not expected:
        return False
    actual = {_norm_source_id(item) for item in infer_source_ids(path)}
    return bool(expected & actual)


def _source_sort_key(path: Path) -> tuple[str, int, float, str]:
    metadata = source_package_metadata(path)
    created_at = str(
        metadata.get("created_at") or metadata.get("timestamp") or _parse_date(path)
    )
    version = metadata.get("version")
    try:
        parsed_version = int(version)
    except (TypeError, ValueError):
        parsed_version = _parse_version(path)
    return (created_at, parsed_version, path.stat().st_mtime, path.name)


def _safe_component(value: Any, fallback: str = "source") -> str:
    import re as _re
    raw = _re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    raw = raw.strip("._-")
    return raw or fallback


def _primary_source_id(path: Path, expected_ids: Iterable[str], fallback: str) -> str:
    expected = {_norm_source_id(item): str(item) for item in expected_ids if item}
    for source_id in infer_source_ids(path):
        if _norm_source_id(source_id) in expected:
            return expected[_norm_source_id(source_id)]
    ids = infer_source_ids(path)
    return str(ids[0]) if ids else fallback


def find_sources(
    patterns: Iterable[str],
    *,
    mode: str = "latest",
    source_ids: Iterable[str] = (),
) -> list[Path]:
    found: dict[Path, Path] = {}
    expected_ids = tuple(source_ids) or _source_ids_from_patterns(patterns)
    if expected_ids and SOURCE_ARTIFACTS_DIR.exists():
        for path in SOURCE_ARTIFACTS_DIR.iterdir():
            if path.is_dir() and source_matches_ids(path, expected_ids):
                found[path.resolve()] = path
    if not found:
        for pattern in patterns:
            for path in SOURCE_ARTIFACTS_DIR.glob(pattern):
                if path.is_dir():
                    found[path.resolve()] = path
    ordered = sorted(found.values(), key=_source_sort_key)
    if mode == "all":
        return ordered
    if mode == "latest":
        return ordered[-1:] if ordered else []
    raise ValueError(f"Unknown source selection mode: {mode}")
