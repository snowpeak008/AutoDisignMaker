"""Node role classification helpers for ADR 0009."""

from collections import Counter
from enum import Enum


class RoleClass(str, Enum):
    META_PLANNING = "meta_planning"
    SYSTEM_CONCRETE = "system_concrete"
    CONTENT_CONCRETE = "content_concrete"


DEFAULT_ROLE_CLASS = RoleClass.META_PLANNING.value
ROLE_CLASS_VALUES = {role.value for role in RoleClass}


def normalize_role_class(value):
    raw_value = "" if value is None else str(value).strip()
    if not raw_value:
        return DEFAULT_ROLE_CLASS, None
    if raw_value in ROLE_CLASS_VALUES:
        return raw_value, None
    message = f"unknown roleClass {raw_value!r}; defaulted to {DEFAULT_ROLE_CLASS}"
    return DEFAULT_ROLE_CLASS, message


def empty_role_class_counts():
    return {role.value: 0 for role in RoleClass}


def count_role_classes(domains):
    counts = Counter()
    for domain_doc in domains:
        for node in domain_doc.get("nodes", []):
            role_class = node.get("roleClass", DEFAULT_ROLE_CLASS)
            if role_class not in ROLE_CLASS_VALUES:
                role_class = DEFAULT_ROLE_CLASS
            counts[role_class] += 1
    result = empty_role_class_counts()
    result.update(counts)
    return result
