#!/usr/bin/env python3
"""Project save manager.

Runtime edits live in the current per-session draft. Formal archives live
under ``saves/<save_id>/`` and contain only ``manifest.json`` plus
``workspace/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.paths import (
    DRAFT_DIR,
    DRAFT_META_FILE,
    DRAFTS_DIR,
    PROJECT_ROOT,
    SESSION_ID,
    locate_project_root,
)


ACTIVE_DIRS = ("source_artifacts", "outputs", "workspace")
EMPTY_DIRS = (
    "source_artifacts",
    "source_artifacts/operator_drafts",
    "outputs",
    "outputs/artifacts",
    "outputs/run_logs",
    "outputs/checkpoints",
    "outputs/artifact_layer",
    "outputs/runtime_control",
    "outputs/execution_objects",
    "workspace",
    "workspace/projects",
    "workspace/exports",
)
ACTIVE_FILES = ("gate_log.yaml",)
_SNAPSHOT_SKIP_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".mp4",
        ".mov",
        ".avi",
        ".zip",
        ".tar",
        ".gz",
    }
)
DRAFT_RUNTIME_DIRS = ("snapshots",)
DRAFT_RUNTIME_FILES = ("draft_file_map.json", "timeline.jsonl")
INDEX_NAME = "save_index.json"
MANIFEST_NAME = "manifest.json"
LEGACY_MANIFEST_NAME = "save_manifest.json"
FORMAL_RUNTIME_ARTIFACTS = (
    "snapshots",
    "save_file_map.json",
    "timeline.jsonl",
    LEGACY_MANIFEST_NAME,
)
LEGACY_PROJECT_IDS = ("newdemotower", "Demo_tower", "DemoTower")
PROJECT_ID = "devflow"
PROJECT_DISPLAY_NAME = "程序自动开发流程工具"
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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def default_display_name() -> str:
    return f"存档_{stamp()}"


def _path_contains(root: Path, path: Path) -> bool:
    try:
        resolved_root = root.resolve()
        resolved_path = path.resolve()
    except OSError:
        return False
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _formal_root(project_root: Path) -> Path:
    root = Path(project_root)
    try:
        return locate_project_root(root)
    except RuntimeError:
        return root


def _active_root(project_root: Path) -> Path:
    root = Path(project_root)
    formal = _formal_root(root)
    if formal == PROJECT_ROOT:
        if _path_contains(DRAFTS_DIR, root):
            rel = root.resolve().relative_to(DRAFTS_DIR.resolve())
            if rel.parts:
                return DRAFTS_DIR / rel.parts[0]
        return DRAFT_DIR
    return root


def _active_meta_path(project_root: Path) -> Path:
    active = _active_root(project_root)
    if active == DRAFT_DIR:
        return DRAFT_META_FILE
    return active / "draft_meta.json"


_UNSET = object()


def _write_draft_meta(project_root: Path, *, linked_save_id: Any = _UNSET) -> None:
    active = _active_root(project_root)
    meta_path = _active_meta_path(project_root)
    existing = read_json(meta_path, {})
    if not isinstance(existing, dict):
        existing = {}
    formal = _formal_root(project_root)
    payload = {
        **existing,
        "schema_version": 1,
        "session_id": SESSION_ID if active == DRAFT_DIR else active.name,
        "pid": os.getpid(),
        "project_root": str(formal),
        "draft_root": str(active),
        "updated_at": now_iso(),
    }
    if linked_save_id is not _UNSET:
        payload["linked_save_id"] = str(linked_save_id) if linked_save_id else None
        payload["linked_archive_path"] = (
            str(save_dir(formal, linked_save_id)) if linked_save_id else ""
        )
    else:
        if "linked_save_id" not in payload:
            payload["linked_save_id"] = None
        if "linked_archive_path" not in payload:
            payload["linked_archive_path"] = ""
    write_json(meta_path, payload)


def active_root(project_root: Path = PROJECT_ROOT) -> Path:
    return _active_root(project_root)


def save_root(project_root: Path) -> Path:
    return _formal_root(project_root) / "saves"


def index_path(project_root: Path) -> Path:
    return save_root(project_root) / INDEX_NAME


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_name(value: str, fallback: str = "save") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or "").strip())
    value = re.sub(r"\s+", "_", value).strip("._ ")
    return value or fallback


def _safe_resolve_under(root: Path, path: Path) -> Path:
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    if path_resolved == root_resolved or root_resolved not in path_resolved.parents:
        raise RuntimeError(f"Refusing path outside expected root: {path}")
    return path_resolved


def _safe_remove_tree(root: Path, target: Path) -> bool:
    """Remove a directory only when the resolved target stays under root."""
    try:
        _safe_resolve_under(root, target)
        if not target.exists():
            return False
        shutil.rmtree(target)
        return True
    except Exception:
        return False


def _safe_remove_file(root: Path, target: Path) -> bool:
    """Remove a file only when the resolved target stays under root."""
    try:
        _safe_resolve_under(root, target)
        if not target.exists():
            return False
        if target.is_dir():
            return False
        target.unlink()
        return True
    except Exception:
        return False


def _linked_save_id_from_meta(meta: dict[str, Any]) -> str | None:
    direct = meta.get("linked_save_id")
    if direct:
        return str(direct)
    archive_path = str(meta.get("linked_archive_path") or "").strip()
    if archive_path:
        return Path(archive_path).name
    return None


def _draft_linked_save_id(draft: Path) -> str | None:
    meta = read_json(draft / "draft_meta.json", {})
    if not isinstance(meta, dict):
        return None
    return _linked_save_id_from_meta(meta)


def _draft_is_pruneable(draft: Path, saves_root: Path) -> bool:
    """True when the draft has no live save to protect it."""
    save_id = _draft_linked_save_id(draft)
    if save_id is None:
        return True
    return not (saves_root / save_id).is_dir()


def _drafts_root(project_root: Path) -> Path:
    return _formal_root(project_root) / "drafts"


def _is_current_draft(draft: Path) -> bool:
    try:
        return draft.resolve() == DRAFT_DIR.resolve()
    except OSError:
        return False


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _replace_legacy_text(value: str) -> str:
    updated = value
    for legacy in LEGACY_PROJECT_IDS:
        updated = updated.replace(legacy, PROJECT_ID)
    return updated


def _rewrite_legacy_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    suffixes = {".json", ".md", ".txt", ".yaml", ".yml", ".log"}
    if path.suffix.lower() not in suffixes:
        return False
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return False
    updated = _replace_legacy_text(raw)
    changed = updated != raw
    if updated != raw:
        path.write_text(updated, encoding="utf-8")
    if path.suffix.lower() == ".json":
        changed = _normalize_project_json(path) or changed
    return changed


def _normalize_project_json(path: Path) -> bool:
    data = read_json(path, None)
    if not isinstance(data, dict):
        return False
    changed = False
    if data.get("project") in LEGACY_PROJECT_IDS or data.get("project") == PROJECT_ID:
        data["project"] = PROJECT_DISPLAY_NAME
        changed = True
    if "project" in data and data.get("project_id") != PROJECT_ID:
        data["project_id"] = PROJECT_ID
        changed = True
    if changed:
        write_json(path, data)
    return changed


def _package_version_from_name(path: Path) -> int:
    match = re.search(r"_v(\d+)$", path.name)
    return int(match.group(1)) if match else 0


def _infer_source_type(path: Path) -> str:
    manifest = read_json(path / "package_manifest.json", {})
    if isinstance(manifest, dict):
        for key in ("source_id", "package_type", "package_type_id"):
            if manifest.get(key):
                return str(manifest[key])
    submission = read_json(path / "operator_submission.json", {})
    if isinstance(submission, dict):
        for key in ("source_id", "package_type", "package_type_id"):
            if submission.get(key):
                return str(submission[key])
    for marker, source_type in SOURCE_MARKERS.items():
        if (path / marker).exists():
            return source_type
    for source_type in SOURCE_MARKERS.values():
        if f"_{source_type}_" in path.name or path.name.startswith(f"{source_type}_"):
            return source_type
    return ""


def _ensure_source_package_manifests(source_root: Path) -> bool:
    if not source_root.exists() or not source_root.is_dir():
        return False
    changed = False
    for package_dir in source_root.iterdir():
        if not package_dir.is_dir() or package_dir.name in {"operator_drafts"}:
            continue
        source_type = _infer_source_type(package_dir)
        if not source_type:
            continue
        submission = read_json(package_dir / "operator_submission.json", {})
        if not isinstance(submission, dict):
            submission = {}
        manifest_path = package_dir / "package_manifest.json"
        manifest = read_json(manifest_path, {})
        if not isinstance(manifest, dict):
            manifest = {}
        updated_manifest = {
            **manifest,
            "schema_version": 1,
            "project": PROJECT_DISPLAY_NAME,
            "project_id": PROJECT_ID,
            "package_id": f"source:{source_type}",
            "package_type": source_type,
            "package_type_id": re.sub(r"[^a-z0-9]+", "", source_type.lower()),
            "source_id": source_type,
            "source_ids": [source_type],
            "stage": submission.get("step"),
            "stage_slug": submission.get("slug", ""),
            "stage_title": submission.get("title", ""),
            "created_at": submission.get("created_at") or manifest.get("created_at") or now_iso(),
            "version": manifest.get("version") or _package_version_from_name(package_dir),
        }
        if updated_manifest != manifest:
            write_json(manifest_path, updated_manifest)
            changed = True
    return changed


def _rewrite_legacy_file_refs(root: Path) -> bool:
    if not root.exists() or not root.is_dir():
        return False
    suffixes = {".json", ".md", ".txt", ".yaml", ".yml", ".log"}
    changed = False
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        changed = _rewrite_legacy_file(path) or changed
    return changed


def _rename_legacy_dirs(root: Path) -> bool:
    if not root.exists():
        return False
    dirs = sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True)
    changed = False
    for path in dirs:
        new_name = _replace_legacy_text(path.name)
        if new_name == path.name:
            continue
        changed = True
        target = path.with_name(new_name)
        if target.exists():
            for item in path.iterdir():
                dest = target / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
            shutil.rmtree(path)
        else:
            path.rename(target)
    return changed


def migrate_workspace_project_id(workspace_root: Path) -> bool:
    """Update active workspace naming. Returns True when files changed."""
    root = Path(workspace_root)
    changed = False
    for dirname in ACTIVE_DIRS:
        active_dir = root / dirname
        changed = _rename_legacy_dirs(active_dir) or changed
        changed = _rewrite_legacy_file_refs(active_dir) or changed
    for filename in ACTIVE_FILES:
        path = root / filename
        changed = _rewrite_legacy_file(path) or changed
    changed = _ensure_source_package_manifests(root / "source_artifacts") or changed
    return changed


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_index(project_root: Path) -> dict[str, Any]:
    root = _formal_root(project_root)
    data = read_json(index_path(root), {})
    saves = data.get("saves", [])
    if not isinstance(saves, list):
        saves = []
    return {
        "schema_version": 1,
        "current_save_id": data.get("current_save_id"),
        "saves": [item for item in saves if isinstance(item, dict)],
        "updated_at": data.get("updated_at", ""),
    }


def save_index(project_root: Path, data: dict[str, Any]) -> Path:
    root = _formal_root(project_root)
    data = dict(data)
    data["schema_version"] = 1
    data["updated_at"] = now_iso()
    data["saves"] = sorted(
        data.get("saves", []),
        key=lambda item: str(item.get("last_worked_at") or item.get("created_at") or ""),
        reverse=True,
    )
    return write_json(index_path(root), data)


def ensure_save_system(project_root: Path) -> dict[str, Any]:
    root = _formal_root(project_root)
    save_root(root).mkdir(parents=True, exist_ok=True)
    _active_root(project_root).mkdir(parents=True, exist_ok=True)
    data = load_index(root)
    _write_draft_meta(project_root, linked_save_id=data.get("current_save_id") or None)
    save_index(root, data)
    return data


def set_current_save(project_root: Path, save_id: str | None) -> None:
    data = ensure_save_system(project_root)
    data["current_save_id"] = save_id
    save_index(project_root, data)
    _write_draft_meta(project_root, linked_save_id=save_id)


def current_save_id(project_root: Path) -> str | None:
    value = ensure_save_system(project_root).get("current_save_id")
    return str(value) if value else None


def current_save_id_readonly(project_root: Path) -> str | None:
    """Pure read; does not initialize or write save-system metadata."""
    data = read_json(index_path(_formal_root(project_root)), {})
    value = data.get("current_save_id") if isinstance(data, dict) else None
    return str(value) if value else None


def save_dir(project_root: Path, save_id: str) -> Path:
    return save_root(_formal_root(project_root)) / save_id


def save_manifest_path(project_root: Path, save_id: str) -> Path:
    target = save_dir(project_root, save_id)
    manifest = target / MANIFEST_NAME
    if manifest.exists():
        return manifest
    legacy = target / LEGACY_MANIFEST_NAME
    return legacy if legacy.exists() else manifest


def workspace_dir(project_root: Path, save_id: str) -> Path:
    return save_dir(project_root, save_id) / "workspace"


def current_save_workspace_dir(project_root: Path) -> Path | None:
    save_id = current_save_id(project_root)
    if not save_id:
        return None
    return workspace_dir(project_root, save_id)


def _iter_active_files(project_root: Path):
    root = _active_root(project_root)
    for dirname in ACTIVE_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            yield path
    for filename in ACTIVE_FILES:
        path = root / filename
        if path.exists() and path.is_file():
            yield path


def workspace_has_state(project_root: Path) -> bool:
    for path in _iter_active_files(project_root):
        if path.name == ".gitkeep":
            continue
        if path.exists():
            return True
    return False


def clear_active_workspace(project_root: Path) -> None:
    root = _active_root(project_root)
    for dirname in ACTIVE_DIRS:
        target = root / dirname
        _safe_resolve_under(root, target)
        if target.exists():
            shutil.rmtree(target)
    for filename in ACTIVE_FILES:
        target = root / filename
        _safe_resolve_under(root, target)
        if target.exists():
            target.unlink()
    for dirname in DRAFT_RUNTIME_DIRS:
        target = root / dirname
        _safe_resolve_under(root, target)
        if target.exists():
            shutil.rmtree(target)
    for filename in DRAFT_RUNTIME_FILES:
        target = root / filename
        _safe_resolve_under(root, target)
        if target.exists():
            target.unlink()
    for dirname in EMPTY_DIRS:
        (root / dirname).mkdir(parents=True, exist_ok=True)


def initialize_active_workspace(project_root: Path) -> None:
    ensure_save_system(project_root)
    clear_active_workspace(project_root)
    set_current_save(project_root, None)
    _write_draft_meta(project_root, linked_save_id=None)


def reset_current_draft_outputs(project_root: Path, stage_from: int = 0) -> None:
    """Clear generated artifact outputs for stages at or after stage_from."""
    root = _active_root(project_root)
    artifacts_dir = root / "outputs" / "artifacts"
    _safe_resolve_under(root, artifacts_dir)
    if not artifacts_dir.exists():
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return
    if stage_from <= 0:
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return
    for stage_dir in sorted(artifacts_dir.iterdir()):
        if not stage_dir.is_dir():
            continue
        match = re.fullmatch(r"stage_(\d+)", stage_dir.name)
        if match and int(match.group(1)) >= stage_from:
            _safe_remove_tree(artifacts_dir, stage_dir)


def prune_sibling_draft_outputs(project_root: Path, stage_from: int = 0) -> list[str]:
    """Clear artifact outputs from non-current drafts linked to the active save."""
    save_id = current_save_id(project_root)
    if not save_id:
        return []
    drafts_root = _drafts_root(project_root)
    if not drafts_root.exists():
        return []

    pruned: list[str] = []
    for draft in sorted(drafts_root.iterdir(), key=lambda path: path.name):
        if not draft.is_dir() or _is_current_draft(draft):
            continue
        if _draft_linked_save_id(draft) != save_id:
            continue
        artifacts_dir = draft / "outputs" / "artifacts"
        if not artifacts_dir.exists():
            continue
        if stage_from <= 0:
            if _safe_remove_tree(draft, artifacts_dir):
                pruned.append(draft.name)
            continue
        removed = False
        for stage_dir in sorted(artifacts_dir.iterdir()):
            if not stage_dir.is_dir():
                continue
            match = re.fullmatch(r"stage_(\d+)", stage_dir.name)
            if match and int(match.group(1)) >= stage_from:
                removed = _safe_remove_tree(artifacts_dir, stage_dir) or removed
        if removed:
            pruned.append(draft.name)
    return pruned


def prune_old_drafts(project_root: Path, keep_count: int = 5) -> list[str]:
    """Delete oldest pruneable draft directories (unlinked or orphaned saves)."""
    drafts_root = _drafts_root(project_root)
    if not drafts_root.exists():
        return []
    keep_count = max(0, int(keep_count))
    saves_root = save_root(_formal_root(project_root))
    drafts = sorted(
        (path for path in drafts_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )
    candidates = [draft for draft in drafts if not _is_current_draft(draft)]
    pruneable = [draft for draft in candidates if _draft_is_pruneable(draft, saves_root)]
    to_delete = pruneable[: max(0, len(pruneable) - keep_count)]

    deleted: list[str] = []
    for draft in to_delete:
        if _safe_remove_tree(drafts_root, draft):
            deleted.append(draft.name)
    return deleted


def prune_draft_snapshots(project_root: Path, keep_per_draft: int = 0) -> list[str]:
    """Delete snapshot directories from pruneable drafts to reclaim space.

    keep_per_draft=0 removes all snapshots from pruneable drafts.
    Live (non-pruneable) drafts are not touched.
    """
    drafts_root = _drafts_root(project_root)
    if not drafts_root.exists():
        return []
    saves_root = save_root(_formal_root(project_root))
    pruned: list[str] = []
    for draft in sorted(drafts_root.iterdir(), key=lambda p: p.name):
        if not draft.is_dir() or _is_current_draft(draft):
            continue
        if not _draft_is_pruneable(draft, saves_root):
            continue
        snap_dir = draft / "snapshots"
        if not snap_dir.exists():
            continue
        if keep_per_draft <= 0:
            if _safe_remove_tree(draft, snap_dir):
                pruned.append(draft.name)
        else:
            snaps = sorted(snap_dir.iterdir(), key=lambda p: p.name)
            removed = False
            for snap in snaps[: max(0, len(snaps) - keep_per_draft)]:
                if snap.is_dir():
                    removed = _safe_remove_tree(snap_dir, snap) or removed
                else:
                    snap.unlink(missing_ok=True)
                    removed = True
            if removed:
                pruned.append(draft.name)
    return pruned


def _prune_drafts_linked_to(project_root: Path, save_id: str) -> list[str]:
    drafts_root = _drafts_root(project_root)
    if not drafts_root.exists():
        return []
    deleted: list[str] = []
    for draft in sorted(drafts_root.iterdir(), key=lambda path: path.name):
        if not draft.is_dir() or _is_current_draft(draft):
            continue
        if _draft_linked_save_id(draft) != save_id:
            continue
        if _safe_remove_tree(drafts_root, draft):
            deleted.append(draft.name)
    return deleted


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _fingerprint_dir(workspace_root: Path) -> str:
    """SHA256 of sorted 'relpath:sha256' lines. Returns empty string for blank workspace."""
    parts = []
    for dirn in ACTIVE_DIRS:
        base = workspace_root / dirn
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if path.name == ".gitkeep":
                continue
            parts.append(f"{_rel(path, workspace_root)}:{_sha256(path)}")
    if not parts:
        return ""
    return hashlib.sha256("\n".join(sorted(parts)).encode()).hexdigest()


def compute_workspace_fingerprint(project_root: Path) -> str:
    """Content fingerprint of the current draft workspace."""
    return _fingerprint_dir(_active_root(project_root))


def compute_save_fingerprint(project_root: Path, save_id: str) -> str:
    """Content fingerprint of a formal archive's workspace."""
    return _fingerprint_dir(workspace_dir(project_root, save_id))


LOCK_FILENAME = ".archive_lock"


def _lock_path(project_root: Path, save_id: str) -> Path:
    return save_dir(project_root, save_id) / LOCK_FILENAME


def acquire_archive_lock(project_root: Path, save_id: str) -> bool:
    """Write a lock file. Returns False if already held by another live process."""
    path = _lock_path(project_root, save_id)
    if path.exists():
        data = read_json(path, {})
        pid = int(data.get("pid") or 0)
        if pid and pid != os.getpid() and _pid_alive(pid):
            return False
    write_json(path, {"pid": os.getpid(), "session_id": SESSION_ID, "acquired_at": now_iso()})
    return True


def release_archive_lock(project_root: Path, save_id: str) -> None:
    path = _lock_path(project_root, save_id)
    if not path.exists():
        return
    data = read_json(path, {})
    if data.get("pid") == os.getpid():
        try:
            path.unlink()
        except OSError:
            pass


def release_current_lock(project_root: Path) -> None:
    save_id = current_save_id(project_root)
    if save_id:
        release_archive_lock(project_root, save_id)


def _stage_from_path(rel_path: str) -> int | None:
    match = re.search(r"outputs/artifacts/stage_(\d{2})/", rel_path.replace("\\", "/"))
    return int(match.group(1)) if match else None


def _stage_reference_data(project_root: Path, step: int) -> dict[str, Any]:
    stage_dir = _active_root(project_root) / "outputs" / "artifacts" / f"stage_{step:02d}"
    return read_json(stage_dir / "reference_manifest.json", {})


def _file_role_from_reference(project_root: Path, rel_path: str, step: int | None) -> tuple[str, str, str]:
    if step is None:
        if rel_path.startswith("source_artifacts/"):
            return "source_artifact", "", ""
        if rel_path.startswith("outputs/execution_objects/"):
            return "execution_object_store", "", ""
        if rel_path == "gate_log.yaml":
            return "gate_log", "", ""
        return "workspace_file", "", ""

    reference = _stage_reference_data(project_root, step)
    ref_path = f"outputs/artifacts/stage_{step:02d}/reference_manifest.json"
    artifacts = reference.get("artifacts", []) if isinstance(reference, dict) else []
    artifact_ids = ",".join(
        str(item.get("id"))
        for item in artifacts
        if isinstance(item, dict) and item.get("id")
    )
    files = reference.get("files", []) if isinstance(reference, dict) else []
    for item in files:
        if isinstance(item, dict) and item.get("stage_path") == rel_path:
            return str(item.get("role", "stage_file")), artifact_ids, ref_path
    if rel_path.endswith("/UPSTREAM_REFERENCE.json"):
        return "upstream_reference", artifact_ids, ref_path
    return "stage_file", artifact_ids, ref_path


def _file_map_entry(
    project_root: Path,
    path: Path,
    rel_path: str,
    *,
    transaction_seq: int | None,
    prev_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stat = path.stat()
    cached_sha256 = None
    if (
        prev_entry
        and prev_entry.get("mtime_ns") == stat.st_mtime_ns
        and prev_entry.get("size_bytes") == stat.st_size
        and prev_entry.get("sha256")
    ):
        cached_sha256 = prev_entry["sha256"]

    stage = _stage_from_path(rel_path)
    role, artifact_id, reference_manifest = _file_role_from_reference(project_root, rel_path, stage)
    if rel_path.startswith("source_artifacts/"):
        source_type = "source_artifact"
    elif rel_path.startswith("outputs/execution_objects/"):
        source_type = "execution_object_store"
    elif rel_path.startswith("outputs/"):
        source_type = "run_output"
    elif rel_path == "gate_log.yaml":
        source_type = "gate_log"
    else:
        source_type = "workspace_file"
    return {
        "workspace_path": rel_path,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": cached_sha256 or _sha256(path),
        "stage": stage,
        "artifact_id": artifact_id,
        "role": role,
        "source_type": source_type,
        "reference_manifest": reference_manifest,
        "latest_transaction_seq": transaction_seq,
    }


def build_file_map(project_root: Path, *, transaction_seq: int | None = None) -> dict[str, Any]:
    root = _active_root(project_root)
    previous = read_json(root / "draft_file_map.json", {})
    prev_by_path = {
        str(item.get("workspace_path")): item
        for item in previous.get("files", [])
        if isinstance(item, dict) and item.get("workspace_path") and item.get("mtime_ns")
    } if isinstance(previous, dict) else {}
    files = []
    for path in _iter_active_files(root):
        try:
            rel_path = _rel(path, root)
            files.append(_file_map_entry(
                root,
                path,
                rel_path,
                transaction_seq=transaction_seq,
                prev_entry=prev_by_path.get(rel_path),
            ))
        except OSError as exc:
            files.append({
                "workspace_path": _rel(path, root),
                "error": str(exc),
                "latest_transaction_seq": transaction_seq,
            })
    current = current_save_id(project_root)
    if current:
        store_path = workspace_dir(project_root, current) / _execution_object_store_relpath()
        if store_path.is_file():
            rel_path = _execution_object_store_relpath().as_posix()
            files = [item for item in files if item.get("workspace_path") != rel_path]
            files.append(_file_map_entry(
                root,
                store_path,
                rel_path,
                transaction_seq=transaction_seq,
                prev_entry=prev_by_path.get(rel_path),
            ))
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "transaction_seq": transaction_seq,
        "files": sorted(files, key=lambda item: item["workspace_path"]),
    }


def _file_map_by_path(file_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = file_map.get("files", []) if isinstance(file_map, dict) else []
    return {
        str(item.get("workspace_path")): item
        for item in files
        if isinstance(item, dict) and item.get("workspace_path")
    }


def _delta(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    old = _file_map_by_path(previous)
    new = _file_map_by_path(current)
    added = [new[path] for path in sorted(set(new) - set(old))]
    removed = [old[path] for path in sorted(set(old) - set(new))]
    modified = []
    for path in sorted(set(old) & set(new)):
        if old[path].get("sha256") != new[path].get("sha256"):
            modified.append({"before": old[path], "after": new[path]})
    return {"added": added, "modified": modified, "removed": removed}


def _copy_active_to(project_root: Path, dest_root: Path) -> None:
    root = _active_root(project_root)
    migrate_workspace_project_id(root)
    dest_root.mkdir(parents=True, exist_ok=True)
    for dirname in ACTIVE_DIRS:
        src = root / dirname
        dest = dest_root / dirname
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest)
        else:
            dest.mkdir(parents=True, exist_ok=True)
    for filename in ACTIVE_FILES:
        src = root / filename
        dest = dest_root / filename
        if dest.exists():
            dest.unlink()
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    for dirname in EMPTY_DIRS:
        (dest_root / dirname).mkdir(parents=True, exist_ok=True)


def _snapshot_ignore(_dirname: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if Path(name).suffix.lower() in _SNAPSHOT_SKIP_SUFFIXES
    }


def _copy_active_to_snapshot(project_root: Path, dest_root: Path) -> None:
    root = _active_root(project_root)
    migrate_workspace_project_id(root)
    dest_root.mkdir(parents=True, exist_ok=True)
    for dirname in ACTIVE_DIRS:
        src = root / dirname
        dest = dest_root / dirname
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest, ignore=_snapshot_ignore)
        else:
            dest.mkdir(parents=True, exist_ok=True)
    for filename in ACTIVE_FILES:
        src = root / filename
        dest = dest_root / filename
        if dest.exists():
            dest.unlink()
        if src.exists() and src.suffix.lower() not in _SNAPSHOT_SKIP_SUFFIXES:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    for dirname in EMPTY_DIRS:
        (dest_root / dirname).mkdir(parents=True, exist_ok=True)


def _copy_workspace_to_active(project_root: Path, source_root: Path) -> bool:
    clear_active_workspace(project_root)
    root = _active_root(project_root)
    for dirname in ACTIVE_DIRS:
        src = source_root / dirname
        dest = root / dirname
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest)
        else:
            dest.mkdir(parents=True, exist_ok=True)
    for filename in ACTIVE_FILES:
        src = source_root / filename
        dest = root / filename
        if dest.exists():
            dest.unlink()
        if src.exists():
            shutil.copy2(src, dest)
    for dirname in EMPTY_DIRS:
        (root / dirname).mkdir(parents=True, exist_ok=True)
    return migrate_workspace_project_id(root)


def _execution_object_store_relpath() -> Path:
    return Path("outputs") / "execution_objects" / "execution_objects.json"


def _read_authoritative_execution_object_store(save_workspace: Path) -> str | None:
    path = save_workspace / _execution_object_store_relpath()
    if not path.exists() or not path.is_file():
        return None
    return path.read_text(encoding="utf-8-sig")


def _write_authoritative_execution_object_store(dest_root: Path, content: str | None) -> None:
    if content is None:
        return
    path = dest_root / _execution_object_store_relpath()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _transfer_execution_object_store_ownership(
    workspace_root: Path,
    *,
    new_save_id: str,
    source_save_id: str | None,
    reason: str,
) -> bool:
    path = Path(workspace_root) / _execution_object_store_relpath()
    if not path.is_file():
        return False

    from core.engines.execution_objects.workflow import ExecutionObjectStore

    store = ExecutionObjectStore(path, expected_save_id=None)
    existing_save_id = str(store.data.get("save_id") or "").strip() or None
    new_save_id = str(new_save_id or "").strip()
    if existing_save_id == new_save_id:
        return False
    record = store.transfer_ownership_to_save(
        new_save_id,
        source_save_id=source_save_id,
        reason=reason,
    )
    store.save()
    append_jsonl(Path(workspace_root) / "timeline.jsonl", {
        "event": "execution_object_store_ownership_transferred",
        "from_save_id": record.get("from_save_id"),
        "to_save_id": record.get("to_save_id"),
        "reason": record.get("reason"),
        "timestamp": record.get("at"),
    })
    return True


def _atomic_copy_to_workspace(project_root: Path, target: Path, authoritative_store: str | None) -> None:
    """Write active state into target/workspace via temp-dir rename (atomic on same drive)."""
    ws = target / "workspace"
    tmp = target / "_workspace_tmp"
    old = target / "_workspace_old"
    for leftover in (tmp, old):
        if leftover.exists():
            shutil.rmtree(leftover)
    _copy_active_to(project_root, tmp)
    _write_authoritative_execution_object_store(tmp, authoritative_store)
    if ws.exists():
        ws.rename(old)
    try:
        tmp.rename(ws)
        if old.exists():
            shutil.rmtree(old)
    except Exception:
        if old.exists() and not ws.exists():
            old.rename(ws)
        raise
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


def _next_seq(manifest: dict[str, Any]) -> int:
    return int(manifest.get("last_transaction_seq") or 0) + 1


def _progress_from_workspace_root(root: Path) -> dict[str, Any]:
    from core.registry import max_step_number

    root = Path(root)
    passed = 0
    final_step = max_step_number()
    total = final_step + 1
    for step in range(final_step + 1):
        stage = root / "outputs" / "artifacts" / f"stage_{step:02d}"
        validation = read_json(stage / "validation_report.json", {})
        reviews = read_json(stage / "artifact_reviews.json", {})
        layer = read_json(stage / "artifact_validation_layer.json", {})
        primary = stage / (
            "migration_audit.json" if step == final_step else "artifact_index.json"
        )
        reference = stage / "reference_manifest.json"
        if (
            validation.get("status") == "success"
            and validation.get("valid") is True
            and reviews.get("status") == "success"
            and layer.get("status") == "success"
            and primary.exists()
            and reference.exists()
        ):
            passed += 1
    return {"passed": passed, "total": total, "label": f"已通过 {passed}/{total}"}


def _progress(project_root: Path) -> dict[str, Any]:
    return _progress_from_workspace_root(_active_root(project_root))


def _load_manifest(path: Path) -> dict[str, Any]:
    data = read_json(path, {})
    return data if isinstance(data, dict) else {}


def _save_entry(manifest: dict[str, Any]) -> dict[str, Any]:
    from core.registry import max_step_number

    total = max_step_number() + 1
    return {
        "save_id": manifest["save_id"],
        "display_name": manifest["display_name"],
        "save_type": manifest.get("save_type", "manual"),
        "created_by": manifest.get("created_by", ""),
        "reason": manifest.get("reason", ""),
        "path": f"saves/{manifest['save_id']}",
        "created_at": manifest.get("created_at", ""),
        "last_worked_at": manifest.get("last_worked_at", ""),
        "progress": manifest.get(
            "progress", {"passed": 0, "total": total, "label": f"已通过 0/{total}"}
        ),
    }


def _replace_entry(project_root: Path, manifest: dict[str, Any], *, current: bool | None = None) -> None:
    data = ensure_save_system(project_root)
    saves = [item for item in data["saves"] if item.get("save_id") != manifest["save_id"]]
    saves.append(_save_entry(manifest))
    data["saves"] = saves
    if current is True:
        data["current_save_id"] = manifest["save_id"]
    elif current is False and data.get("current_save_id") == manifest["save_id"]:
        data["current_save_id"] = None
    save_index(project_root, data)


def _display_names(project_root: Path) -> set[str]:
    return {str(item.get("display_name")) for item in ensure_save_system(project_root)["saves"]}


def unique_display_name(project_root: Path, requested: str | None = None) -> str:
    name = (requested or default_display_name()).strip() or default_display_name()
    existing = _display_names(project_root)
    if name not in existing:
        return name
    return f"{name}_重复_{stamp()}"


def new_save_id() -> str:
    return f"save_{stamp()}_{secrets.token_hex(3)}"


def _blank_progress() -> dict[str, Any]:
    from core.registry import max_step_number

    total = max_step_number() + 1
    return {"passed": 0, "total": total, "label": f"已通过 0/{total}"}


def _reset_active_for_blank_save(project_root: Path) -> None:
    root = _active_root(project_root)
    for relative in (
        Path("outputs") / "artifacts",
        Path("outputs") / "checkpoints",
        Path("outputs") / "run_logs",
        Path("outputs") / "runtime_control",
        Path("outputs") / "artifact_layer",
        Path("outputs") / "execution_objects" / "execution_objects.json",
        Path("workspace"),
        Path("snapshots"),
        Path("draft_file_map.json"),
        Path("timeline.jsonl"),
        Path("gate_log.yaml"),
    ):
        target = root / relative
        if target.is_dir():
            _safe_remove_tree(root, target)
        else:
            _safe_remove_file(root, target)

    source_root = root / "source_artifacts"
    if source_root.is_dir():
        for path in sorted(source_root.glob("devflow_*")):
            if path.is_dir():
                _safe_remove_tree(root, path)
            else:
                _safe_remove_file(root, path)

    for dirname in EMPTY_DIRS:
        (root / dirname).mkdir(parents=True, exist_ok=True)


def create_save(
    project_root: Path,
    display_name: str | None = None,
    *,
    save_type: str = "manual",
    created_by: str = "user",
    reason: str = "",
    event: str = "create_save",
) -> dict[str, Any]:
    from core.registry import max_step_number

    root = _formal_root(project_root)
    ensure_save_system(root)
    source_save_id = current_save_id(root)
    save_id = new_save_id()
    while save_dir(root, save_id).exists():
        save_id = new_save_id()
    name = unique_display_name(root, display_name)
    created_at = now_iso()
    total = max_step_number() + 1
    manifest = {
        "schema_version": 1,
        "save_id": save_id,
        "display_name": name,
        "save_type": save_type,
        "created_by": created_by,
        "reason": reason,
        "created_at": created_at,
        "last_worked_at": created_at,
        "last_transaction_seq": 0,
        "progress": {"passed": 0, "total": total, "label": f"已通过 0/{total}"},
    }
    target = save_dir(root, save_id)
    (target / "workspace").mkdir(parents=True, exist_ok=True)
    write_json(target / MANIFEST_NAME, manifest)
    _replace_entry(root, manifest, current=True)
    _transfer_execution_object_store_ownership(
        _active_root(project_root),
        new_save_id=save_id,
        source_save_id=source_save_id,
        reason=event,
    )
    sync_current_save(project_root, event=event)
    return _load_manifest(target / MANIFEST_NAME)


def create_blank_save(
    project_root: Path,
    display_name: str | None = None,
    *,
    save_type: str = "manual",
    created_by: str = "user",
    reason: str = "",
    event: str = "create_blank_save",
) -> dict[str, Any]:
    root = _formal_root(project_root)
    ensure_save_system(root)
    save_id = new_save_id()
    while save_dir(root, save_id).exists():
        save_id = new_save_id()
    name = unique_display_name(root, display_name)
    created_at = now_iso()
    manifest = {
        "schema_version": 1,
        "save_id": save_id,
        "display_name": name,
        "save_type": save_type,
        "created_by": created_by,
        "reason": reason,
        "created_at": created_at,
        "last_worked_at": created_at,
        "last_transaction_seq": 0,
        "progress": _blank_progress(),
    }
    target = save_dir(root, save_id)
    (target / "workspace").mkdir(parents=True, exist_ok=True)
    write_json(target / MANIFEST_NAME, manifest)
    _replace_entry(root, manifest, current=True)
    _reset_active_for_blank_save(project_root)
    sync_current_save(project_root, event=event)
    return _load_manifest(target / MANIFEST_NAME)


def get_save(project_root: Path, save_id: str) -> dict[str, Any] | None:
    path = save_manifest_path(project_root, save_id)
    if not path.exists():
        return None
    data = _load_manifest(path)
    return data if data.get("save_id") else None


def list_saves(project_root: Path) -> list[dict[str, Any]]:
    ensure_save_system(project_root)
    result = []
    for entry in load_index(project_root)["saves"]:
        manifest = get_save(project_root, str(entry.get("save_id")))
        if manifest:
            result.append(_save_entry(manifest))
    return sorted(result, key=lambda item: str(item.get("last_worked_at") or ""), reverse=True)


def ensure_current_save(project_root: Path, display_name: str | None = None) -> dict[str, Any]:
    current = current_save_id(project_root)
    if current:
        manifest = get_save(project_root, current)
        if manifest:
            return manifest
    return create_save(project_root, display_name or default_display_name(), event="auto_create_save")


def _snapshot_name(seq: int, event: str) -> str:
    return f"{seq:06d}_{_safe_name(event, 'event')}"


def _remove_formal_runtime_artifacts(save_path: Path) -> None:
    for name in FORMAL_RUNTIME_ARTIFACTS:
        path = save_path / name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _trim_current_draft_snapshots(draft: Path, keep: int = 5) -> None:
    snap_dir = draft / "snapshots"
    if not snap_dir.exists():
        return
    snaps = sorted((path for path in snap_dir.iterdir() if path.is_dir()), key=lambda path: path.name)
    for old in snaps[: max(0, len(snaps) - keep)]:
        _safe_remove_tree(snap_dir, old)


def sync_current_save(
    project_root: Path,
    *,
    event: str,
    stage: int | None = None,
    message: str = "",
) -> dict[str, Any]:
    root = _formal_root(project_root)
    active = _active_root(project_root)
    save_id = current_save_id(root)
    if not save_id:
        raise RuntimeError("No current save is bound.")
    target = save_dir(root, save_id)
    manifest_path = save_manifest_path(root, save_id)
    manifest = _load_manifest(manifest_path)
    if not manifest:
        raise RuntimeError(f"Missing save manifest for {save_id}")

    migrate_workspace_project_id(active)
    draft_file_map = active / "draft_file_map.json"
    previous_map = read_json(draft_file_map, {"files": []})
    seq = _next_seq(manifest)
    current_map = build_file_map(project_root, transaction_seq=seq)
    delta = _delta(previous_map, current_map)

    ws = workspace_dir(root, save_id)
    authoritative_execution_object_store = _read_authoritative_execution_object_store(ws)
    _atomic_copy_to_workspace(project_root, target, authoritative_execution_object_store)
    _remove_formal_runtime_artifacts(target)

    snapshot_root = active / "snapshots" / _snapshot_name(seq, event)
    full_root = snapshot_root / "full"
    delta_root = snapshot_root / "delta"
    _copy_active_to_snapshot(project_root, full_root)
    _write_authoritative_execution_object_store(full_root, authoritative_execution_object_store)
    write_json(delta_root / "added.json", delta["added"])
    write_json(delta_root / "modified.json", delta["modified"])
    write_json(delta_root / "removed.json", delta["removed"])
    snapshot_manifest = {
        "schema_version": 1,
        "seq": seq,
        "event": event,
        "stage": stage,
        "timestamp": now_iso(),
        "message": message,
        "file_count": len(current_map["files"]),
        "added": len(delta["added"]),
        "modified": len(delta["modified"]),
        "removed": len(delta["removed"]),
    }
    write_json(snapshot_root / "snapshot_manifest.json", snapshot_manifest)
    write_json(snapshot_root / "snapshot_file_map.json", current_map)
    write_json(draft_file_map, current_map)

    progress = _progress(project_root)
    manifest.update({
        "last_worked_at": now_iso(),
        "last_transaction_seq": seq,
        "progress": progress,
    })
    write_json(target / MANIFEST_NAME, manifest)
    if manifest_path.name == LEGACY_MANIFEST_NAME and manifest_path.exists():
        manifest_path.unlink()
    append_jsonl(active / "timeline.jsonl", {
        "seq": seq,
        "event": event,
        "stage": stage,
        "timestamp": now_iso(),
        "message": message,
        "progress": progress,
    })
    _replace_entry(root, manifest, current=True)
    _write_draft_meta(project_root, linked_save_id=save_id)
    _trim_current_draft_snapshots(active, keep=5)
    return manifest


def retry_sync(
    project_root: Path,
    *,
    event: str,
    stage: int | None = None,
    message: str = "",
    attempts: int = 10,
    delay_seconds: int = 3,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = log or (lambda text: None)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return sync_current_save(project_root, event=event, stage=stage, message=message)
        except Exception as exc:  # noqa: BLE001 - retry boundary
            last_exc = exc
            log(f"Save sync failed ({attempt}/{attempts}): {exc}\n")
            if attempt < attempts:
                time.sleep(delay_seconds)
    raise RuntimeError(f"Save sync failed after {attempts} attempts: {last_exc}")


def save_current_as(project_root: Path, display_name: str | None = None) -> dict[str, Any]:
    manifest = create_save(project_root, display_name or default_display_name(), event="manual_save_new")
    return manifest


def overwrite_save(project_root: Path, save_id: str, *, event: str = "manual_save_overwrite") -> dict[str, Any]:
    if not get_save(project_root, save_id):
        raise RuntimeError(f"Unknown save id: {save_id}")
    set_current_save(project_root, save_id)
    return sync_current_save(project_root, event=event)


def _load_save_lightweight(
    project_root: Path,
    root: Path,
    save_id: str,
    manifest: dict[str, Any],
    active: Path,
) -> dict[str, Any]:
    """Load bookkeeping when active workspace already equals the archive."""
    seq = _next_seq(manifest)
    progress = manifest.get("progress") or _progress(project_root)
    manifest.update({
        "last_worked_at": now_iso(),
        "last_transaction_seq": seq,
        "progress": progress,
    })
    target = save_dir(root, save_id)
    write_json(target / MANIFEST_NAME, manifest)
    append_jsonl(active / "timeline.jsonl", {
        "seq": seq,
        "event": "load_save",
        "stage": None,
        "timestamp": now_iso(),
        "message": "fast path: no migration changes",
        "progress": progress,
    })
    _replace_entry(root, manifest, current=True)
    _write_draft_meta(project_root, linked_save_id=save_id)
    return manifest


def load_save(project_root: Path, save_id: str) -> dict[str, Any]:
    root = _formal_root(project_root)
    manifest = get_save(root, save_id)
    if not manifest:
        raise RuntimeError(f"Unknown save id: {save_id}")
    ws = workspace_dir(root, save_id)
    if not ws.exists():
        raise RuntimeError(f"Save workspace is missing: {save_id}")
    if not acquire_archive_lock(root, save_id):
        raise RuntimeError(f"Archive is already open in another window: {save_id}")
    migration_changed = _copy_workspace_to_active(project_root, ws)
    set_current_save(root, save_id)
    active = _active_root(project_root)
    if migration_changed:
        return sync_current_save(project_root, event="load_save_migrated")
    return _load_save_lightweight(project_root, root, save_id, manifest, active)


def delete_save(project_root: Path, save_id: str) -> None:
    root = _formal_root(project_root)
    target = save_dir(root, save_id)
    save_root_resolved = save_root(root).resolve()
    target_resolved = target.resolve()
    if save_root_resolved not in target_resolved.parents:
        raise RuntimeError(f"Refusing to delete outside save root: {target}")
    if target.exists():
        shutil.rmtree(target)
    data = ensure_save_system(root)
    data["saves"] = [item for item in data["saves"] if item.get("save_id") != save_id]
    if data.get("current_save_id") == save_id:
        data["current_save_id"] = None
    save_index(root, data)
    _prune_drafts_linked_to(root, save_id)


def delete_all_saves(project_root: Path) -> list[str]:
    root = _formal_root(project_root)
    data = ensure_save_system(root)
    save_root_resolved = save_root(root).resolve()
    deleted: list[str] = []
    for entry in list(data.get("saves", [])):
        save_id = str(entry.get("save_id") or "")
        if not save_id:
            continue
        target = save_dir(root, save_id)
        try:
            target_resolved = target.resolve()
        except OSError:
            continue
        if save_root_resolved not in target_resolved.parents:
            continue
        if target.exists():
            shutil.rmtree(target)
        _prune_drafts_linked_to(root, save_id)
        deleted.append(save_id)
    data["saves"] = []
    data["current_save_id"] = None
    save_index(root, data)
    _write_draft_meta(project_root, linked_save_id=None)
    return deleted
