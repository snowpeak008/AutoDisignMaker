"""Source artifact import helpers for the 0-16 pipeline."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterable

from core.io import file_manifest, now_iso, read_json, rel, write_json, write_text
from core.paths import PROJECT_ROOT
from core.registry import STEP_SPECS, max_step_number
from core.source.finder import (
    _parse_version,
    _primary_source_id,
    _safe_component,
    find_sources,
    infer_source_ids,
    source_package_metadata,
)
from core.source.groups import SourceGroup
from core.stage import classify_stage_file, stage_dir, reset_stage


def _registry_artifacts() -> list[dict[str, Any]]:
    registry_path = PROJECT_ROOT / "pipeline" / "artifact_layer" / "registry.json"
    data = read_json(registry_path, {})
    artifacts = data.get("artifacts", []) if isinstance(data, dict) else []
    if not isinstance(artifacts, list):
        return []
    return [item for item in artifacts if isinstance(item, dict)]


def upstream_artifacts_for_step(step_number: int) -> list[dict[str, Any]]:
    artifacts = _registry_artifacts()
    by_id = {str(item.get("id")): item for item in artifacts if item.get("id") is not None}
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
    return [a for a in _registry_artifacts() if int(a.get("stage", -1)) == step_number]


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


def import_upstream_artifacts(
    step_number: int, out_dir: Path
) -> tuple[list[dict[str, Any]], list[str]]:
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
            status = validation.get("status", "missing") if isinstance(validation, dict) else "invalid"
            missing.append(f"{artifact_id}: artifact validation is {status}")
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
            target_name = _safe_component(
                f"{primary_id}_v{version}" if version else f"{primary_id}_{source_index:03d}"
            )
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
        write_text(out_dir / "MISSING_SOURCE_ARTIFACTS.md",
            "# Missing Source Artifacts\n\n" + "\n".join(f"- {g}" for g in missing_required_groups) + "\n")
    if optional_missing_groups:
        write_text(out_dir / "OPTIONAL_SOURCE_ARTIFACTS_NOT_PROVIDED.md",
            "# Optional Source Artifacts Not Provided\n\n" + "\n".join(f"- {g}" for g in optional_missing_groups) + "\n")
    if missing_upstream_artifacts:
        write_text(out_dir / "MISSING_UPSTREAM_ARTIFACTS.md",
            "# Missing Upstream Artifacts\n\n" + "\n".join(f"- {item}" for item in missing_upstream_artifacts) + "\n")

    imported = bool(imported_sources or imported_upstream_artifacts)
    report_notes = list(notes or [])
    if missing_required_groups:
        report_notes.append("Required current-project source artifact groups are missing.")
    if missing_upstream_artifacts:
        report_notes.append("Required upstream stage artifacts are missing or not validated.")
    if not imported:
        report_notes.append("No source artifact directory or upstream stage artifact matched this stage.")

    report_status = "failed" if (missing_required_groups or missing_upstream_artifacts) else "success"
    report_valid = not missing_required_groups and not missing_upstream_artifacts

    index = {
        "step": step_number,
        "name": spec.slug,
        "title": spec.title,
        "timestamp": now_iso(),
        "artifact_root": rel(out_dir),
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
        f"- Missing required source groups: {', '.join(missing_required_groups) or 'none'}\n"
        f"- Optional source groups not provided: {', '.join(optional_missing_groups) or 'none'}\n"
        f"- Missing upstream artifacts: {', '.join(missing_upstream_artifacts) or 'none'}\n",
    )

    report = {
        "step": step_number,
        "name": spec.slug,
        "title": spec.title,
        "status": report_status,
        "valid": report_valid,
        "timestamp": now_iso(),
        "artifacts_dir": rel(out_dir),
        "imported_sources": imported_sources,
        "missing_groups": missing_groups,
        "missing_required_groups": missing_required_groups,
        "optional_missing_groups": optional_missing_groups,
        "imported_upstream_artifacts": imported_upstream_artifacts,
        "missing_upstream_artifacts": missing_upstream_artifacts,
        "notes": report_notes,
    }
    write_json(out_dir / "validation_report.json", report)

    if missing_required_groups:
        raise RuntimeError(f"Missing required current-project source groups: {', '.join(missing_required_groups)}")
    if missing_upstream_artifacts:
        raise RuntimeError(f"Missing required upstream artifacts: {', '.join(missing_upstream_artifacts)}")
    return report


def run_step_cli(step_number: int) -> int:
    """Route direct step execution through the full orchestrator."""
    from core.main import run_range
    return run_range(step_number, step_number, auto_approve=True)


def forbidden_runtime_matches(base_dir: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    """Scan Python files for forbidden agent runtime imports (CrewAI etc.)."""
    import os, re
    patterns = [
        re.compile(r"\bfrom\s+crewai\b", re.IGNORECASE),
        re.compile(r"\bimport\s+crewai\b", re.IGNORECASE),
        re.compile(r"crewai_tools", re.IGNORECASE),
        re.compile(r"\bCrew\s*\("),
        re.compile(r"\bAgent\s*\("),
        re.compile(r"\bTask\s*\("),
        re.compile(r"\bProcess\."),
        re.compile(r"\bLLM\s*\("),
    ]
    skip = {".git", "__pycache__", "venv", ".venv", "outputs", "_cleanup_backup",
            "GeneratedAssets", "ArtAssets"}
    matches: list[dict[str, Any]] = []
    for root_text, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if not (fname.endswith(".py") or fname.startswith("requirements")):
                continue
            fpath = Path(root_text) / fname
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if any(p.search(line) for p in patterns):
                    matches.append({"path": rel(fpath), "line": lineno, "text": line.strip()})
    return matches


def build_reference_manifest(
    step_number: int,
    out_dir: Path,
    *,
    imported_sources: list[dict[str, Any]],
    imported_upstream_artifacts: list[dict[str, Any]],
    missing_required_groups: list[str],
    optional_missing_groups: list[str],
    missing_upstream_artifacts: list[str],
) -> dict[str, Any]:
    from core.io import file_manifest as _file_manifest
    source_inputs = []
    upstream_inputs = []
    relations = []
    current_artifacts = current_artifacts_for_step(step_number)
    current_artifact_ids = [str(a.get("id")) for a in current_artifacts if a.get("id")]

    for source in imported_sources:
        source_root = PROJECT_ROOT / source["source"]
        target_root = PROJECT_ROOT / source["target"]
        files = []
        for item in _file_manifest(source_root):
            source_file = rel(source_root / item["path"])
            target_file = rel(target_root / item["path"])
            files.append({"source_path": source_file, "target_path": target_file,
                          "path": item["path"], "size_bytes": item["size_bytes"], "sha256": item["sha256"]})
            relations.append({"type": "source_file_copied", "from": source_file,
                               "to": target_file, "source_group": source["group"]})
        source_inputs.append({"group": source["group"], "source": source["source"],
                               "target": source["target"], "file_count": len(files), "files": files})

    for upstream in imported_upstream_artifacts:
        source_dir = PROJECT_ROOT / str(upstream["source"])
        files = _upstream_file_refs(source_dir)
        uid = str(upstream["artifact_id"])
        upstream_inputs.append({"artifact_id": uid, "stage": int(upstream["stage"]),
                                  "stage_dir": upstream["source"], "reference_record": upstream["target"],
                                  "file_count": len(files), "files": files})
        for f in files:
            relations.append({"type": "upstream_file_referenced", "from": f["stage_path"],
                               "to": rel(out_dir / "reference_manifest.json"),
                               "upstream_artifact_id": uid, "upstream_stage": int(upstream["stage"])})
        for cid in current_artifact_ids:
            relations.append({"type": "artifact_dependency", "from_artifact_id": uid, "to_artifact_id": cid})

    spec = STEP_SPECS[step_number]
    manifest = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "stage": {"number": step_number, "name": spec.slug, "title": spec.title, "artifact_root": rel(out_dir)},
        "artifacts": current_artifacts,
        "inputs": {"source_artifacts": source_inputs, "upstream_artifacts": upstream_inputs,
                   "missing_required_groups": missing_required_groups,
                   "optional_missing_groups": optional_missing_groups,
                   "missing_upstream_artifacts": missing_upstream_artifacts},
        "files": [],
        "relations": relations,
        "summary": {"local_file_count": 0,
                    "source_file_count": sum(s["file_count"] for s in source_inputs),
                    "upstream_artifact_count": len(upstream_inputs),
                    "upstream_file_count": sum(u["file_count"] for u in upstream_inputs),
                    "relation_count": len(relations)},
    }
    write_json(out_dir / "reference_manifest.json", manifest)
    return manifest


def refresh_reference_manifest_file_inventory(step_number: int) -> dict[str, Any]:
    from core.stage import classify_stage_file
    from core.io import file_manifest as _file_manifest
    out_dir = stage_dir(step_number)
    path = out_dir / "reference_manifest.json"
    manifest = read_json(path, {})
    if not isinstance(manifest, dict):
        return {}
    manifest["updated_at"] = now_iso()
    files = []
    for item in _file_manifest(out_dir):
        if item["path"] == "reference_manifest.json":
            continue
        entry = dict(item)
        entry["stage_path"] = rel(out_dir / item["path"])
        entry["role"] = classify_stage_file(item["path"])
        files.append(entry)
    manifest["files"] = files
    summary = manifest.setdefault("summary", {})
    if isinstance(summary, dict):
        summary["local_file_count"] = len(files)
        summary["relation_count"] = len(manifest.get("relations", []))
    write_json(path, manifest)
    return manifest


def run_audit_step(context: dict[str, Any] | None = None) -> dict[str, Any]:
    import json as _json
    import os
    import re
    _ = context or {}
    step_number = max_step_number()
    out_dir = reset_stage(step_number)
    imported_upstream_artifacts, missing_upstream_artifacts = import_upstream_artifacts(step_number, out_dir)

    stage_reports, missing_stage_reports = [], []
    artifact_layer_reports, missing_artifact_layer_reports, failed_artifact_layer_reports = [], [], []

    for num in range(0, step_number):
        report_path = stage_dir(num) / "validation_report.json"
        if not report_path.exists():
            missing_stage_reports.append(num)
            continue
        try:
            report = _json.loads(report_path.read_text(encoding="utf-8"))
        except _json.JSONDecodeError:
            report = {"step": num, "status": "invalid_json", "valid": False}
        stage_reports.append(report)
        layer_path = stage_dir(num) / "artifact_validation_layer.json"
        if not layer_path.exists():
            missing_artifact_layer_reports.append(num)
            continue
        try:
            layer_report = _json.loads(layer_path.read_text(encoding="utf-8"))
        except _json.JSONDecodeError:
            layer_report = {"step": num, "status": "invalid_json"}
        artifact_layer_reports.append(layer_report)
        if layer_report.get("status") != "success":
            failed_artifact_layer_reports.append(num)

    # forbidden runtime check
    patterns = [re.compile(r"\bfrom\s+crewai\b", re.IGNORECASE),
                re.compile(r"\bimport\s+crewai\b", re.IGNORECASE)]
    forbidden: list[dict] = []
    skip = {".git", "__pycache__", "venv", ".venv", "outputs", "_cleanup_backup"}
    for root_text, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = PROJECT_ROOT / root_text / fname
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if any(p.search(line) for p in patterns):
                    forbidden.append({"path": rel(fpath), "line": lineno, "text": line.strip()})

    from core.engines.execution_objects.integration import audit_execution_object_store
    execution_object_audit = audit_execution_object_store(PROJECT_ROOT)

    passed = (
        not missing_stage_reports and not missing_artifact_layer_reports
        and not failed_artifact_layer_reports and not missing_upstream_artifacts
        and not forbidden and execution_object_audit.get("valid") is True
        and all(r.get("status") == "success" and r.get("valid") is True for r in stage_reports)
    )

    spec = STEP_SPECS[step_number]
    audit = {
        "step": step_number, "name": spec.slug, "timestamp": now_iso(), "passed": passed,
        "checked_stages": list(range(0, step_number)),
        "missing_stage_reports": missing_stage_reports,
        "missing_artifact_layer_reports": missing_artifact_layer_reports,
        "failed_artifact_layer_reports": failed_artifact_layer_reports,
        "imported_upstream_artifacts": imported_upstream_artifacts,
        "missing_upstream_artifacts": missing_upstream_artifacts,
        "forbidden_runtime_references": forbidden,
        "execution_object_audit": execution_object_audit,
        "stage_reports": stage_reports,
        "artifact_layer_reports": artifact_layer_reports,
    }
    write_json(out_dir / "migration_audit.json", audit)
    write_text(out_dir / "migration_audit.md",
        f"# Migration Audit\n\n- Passed: {str(passed).lower()}\n"
        f"- Missing stage reports: {missing_stage_reports or 'none'}\n"
        f"- Forbidden runtime references: {len(forbidden)}\n")
    report = {
        "step": step_number, "name": spec.slug, "title": spec.title,
        "status": "success" if passed else "failed", "valid": passed,
        "timestamp": now_iso(), "artifacts_dir": rel(out_dir),
        "imported_sources": [], "missing_groups": [],
        "imported_upstream_artifacts": imported_upstream_artifacts,
        "missing_upstream_artifacts": missing_upstream_artifacts,
        "notes": ["Final migration audit."],
    }
    write_json(out_dir / "validation_report.json", report)
    if not passed:
        raise RuntimeError("Migration audit failed.")
    return report


def finalize_migration_audit_with_self_layer() -> dict[str, Any]:
    import json as _json
    step_number = max_step_number()
    audit_path = stage_dir(step_number) / "migration_audit.json"
    report_path = stage_dir(step_number) / "validation_report.json"
    layer_path = stage_dir(step_number) / "artifact_validation_layer.json"
    if not audit_path.exists():
        raise FileNotFoundError(f"Missing migration audit: {audit_path}")
    audit = _json.loads(audit_path.read_text(encoding="utf-8"))
    layer_report = (_json.loads(layer_path.read_text(encoding="utf-8"))
                    if layer_path.exists() else {"step": step_number, "status": "missing"})
    layer_status = layer_report.get("status")
    audit[f"stage_{step_number:02d}_artifact_layer_report"] = layer_report
    audit[f"stage_{step_number:02d}_artifact_layer_status"] = layer_status
    audit["passed"] = bool(audit.get("passed")) and layer_status == "success"
    write_json(audit_path, audit)
    if report_path.exists():
        report = _json.loads(report_path.read_text(encoding="utf-8"))
        report["valid"] = audit["passed"]
        report["status"] = "success" if audit["passed"] else "failed"
        report["notes"] = list(report.get("notes", [])) + [
            f"Stage {step_number:02d} self artifact layer finalized."
        ]
        write_json(report_path, report)
    if not audit["passed"]:
        raise RuntimeError("Migration audit self-layer finalization failed.")
    return audit
