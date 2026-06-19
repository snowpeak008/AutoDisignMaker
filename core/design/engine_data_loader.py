"""Design engine data-loading facade."""

from __future__ import annotations

from core.design.data_loader import load_domains, load_project_data


def load_all():
    return load_project_data()


__all__ = ["load_all", "load_domains", "load_project_data"]

