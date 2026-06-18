"""Entity schema registry and lightweight validation for ADR 0009 L5 cards."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path


def runtime_project_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundled_data_dir():
    bundle_root = Path(getattr(sys, "_MEIPASS", runtime_project_root()))
    design_data = bundle_root / "data" / "design"
    return design_data if design_data.exists() else bundle_root / "data"


def data_dir():
    local_data = runtime_project_root() / "data" / "design"
    if local_data.exists():
        return local_data
    legacy_data = runtime_project_root() / "data"
    if (legacy_data / "entity_schemas").exists():
        return legacy_data
    return bundled_data_dir()


def entity_schemas_dir():
    return data_dir() / "entity_schemas"


@dataclass(frozen=True)
class ValidationError:
    path: str
    message: str
    schema_id: str = ""

    def __str__(self):
        prefix = f"{self.schema_id}: " if self.schema_id else ""
        return f"{prefix}{self.path}: {self.message}"


class EntitySchemaRegistry:
    def __init__(self, schema_dir=None):
        self.schema_dir = Path(schema_dir) if schema_dir else entity_schemas_dir()
        self.schemas_by_id = {}
        self.schemas_by_key = {}
        self.load()

    def load(self):
        self.schemas_by_id.clear()
        self.schemas_by_key.clear()
        if not self.schema_dir.exists():
            return
        for path in sorted(self.schema_dir.glob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            schema_id = str(schema.get("id") or path.stem)
            kind = self.schema_kind(schema)
            version = self.schema_version(schema)
            schema["_schemaFile"] = str(path)
            schema["_schemaId"] = schema_id
            self.schemas_by_id[schema_id] = schema
            if kind and version:
                self.schemas_by_key[(kind, version)] = schema

    def schema_kind(self, schema):
        return str(
            schema.get("kind")
            or schema.get("properties", {}).get("kind", {}).get("const")
            or ""
        )

    def schema_version(self, schema):
        return normalize_schema_version(
            schema.get("schemaVersion")
            or schema.get("properties", {}).get("schemaVersion", {}).get("const")
            or ""
        )

    def schema_for(self, entity):
        if not isinstance(entity, dict):
            return None, [ValidationError("$", "entity must be an object")]

        schema_id = str(entity.get("schema") or "").strip()
        if schema_id and schema_id in self.schemas_by_id:
            return self.schemas_by_id[schema_id], []

        kind = str(entity.get("kind") or "").strip()
        version = normalize_schema_version(entity.get("schemaVersion") or "")
        if kind and version and (kind, version) in self.schemas_by_key:
            return self.schemas_by_key[(kind, version)], []

        if schema_id:
            return None, [ValidationError("$", f"unknown entity schema: {schema_id}")]
        if not kind:
            return None, [ValidationError("$", "missing entity kind")]
        if not version:
            return None, [ValidationError("$", "missing entity schemaVersion or schema")]
        return None, [ValidationError("$", f"unknown entity schema for kind={kind}, schemaVersion={version}")]

    def validate(self, entity):
        schema, lookup_errors = self.schema_for(entity)
        if lookup_errors:
            return lookup_errors
        errors = []
        validate_schema(entity, schema, "$", errors, schema.get("_schemaId", ""))
        return errors

    def validate_all(self, entities):
        errors = []
        if not isinstance(entities, list):
            return [ValidationError("$", "designEntities must be an array")]
        for index, entity in enumerate(entities):
            for error in self.validate(entity):
                errors.append(ValidationError(f"$[{index}]{error.path[1:]}", error.message, error.schema_id))
        return errors


def normalize_schema_version(value):
    text = str(value or "").strip()
    if text and text[0].isdigit():
        return f"v{text}"
    return text


def validate_schema(instance, schema, path, errors, schema_id=""):
    if "type" in schema and not type_matches(instance, schema["type"]):
        errors.append(ValidationError(path, f"expected {schema['type']}, got {type_name(instance)}", schema_id))
        return

    if "const" in schema and instance != schema["const"]:
        errors.append(ValidationError(path, f"expected constant {schema['const']!r}", schema_id))

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(ValidationError(path, f"expected one of {schema['enum']!r}", schema_id))

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(ValidationError(path, f"missing required field: {key}", schema_id))
        for key, property_schema in schema.get("properties", {}).items():
            if key in instance:
                validate_schema(instance[key], property_schema, f"{path}.{key}", errors, schema_id)
    elif schema.get("required"):
        errors.append(ValidationError(path, "required fields can only be checked on objects", schema_id))

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < int(min_items):
            errors.append(ValidationError(path, f"expected at least {min_items} item(s)", schema_id))
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                validate_schema(item, item_schema, f"{path}[{index}]", errors, schema_id)

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < int(min_length):
            errors.append(ValidationError(path, f"expected length >= {min_length}", schema_id))

    if "anyOf" in schema and not branch_matches(instance, schema["anyOf"], schema_id):
        errors.append(ValidationError(path, "must satisfy at least one anyOf branch", schema_id))

    if "oneOf" in schema:
        matches = sum(1 for branch in schema["oneOf"] if not collect_branch_errors(instance, branch, schema_id))
        if matches != 1:
            errors.append(ValidationError(path, f"must satisfy exactly one oneOf branch, matched {matches}", schema_id))


def branch_matches(instance, branches, schema_id):
    return any(not collect_branch_errors(instance, branch, schema_id) for branch in branches)


def collect_branch_errors(instance, schema, schema_id):
    errors = []
    validate_schema(instance, schema, "$", errors, schema_id)
    return errors


def type_matches(value, schema_type):
    if isinstance(schema_type, list):
        return any(type_matches(value, item) for item in schema_type)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "null":
        return value is None
    return True


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__
