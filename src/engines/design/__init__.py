"""Compatibility facade for the migrated design engine."""

from design_tool.data_loader import load_project_data
from design_tool.engine import DesignEngine

__all__ = ["DesignEngine", "load_project_data"]

