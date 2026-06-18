#!/usr/bin/env python3
"""Common helpers for the migrated 0-15 pipeline.

The step layer is deterministic: it imports source artifacts owned by the
current project, imports validated upstream stage artifacts declared by the
artifact registry, records missing inputs explicitly, and writes validation
metadata under outputs/artifacts/.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_ARTIFACTS_DIR = BASE_DIR / "source_artifacts"
OUTPUTS_DIR = BASE_DIR / "outputs"
ARTIFACTS_DIR = OUTPUTS_DIR / "artifacts"
CHECKPOINTS_DIR = OUTPUTS_DIR / "checkpoints"
PROMPTS_DIR = BASE_DIR / "prompts" / "steps"
GATE_LOG_PATH = BASE_DIR / "gate_log.yaml"


@dataclass(frozen=True)
class SourceGroup:
    label: str
    patterns: tuple[str, ...]
    mode: str = "latest"
    required: bool = False
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepSpec:
    number: int
    slug: str
    title: str
    design_doc: str | None = None


STEP_SPECS: dict[int, StepSpec] = {
    0: StepSpec(0, "idea_intake", "Idea intake", "01_*.md"),
    1: StepSpec(1, "demo", "Gameplay framework", "02_*.md"),
    2: StepSpec(2, "design_review", "Design review and freeze", "03_*.md"),
    3: StepSpec(3, "program_requirements", "Program requirements", "04_*.md"),
    4: StepSpec(4, "art_requirements", "Art requirements", "05_*.md"),
    5: StepSpec(5, "program_review", "Program requirements review", "06_*.md"),
    6: StepSpec(6, "art_review", "Art requirements review", "07_*.md"),
    7: StepSpec(7, "design_to_plan", "Program plan", "08_*.md"),
    8: StepSpec(8, "art_plan", "Art plan", "09_*.md"),
    9: StepSpec(9, "asset_alignment", "Asset alignment", "10_*.md"),
    10: StepSpec(10, "dev_execution", "Development execution", "11_*.md"),
    11: StepSpec(11, "art_production", "Art production", "12_*.md"),
    12: StepSpec(12, "integration_validation", "Integration validation", "13_*.md"),
    13: StepSpec(13, "build_package", "Build package", "14_*.md"),
    14: StepSpec(14, "delta_patch", "Delta patch", "15_*.md"),
    15: StepSpec(15, "migration_audit", "Migration audit", "16_*.md"),
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def stage_dir(step_number: int) -> Path:
    return ARTIFACTS_DIR / f"stage_{step_number:02d}"


def prompt_path(step_number: int) -> Path:
    return PROMPTS_DIR / f"step{step_number:02d}.txt"


def _safe_reset_dir(path: Path, root: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = path.resolve()
    if target_resolved == root_resolved or root_resolved not in target_resolved.parents:
        raise RuntimeError(f"Refusing to reset path outside artifact root: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def reset_stage(step_number: int) -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = stage_dir(step_number)
    _safe_reset_dir(path, ARTIFACTS_DIR)
    return path


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _parse_version(path: Path) -> int:
    match = re.search(r"_v(\d+)$", path.name)
    return int(match.group(1)) if match else 0


def _parse_date(path: Path) -> str:
    match = re.search(r"_(\d{8})(?:_|$)", path.name)
    return match.group(1) if match else ""


def _sort_key(path: Path) -> tuple[str, int, float, str]:
    return (_parse_date(path), _parse_version(path), path.stat().st_mtime, path.name)


SOURCE_TYPES = (
    "Concept",
    "GameplayFramework",
    "SubsystemDesign",
    "AIDesignScript",
    "Design",
    "DevelopmentDesign",
    "ProgReq",
    "ArtReq",
    "ProgReview",
    "ArtReview",
    "Plans",
    "ArtPlans",
    "Alignment",
    "DevExecution",
    "ArtProduction",
    "Integration",
    "Build",
    "DeltaPatch",
)

SOURCE_MARKERS = {
    "selected_play_prototype.json": "Concept",
    "gameplay_framework.json": "GameplayFramework",
    "approved_subsystems.json": "SubsystemDesign",
    "ai_design_script.json": "AIDesignScript",
    "frozen_game_design.md": "Design",
    "development_system_design.md": "DevelopmentDesign",
    "program_requirements_contract.json": "ProgReq",
    "art_requirements_contract.json": "ArtReq",
    "ProgReview_report.json": "ProgReview",
    "ArtReview_report.json": "ArtReview",
    "program_plan_index.md": "Plans",
    "art_plan_index.md": "ArtPlans",
    "AlignmentProtocol.md": "Alignment",
    "devexecution.json": "DevExecution",
    "artproduction.json": "ArtProduction",
    "integration.json": "Integration",
    "build_report.json": "Build",
    "patch_manifest.json": "DeltaPatch",
}


def _norm_source_id(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _source_ids_from_patterns(patterns: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for pattern in patterns:
        for source_type in SOURCE_TYPES:
            if f"_{source_type}_" in pattern or pattern.startswith(f"{source_type}_"):
                result.append(source_type)
    return tuple(dict.fromkeys(result))


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


def _safe_component(value: Any, fallback: str = "source") -> str:
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    raw = raw.strip("._-")
    return raw or fallback


def _primary_source_id(path: Path, expected_ids: Iterable[str], fallback: str) -> str:
    expected = {_norm_source_id(item): str(item) for item in expected_ids if item}
    for source_id in infer_source_ids(path):
        if _norm_source_id(source_id) in expected:
            return expected[_norm_source_id(source_id)]
    ids = infer_source_ids(path)
    return str(ids[0]) if ids else fallback


def _source_sort_key(path: Path) -> tuple[str, int, float, str]:
    metadata = source_package_metadata(path)
    created_at = str(metadata.get("created_at") or metadata.get("timestamp") or _parse_date(path))
    version = metadata.get("version")
    try:
        parsed_version = int(version)
    except (TypeError, ValueError):
        parsed_version = _parse_version(path)
    return (created_at, parsed_version, path.stat().st_mtime, path.name)


def find_sources(patterns: Iterable[str], *, mode: str = "latest", source_ids: Iterable[str] = ()) -> list[Path]:
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


def copy_tree_contents(source: Path, dest: Path, *, skip_dirs: set[str] | None = None) -> None:
    skip_dirs = skip_dirs or set()
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_dir() and item.name in skip_dirs:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def file_manifest(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel_path = path.relative_to(root).as_posix()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        files.append({
            "path": rel_path,
            "size_bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    return files


def _stage_files_for_reference(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for item in file_manifest(root):
        if item["path"] == "reference_manifest.json":
            continue
        entry = dict(item)
        entry["stage_path"] = rel(root / item["path"])
        entry["role"] = classify_stage_file(item["path"])
        files.append(entry)
    return files


def classify_stage_file(path_text: str) -> str:
    normalized = path_text.replace("\\", "/")
    name = Path(normalized).name
    if normalized.startswith("guidance/"):
        return "guidance"
    if normalized.startswith("imported/"):
        return "source_import"
    if normalized.startswith("upstream/"):
        return "upstream_reference"
    if name in {"artifact_index.json", "reference_manifest.json"}:
        return "stage_index"
    if name in {"validation_report.json", "artifact_reviews.json", "artifact_validation_layer.json"}:
        return "validation"
    if name == "artifact_layer_manifest.json":
        return "artifact_layer"
    if name == "README.md" or name.startswith("MISSING_") or name.startswith("OPTIONAL_"):
        return "operator_report"
    if name.startswith("migration_audit"):
        return "audit"
    return "stage_file"


def _registry_artifacts() -> list[dict[str, Any]]:
    registry_path = BASE_DIR / "artifact_layer" / "registry.json"
    data = read_json(registry_path, {})
    artifacts = data.get("artifacts", []) if isinstance(data, dict) else []
    if not isinstance(artifacts, list):
        return []
    return [item for item in artifacts if isinstance(item, dict)]


def upstream_artifacts_for_step(step_number: int) -> list[dict[str, Any]]:
    artifacts = _registry_artifacts()
    by_id = {
        str(item.get("id")): item
        for item in artifacts
        if item.get("id") is not None
    }
    upstream: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if int(artifact.get("stage", -1)) != step_number:
            continue
        for dep_id in artifact.get("depends_on", []):
            dep = by_id.get(str(dep_id))
            if dep is not None:
                upstream[str(dep_id)] = dep
    return list(upstream.values())


def current_artifacts_for_step(step_number: int) -> list[dict[str, Any]]:
    return [artifact for artifact in _registry_artifacts() if int(artifact.get("stage", -1)) == step_number]


def _upstream_file_refs(source_dir: Path) -> list[dict[str, Any]]:
    reference_path = source_dir / "reference_manifest.json"
    reference = read_json(reference_path, {})
    files = reference.get("files", []) if isinstance(reference, dict) else []
    if isinstance(files, list) and files:
        result = []
        for item in files:
            if not isinstance(item, dict):
                continue
            path_text = str(item.get("stage_path") or item.get("path") or "")
            if not path_text:
                continue
            result.append({
                "path": item.get("path", Path(path_text).name),
                "stage_path": path_text,
                "role": item.get("role", classify_stage_file(path_text)),
                "size_bytes": item.get("size_bytes"),
                "sha256": item.get("sha256"),
                "source_manifest": rel(reference_path),
            })
        if result:
            return result

    index = read_json(source_dir / "artifact_index.json", {})
    manifest_files = index.get("manifest", []) if isinstance(index, dict) else []
    if not isinstance(manifest_files, list) or not manifest_files:
        manifest_files = file_manifest(source_dir)
    result = []
    for item in manifest_files:
        if not isinstance(item, dict):
            continue
        path_text = str(item.get("path") or "")
        if not path_text:
            continue
        result.append({
            "path": path_text,
            "stage_path": rel(source_dir / path_text),
            "role": classify_stage_file(path_text),
            "size_bytes": item.get("size_bytes"),
            "sha256": item.get("sha256"),
            "source_manifest": rel(source_dir / "artifact_index.json"),
        })
    return result


def import_upstream_artifacts(step_number: int, out_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    imported: list[dict[str, Any]] = []
    missing: list[str] = []
    for artifact in upstream_artifacts_for_step(step_number):
        artifact_id = str(artifact.get("id", "unknown"))
        upstream_stage = int(artifact.get("stage", -1))
        source_dir = stage_dir(upstream_stage)
        validation_path = source_dir / "artifact_validation_layer.json"
        validation = read_json(validation_path, {})
        if not source_dir.exists():
            missing.append(f"{artifact_id}: missing {rel(source_dir)}")
            continue
        if not isinstance(validation, dict) or validation.get("status") != "success":
            missing.append(f"{artifact_id}: artifact validation is {validation.get('status', 'missing') if isinstance(validation, dict) else 'invalid'}")
            continue

        target = out_dir / "upstream" / f"stage_{upstream_stage:02d}" / artifact_id.replace(".", "_")
        upstream_files = _upstream_file_refs(source_dir)
        reference_manifest_path = source_dir / "reference_manifest.json"
        artifact_index_path = source_dir / "artifact_index.json"
        validation_report_path = source_dir / "validation_report.json"
        write_json(
            target / "UPSTREAM_REFERENCE.json",
            {
                "artifact_id": artifact_id,
                "stage": upstream_stage,
                "source": rel(source_dir),
                "reference_manifest": rel(reference_manifest_path) if reference_manifest_path.exists() else "",
                "artifact_index": rel(artifact_index_path) if artifact_index_path.exists() else "",
                "validation_report": rel(validation_report_path) if validation_report_path.exists() else "",
                "file_count": len(upstream_files),
                "files": upstream_files,
                "note": "Files are referenced by manifest and are not copied into this stage.",
            },
        )
        imported.append({
            "artifact_id": artifact_id,
            "stage": str(upstream_stage),
            "source": rel(source_dir),
            "target": rel(target / "UPSTREAM_REFERENCE.json"),
            "reference_dir": rel(target),
            "reference_manifest": rel(reference_manifest_path) if reference_manifest_path.exists() else "",
            "artifact_index": rel(artifact_index_path) if artifact_index_path.exists() else "",
            "validation_report": rel(validation_report_path) if validation_report_path.exists() else "",
            "file_count": len(upstream_files),
        })
    return imported, missing


def build_reference_manifest(
    step_number: int,
    out_dir: Path,
    *,
    imported_sources: list[dict[str, str]],
    imported_upstream_artifacts: list[dict[str, Any]],
    missing_required_groups: list[str],
    optional_missing_groups: list[str],
    missing_upstream_artifacts: list[str],
) -> dict[str, Any]:
    source_inputs = []
    upstream_inputs = []
    relations = []

    current_artifacts = current_artifacts_for_step(step_number)
    current_artifact_ids = [str(item.get("id")) for item in current_artifacts if item.get("id")]

    for source in imported_sources:
        source_root = BASE_DIR / source["source"]
        target_root = BASE_DIR / source["target"]
        files = []
        for item in file_manifest(source_root):
            source_file = rel(source_root / item["path"])
            target_file = rel(target_root / item["path"])
            files.append({
                "source_path": source_file,
                "target_path": target_file,
                "path": item["path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
            })
            relations.append({
                "type": "source_file_copied",
                "from": source_file,
                "to": target_file,
                "source_group": source["group"],
            })
        source_inputs.append({
            "group": source["group"],
            "source": source["source"],
            "target": source["target"],
            "file_count": len(files),
            "files": files,
        })

    for upstream in imported_upstream_artifacts:
        source_dir = BASE_DIR / str(upstream["source"])
        files = _upstream_file_refs(source_dir)
        upstream_artifact_id = str(upstream["artifact_id"])
        upstream_inputs.append({
            "artifact_id": upstream_artifact_id,
            "stage": int(upstream["stage"]),
            "stage_dir": upstream["source"],
            "reference_record": upstream["target"],
            "reference_manifest": upstream.get("reference_manifest", ""),
            "artifact_index": upstream.get("artifact_index", ""),
            "validation_report": upstream.get("validation_report", ""),
            "file_count": len(files),
            "files": files,
        })
        for file_ref in files:
            relations.append({
                "type": "upstream_file_referenced",
                "from": file_ref["stage_path"],
                "to": rel(out_dir / "reference_manifest.json"),
                "upstream_artifact_id": upstream_artifact_id,
                "upstream_stage": int(upstream["stage"]),
            })
        for current_artifact_id in current_artifact_ids:
            relations.append({
                "type": "artifact_dependency",
                "from_artifact_id": upstream_artifact_id,
                "to_artifact_id": current_artifact_id,
            })

    manifest = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "stage": {
            "number": step_number,
            "name": STEP_SPECS[step_number].slug,
            "title": STEP_SPECS[step_number].title,
            "artifact_root": rel(out_dir),
        },
        "artifacts": current_artifacts,
        "inputs": {
            "source_artifacts": source_inputs,
            "upstream_artifacts": upstream_inputs,
            "missing_required_groups": missing_required_groups,
            "optional_missing_groups": optional_missing_groups,
            "missing_upstream_artifacts": missing_upstream_artifacts,
        },
        "files": _stage_files_for_reference(out_dir),
        "relations": relations,
        "summary": {
            "local_file_count": 0,
            "source_file_count": sum(item["file_count"] for item in source_inputs),
            "upstream_artifact_count": len(upstream_inputs),
            "upstream_file_count": sum(item["file_count"] for item in upstream_inputs),
            "relation_count": len(relations),
        },
    }
    manifest["summary"]["local_file_count"] = len(manifest["files"])
    write_json(out_dir / "reference_manifest.json", manifest)
    return manifest


def refresh_reference_manifest_file_inventory(step_number: int) -> dict[str, Any]:
    out_dir = stage_dir(step_number)
    path = out_dir / "reference_manifest.json"
    manifest = read_json(path, {})
    if not isinstance(manifest, dict):
        return {}
    manifest["updated_at"] = now_iso()
    manifest["files"] = _stage_files_for_reference(out_dir)
    summary = manifest.setdefault("summary", {})
    if isinstance(summary, dict):
        summary["local_file_count"] = len(manifest["files"])
        summary["relation_count"] = len(manifest.get("relations", []))
    write_json(path, manifest)
    return manifest


def design_docs_for_step(step_number: int) -> list[Path]:
    spec = STEP_SPECS[step_number]
    if not spec.design_doc:
        return []
    desc_dir = BASE_DIR / "design_desc"
    return sorted(path for path in desc_dir.glob(spec.design_doc) if path.is_file())


def copy_guidance_docs(step_number: int, dest_root: Path) -> list[str]:
    copied: list[str] = []
    for doc in design_docs_for_step(step_number):
        target = dest_root / "guidance" / doc.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(doc, target)
        copied.append(rel(target))
    prompt = prompt_path(step_number)
    if prompt.exists():
        target = dest_root / "guidance" / prompt.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prompt, target)
        copied.append(rel(target))
    return copied


def validation_report(
    step_number: int,
    status: str,
    *,
    valid: bool,
    imported_sources: list[dict[str, str]],
    missing_groups: list[str],
    imported_upstream_artifacts: list[dict[str, Any]] | None = None,
    missing_upstream_artifacts: list[str] | None = None,
    optional_missing_groups: list[str] | None = None,
    missing_required_groups: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "step": step_number,
        "name": STEP_SPECS[step_number].slug,
        "title": STEP_SPECS[step_number].title,
        "status": status,
        "valid": valid,
        "timestamp": now_iso(),
        "artifacts_dir": rel(stage_dir(step_number)),
        "imported_sources": imported_sources,
        "missing_groups": missing_groups,
        "missing_required_groups": missing_required_groups or missing_groups,
        "optional_missing_groups": optional_missing_groups or [],
        "imported_upstream_artifacts": imported_upstream_artifacts or [],
        "missing_upstream_artifacts": missing_upstream_artifacts or [],
        "notes": notes or [],
    }


def append_gate_log(step_number: int, status: str, *, imported: bool, message: str = "") -> None:
    spec = STEP_SPECS[step_number]
    GATE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GATE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("- timestamp: " + now_iso() + "\n")
        handle.write(f"  step: {step_number}\n")
        handle.write(f"  name: {spec.slug}\n")
        handle.write(f"  status: {status}\n")
        handle.write("  gate: auto_approved\n")
        handle.write(f"  imported: {str(imported).lower()}\n")
        handle.write(f"  artifacts_dir: {rel(stage_dir(step_number))}\n")
        if message:
            safe_message = message.replace("\n", " ")
            handle.write(f"  message: {json.dumps(safe_message, ensure_ascii=False)}\n")


def write_checkpoint(step_number: int, result: dict[str, Any]) -> Path:
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINTS_DIR / f"step_{step_number:02d}_{timestamp()}.json"
    return write_json(path, result)


def run_step_cli(step_number: int) -> int:
    """Route direct step module execution through the full orchestrator.

    Importing a step module from orchestrator still calls its local run(context)
    function. Running `python -m steps.stepX` should not bypass the artifact
    layer, reviewers, validators, dependency graph, or gate logging.
    """
    from orchestrator import run_range

    return run_range(step_number, step_number, auto_approve=True)


def run_import_step(
    step_number: int,
    groups: Iterable[SourceGroup],
    *,
    context: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    _ = context or {}
    spec = STEP_SPECS[step_number]
    out_dir = reset_stage(step_number)
    copied_guidance = copy_guidance_docs(step_number, out_dir)
    imported_upstream_artifacts, missing_upstream_artifacts = import_upstream_artifacts(step_number, out_dir)
    has_upstream_contract = bool(upstream_artifacts_for_step(step_number))

    imported_sources: list[dict[str, str]] = []
    missing_groups: list[str] = []
    optional_missing_groups: list[str] = []
    missing_required_groups: list[str] = []
    for group in groups:
        sources = find_sources(group.patterns, mode=group.mode, source_ids=group.source_ids)
        if not sources:
            if group.required and not has_upstream_contract:
                missing_groups.append(group.label)
                missing_required_groups.append(group.label)
            else:
                optional_missing_groups.append(group.label)
            continue
        for source_index, source in enumerate(sources, start=1):
            metadata = source_package_metadata(source)
            source_ids = infer_source_ids(source)
            primary_id = _primary_source_id(source, group.source_ids, group.label)
            version = metadata.get("version") or _parse_version(source)
            target_name = _safe_component(f"{primary_id}_v{version}" if version else f"{primary_id}_{source_index:03d}")
            target = out_dir / "imported" / group.label / target_name
            copy_tree_contents(source, target)
            imported_sources.append({
                "group": group.label,
                "source_ids": list(source_ids),
                "package_id": str(metadata.get("package_id") or ""),
                "package_type": str(metadata.get("package_type") or primary_id),
                "package_manifest": rel(source / "package_manifest.json") if (source / "package_manifest.json").exists() else "",
                "source": rel(source),
                "target": rel(target),
            })

    if missing_required_groups:
        write_text(
            out_dir / "MISSING_SOURCE_ARTIFACTS.md",
            "# Missing Source Artifacts\n\n"
            + "\n".join(f"- {group}" for group in missing_required_groups)
            + "\n",
        )
    if optional_missing_groups:
        write_text(
            out_dir / "OPTIONAL_SOURCE_ARTIFACTS_NOT_PROVIDED.md",
            "# Optional Source Artifacts Not Provided\n\n"
            + "\n".join(f"- {group}" for group in optional_missing_groups)
            + "\n",
        )
    if missing_upstream_artifacts:
        write_text(
            out_dir / "MISSING_UPSTREAM_ARTIFACTS.md",
            "# Missing Upstream Artifacts\n\n"
            + "\n".join(f"- {item}" for item in missing_upstream_artifacts)
            + "\n",
        )

    imported = bool(imported_sources or imported_upstream_artifacts)
    report_notes = list(notes or [])
    if missing_required_groups:
        report_notes.append("Required current-project source artifact groups are missing.")
    if missing_upstream_artifacts:
        report_notes.append("Required upstream stage artifacts are missing or not validated.")
    if optional_missing_groups and imported_upstream_artifacts:
        report_notes.append("Optional current-project source artifact groups were not provided; validated upstream artifacts were used.")
    if not imported:
        report_notes.append("No source artifact directory or upstream stage artifact matched this stage; generated metadata only.")
    report_status = "failed" if missing_required_groups or missing_upstream_artifacts else "success"
    report_valid = not missing_required_groups and not missing_upstream_artifacts

    index = {
        "step": step_number,
        "name": spec.slug,
        "title": spec.title,
        "timestamp": now_iso(),
        "artifact_root": rel(out_dir),
        "reference_manifest": rel(out_dir / "reference_manifest.json"),
        "guidance_docs": copied_guidance,
        "imported": imported,
        "imported_sources": imported_sources,
        "missing_groups": missing_groups,
        "missing_required_groups": missing_required_groups,
        "optional_missing_groups": optional_missing_groups,
        "imported_upstream_artifacts": imported_upstream_artifacts,
        "missing_upstream_artifacts": missing_upstream_artifacts,
        "manifest": file_manifest(out_dir),
    }
    write_json(out_dir / "artifact_index.json", index)
    write_text(
        out_dir / "README.md",
        f"# Stage {step_number:02d}: {spec.title}\n\n"
        f"- Imported source artifacts: {len(imported_sources)}\n"
        f"- Imported upstream artifacts: {len(imported_upstream_artifacts)}\n"
        f"- Missing required source groups: {', '.join(missing_required_groups) if missing_required_groups else 'none'}\n"
        f"- Optional source groups not provided: {', '.join(optional_missing_groups) if optional_missing_groups else 'none'}\n"
        f"- Missing upstream artifacts: {', '.join(missing_upstream_artifacts) if missing_upstream_artifacts else 'none'}\n"
        f"- Prompt: {rel(prompt_path(step_number)) if prompt_path(step_number).exists() else 'not found'}\n",
    )

    report = validation_report(
        step_number,
        report_status,
        valid=report_valid,
        imported_sources=imported_sources,
        missing_groups=missing_groups,
        imported_upstream_artifacts=imported_upstream_artifacts,
        missing_upstream_artifacts=missing_upstream_artifacts,
        optional_missing_groups=optional_missing_groups,
        missing_required_groups=missing_required_groups,
        notes=report_notes,
    )
    write_json(out_dir / "validation_report.json", report)
    build_reference_manifest(
        step_number,
        out_dir,
        imported_sources=imported_sources,
        imported_upstream_artifacts=imported_upstream_artifacts,
        missing_required_groups=missing_required_groups,
        optional_missing_groups=optional_missing_groups,
        missing_upstream_artifacts=missing_upstream_artifacts,
    )
    append_gate_log(step_number, report_status, imported=imported)
    write_checkpoint(step_number, report)
    if missing_required_groups:
        raise RuntimeError(f"Missing required current-project source groups: {', '.join(missing_required_groups)}")
    if missing_upstream_artifacts:
        raise RuntimeError(f"Missing required upstream artifacts: {', '.join(missing_upstream_artifacts)}")
    return report


def iter_runtime_files(base_dir: Path = BASE_DIR) -> Iterable[Path]:
    skip_dirs = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "outputs",
        "_cleanup_backup",
        "GeneratedAssets",
        "ArtAssets",
    }
    for root_text, dirs, files in os.walk(base_dir):
        root = Path(root_text)
        dirs[:] = [name for name in dirs if name not in skip_dirs]
        for name in files:
            path = root / name
            if path.suffix == ".py" or path.name.startswith("requirements"):
                yield path


def forbidden_runtime_matches(base_dir: Path = BASE_DIR) -> list[dict[str, Any]]:
    patterns = [
        re.compile(r"\bfrom\s+" + "cre" + r"wai\b", re.IGNORECASE),
        re.compile(r"\bimport\s+" + "cre" + r"wai\b", re.IGNORECASE),
        re.compile("cre" + r"wai_tools", re.IGNORECASE),
        re.compile(r"\bCrew\s*\("),
        re.compile(r"\bAgent\s*\("),
        re.compile(r"\bTask\s*\("),
        re.compile(r"\bProcess\."),
        re.compile(r"\bLLM\s*\("),
    ]
    matches: list[dict[str, Any]] = []
    for path in iter_runtime_files(base_dir):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, 1):
            if any(pattern.search(line) for pattern in patterns):
                matches.append({"path": rel(path), "line": line_no, "text": line.strip()})
    return matches


def run_audit_step(context: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = context or {}
    step_number = 15
    out_dir = reset_stage(step_number)
    copied_guidance = copy_guidance_docs(step_number, out_dir)
    imported_upstream_artifacts, missing_upstream_artifacts = import_upstream_artifacts(step_number, out_dir)

    stage_reports = []
    missing_stage_reports = []
    artifact_layer_reports = []
    missing_artifact_layer_reports = []
    failed_artifact_layer_reports = []
    for num in range(0, 15):
        report_path = stage_dir(num) / "validation_report.json"
        if not report_path.exists():
            missing_stage_reports.append(num)
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {"step": num, "status": "invalid_json", "valid": False}
        stage_reports.append(report)

        layer_path = stage_dir(num) / "artifact_validation_layer.json"
        if not layer_path.exists():
            missing_artifact_layer_reports.append(num)
            continue
        try:
            layer_report = json.loads(layer_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            layer_report = {"step": num, "status": "invalid_json"}
        artifact_layer_reports.append(layer_report)
        if layer_report.get("status") != "success":
            failed_artifact_layer_reports.append(num)

    forbidden = forbidden_runtime_matches(BASE_DIR)
    from tools.execution_object_integration import audit_execution_object_store

    execution_object_audit = audit_execution_object_store(BASE_DIR)
    passed = (
        not missing_stage_reports
        and not missing_artifact_layer_reports
        and not failed_artifact_layer_reports
        and not missing_upstream_artifacts
        and not forbidden
        and execution_object_audit.get("valid") is True
        and all(
            report.get("status") == "success" and report.get("valid") is True
            for report in stage_reports
        )
    )

    audit = {
        "step": step_number,
        "name": STEP_SPECS[step_number].slug,
        "timestamp": now_iso(),
        "passed": passed,
        "checked_stages": list(range(0, 15)),
        "missing_stage_reports": missing_stage_reports,
        "missing_artifact_layer_reports": missing_artifact_layer_reports,
        "failed_artifact_layer_reports": failed_artifact_layer_reports,
        "imported_upstream_artifacts": imported_upstream_artifacts,
        "missing_upstream_artifacts": missing_upstream_artifacts,
        "forbidden_runtime_references": forbidden,
        "execution_object_audit": execution_object_audit,
        "guidance_docs": copied_guidance,
        "stage_reports": stage_reports,
        "artifact_layer_reports": artifact_layer_reports,
    }
    write_json(out_dir / "migration_audit.json", audit)
    write_text(
        out_dir / "migration_audit.md",
        "# Migration Audit\n\n"
        f"- Passed: {str(passed).lower()}\n"
        f"- Missing stage reports: {missing_stage_reports or 'none'}\n"
        f"- Missing artifact layer reports: {missing_artifact_layer_reports or 'none'}\n"
        f"- Failed artifact layer reports: {failed_artifact_layer_reports or 'none'}\n"
        f"- Missing upstream artifacts: {missing_upstream_artifacts or 'none'}\n"
        f"- Forbidden runtime references: {len(forbidden)}\n"
        f"- Execution object audit: {execution_object_audit.get('valid')}\n",
    )

    report = validation_report(
        step_number,
        "success" if passed else "failed",
        valid=passed,
        imported_sources=[],
        missing_groups=[],
        imported_upstream_artifacts=imported_upstream_artifacts,
        missing_upstream_artifacts=missing_upstream_artifacts,
        notes=["Final migration audit."],
    )
    write_json(out_dir / "validation_report.json", report)
    build_reference_manifest(
        step_number,
        out_dir,
        imported_sources=[],
        imported_upstream_artifacts=imported_upstream_artifacts,
        missing_required_groups=[],
        optional_missing_groups=[],
        missing_upstream_artifacts=missing_upstream_artifacts,
    )
    append_gate_log(step_number, report["status"], imported=bool(imported_upstream_artifacts))
    write_checkpoint(step_number, report)
    if not passed:
        raise RuntimeError("Migration audit failed; inspect outputs/artifacts/stage_15/migration_audit.json")
    return report


def finalize_migration_audit_with_self_layer() -> dict[str, Any]:
    """Record stage 15's own artifact-layer validation in the final audit.

    Stage 15 creates `migration_audit.json` before the orchestrator writes the
    stage 15 artifact-layer reports. This finalizer is called after those
    reports exist so the audit can cover its own wrapper layer as well.
    """
    audit_path = stage_dir(15) / "migration_audit.json"
    report_path = stage_dir(15) / "validation_report.json"
    layer_path = stage_dir(15) / "artifact_validation_layer.json"
    if not audit_path.exists():
        raise FileNotFoundError(f"Missing migration audit file: {audit_path}")

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if layer_path.exists():
        try:
            layer_report = json.loads(layer_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            layer_report = {"step": 15, "status": "invalid_json"}
    else:
        layer_report = {"step": 15, "status": "missing"}

    layer_status = layer_report.get("status")
    audit["stage_15_artifact_layer_report"] = layer_report
    audit["stage_15_artifact_layer_status"] = layer_status
    audit["passed"] = bool(audit.get("passed")) and layer_status == "success"
    write_json(audit_path, audit)

    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["valid"] = audit["passed"]
        report["status"] = "success" if audit["passed"] else "failed"
        report["notes"] = list(report.get("notes", [])) + ["Stage 15 self artifact layer finalized."]
        write_json(report_path, report)

    if not audit["passed"]:
        raise RuntimeError("Migration audit self-layer finalization failed.")
    return audit
