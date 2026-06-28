import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from core.design.data_loader import data_dir, runtime_project_root
from core.design.profile_schema import PROFILE_OPTION_LABELS, option_label


TEMPLATE_SCHEMA_VERSION = "0.1.0"
TEMPLATE_INDEX_FILE = "template_index.json"
BUILTIN_PREFIX = "builtin_"
CUSTOM_PREFIX = "custom_"
TEMPLATE_SOURCE_LABELS = {
    "builtin": "内置",
    "custom": "自定义",
}
SCALE_ORDER = ["iaa_hypercasual", "indie", "midcore", "3a", "large_service"]


def bundled_template_dir():
    return data_dir() / "project_templates"


def writable_template_dir():
    return runtime_project_root() / "workspace" / "projects" / "templates"


def ensure_writable_template_dir():
    target = writable_template_dir()
    target.mkdir(parents=True, exist_ok=True)
    return target


def template_dirs():
    dirs = []
    bundled = bundled_template_dir()
    writable = writable_template_dir()
    if bundled.exists():
        dirs.append(bundled)
    if writable != bundled and writable.exists():
        dirs.append(writable)
    return dirs


def safe_template_slug(value, fallback="project_template"):
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", str(value).strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    return cleaned or fallback


def template_filename(source, target_scale, name):
    prefix = CUSTOM_PREFIX if source == "custom" else BUILTIN_PREFIX
    return f"{prefix}{target_scale}_{safe_template_slug(name)}.json"


def source_from_filename(path):
    name = Path(path).name
    if name.startswith(BUILTIN_PREFIX):
        return "builtin"
    if name.startswith(CUSTOM_PREFIX):
        return "custom"
    return "custom"


def normalize_template_payload(payload, path=None):
    payload = deepcopy(payload or {})
    payload.setdefault("schemaVersion", TEMPLATE_SCHEMA_VERSION)
    meta = payload.setdefault("template", {})
    if path:
        meta.setdefault("fileName", Path(path).name)
        meta.setdefault("source", source_from_filename(path))
    meta.setdefault("source", "custom")
    meta.setdefault("id", Path(path).stem if path else safe_template_slug(meta.get("name", "")))
    meta.setdefault("name", meta.get("gameName") or meta.get("id", "未命名模板"))
    meta.setdefault("gameName", meta.get("name", ""))
    meta.setdefault("targetScale", payload.get("projectState", {}).get("profile", {}).get("targetScale", "unknown"))
    meta.setdefault("qualityTier", "custom" if meta.get("source") == "custom" else "B")
    meta.setdefault("sourceLabel", TEMPLATE_SOURCE_LABELS.get(meta.get("source"), meta.get("source", "")))
    meta.setdefault("scaleLabel", option_label("targetScale", meta.get("targetScale", "unknown")))
    meta.setdefault("summary", "")
    meta.setdefault("analysis", [])
    meta.setdefault("verification", {})
    payload.setdefault("projectState", {})
    return payload


def load_template_file(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize_template_payload(payload, path)


def list_project_templates(include_internal=False):
    templates = {}
    for directory in template_dirs():
        for path in sorted(directory.glob("*.json")):
            if path.name == TEMPLATE_INDEX_FILE:
                continue
            payload = load_template_file(path)
            meta = payload["template"]
            if not include_internal and meta.get("visibility") == "internal":
                continue
            meta["path"] = str(path)
            key = path.name
            if key not in templates or meta.get("source") == "custom":
                templates[key] = payload

    def sort_key(payload):
        meta = payload.get("template", {})
        source_rank = 0 if meta.get("source") == "builtin" else 1
        scale = meta.get("targetScale", "")
        scale_rank = SCALE_ORDER.index(scale) if scale in SCALE_ORDER else 99
        return (scale_rank, source_rank, meta.get("order", 999), meta.get("name", ""))

    return sorted(templates.values(), key=sort_key)


def find_template_by_id(template_id):
    for payload in list_project_templates():
        if payload.get("template", {}).get("id") == template_id:
            return payload
    return None


def build_custom_template_payload(name, target_scale, project_state):
    state = deepcopy(project_state)
    state.pop("aiInterview", None)
    profile = state.setdefault("profile", {})
    profile["targetScale"] = target_scale
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "schemaVersion": TEMPLATE_SCHEMA_VERSION,
        "template": {
            "id": f"custom_{target_scale}_{safe_template_slug(name)}",
            "source": "custom",
            "sourceLabel": "自定义",
            "name": name,
            "gameName": name,
            "targetScale": target_scale,
            "scaleLabel": option_label("targetScale", target_scale),
            "qualityTier": "custom",
            "summary": "用户从当前项目另存的自定义模板。",
            "analysis": [
                "该模板来自用户当前项目状态，不代表市场范本或官方配置。",
            ],
            "verification": {
                "mode": "user_saved",
                "createdAt": now,
                "runtimeNetwork": "none",
            },
            "createdAt": now,
            "updatedAt": now,
        },
        "projectState": state,
    }


def custom_template_path(name, target_scale):
    return ensure_writable_template_dir() / template_filename("custom", target_scale, name)


def matching_builtin_path(name, target_scale):
    filename = template_filename("builtin", target_scale, name)
    for directory in template_dirs():
        path = directory / filename
        if path.exists():
            return path
    return None


def save_custom_template(name, target_scale, project_state):
    path = custom_template_path(name, target_scale)
    payload = build_custom_template_payload(name, target_scale, project_state)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def delete_custom_template(name: str, target_scale: str) -> bool:
    path = custom_template_path(name, target_scale)
    if path.exists() and path.name.startswith(CUSTOM_PREFIX):
        path.unlink()
        return True
    return False


def target_scale_options():
    values = []
    labels = PROFILE_OPTION_LABELS.get("targetScale", {})
    for value in SCALE_ORDER:
        values.append((value, labels.get(value, value)))
    return values
