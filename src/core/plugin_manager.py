"""Plugin loading and validation for AutoDesignMaker stages."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT_FOR_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT_FOR_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_BOOTSTRAP))

from src.core.paths import PLUGIN_MANIFEST_FILE, PROJECT_ROOT
from src.core.stage_plugin import StagePlugin


@dataclass(frozen=True)
class PluginSpec:
    stage_id: str
    module: str
    class_name: str
    enabled: bool = True
    title: str = ""


class PluginManager:
    def __init__(self, manifest_file: Path = PLUGIN_MANIFEST_FILE) -> None:
        self.manifest_file = manifest_file
        self._manifest: dict[str, Any] | None = None
        self._instances: dict[str, StagePlugin] = {}

    @property
    def manifest(self) -> dict[str, Any]:
        if self._manifest is None:
            self._manifest = json.loads(self.manifest_file.read_text(encoding="utf-8"))
        return self._manifest

    def stage_specs(self, *, enabled_only: bool = True) -> list[PluginSpec]:
        specs: list[PluginSpec] = []
        stages = self.manifest.get("plugins", {}).get("stages", {})
        for stage_id, payload in stages.items():
            enabled = bool(payload.get("enabled", True))
            if enabled_only and not enabled:
                continue
            specs.append(
                PluginSpec(
                    stage_id=str(stage_id),
                    module=str(payload["module"]),
                    class_name=str(payload["class"]),
                    enabled=enabled,
                    title=str(payload.get("title", "")),
                )
            )
        return sorted(specs, key=lambda spec: _stage_sort_key(spec.stage_id))

    def load_stage(self, stage_id: str) -> StagePlugin:
        if stage_id in self._instances:
            return self._instances[stage_id]
        matches = [spec for spec in self.stage_specs() if spec.stage_id == stage_id]
        if not matches:
            raise KeyError(f"Stage plugin is not registered: {stage_id}")
        spec = matches[0]
        module = importlib.import_module(spec.module)
        plugin_class = getattr(module, spec.class_name)
        plugin = plugin_class()
        if not isinstance(plugin, StagePlugin):
            raise TypeError(f"{spec.module}.{spec.class_name} is not a StagePlugin")
        if plugin.stage_id != stage_id:
            raise ValueError(f"Plugin stage_id mismatch: manifest={stage_id}, class={plugin.stage_id}")
        self._instances[stage_id] = plugin
        return plugin

    def list_stages(self) -> list[str]:
        return [spec.stage_id for spec in self.stage_specs()]

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.manifest_file.exists():
            return [f"Missing plugin manifest: {self.manifest_file}"]
        for spec in self.stage_specs():
            try:
                self.load_stage(spec.stage_id)
            except Exception as exc:  # noqa: BLE001 - validation reports all plugin failures.
                errors.append(f"{spec.stage_id}: {exc}")
        return errors


def _stage_sort_key(stage_id: str) -> tuple[int, int | str]:
    text = str(stage_id)
    if text.upper().startswith("D"):
        suffix = text[1:]
        return (0, int(suffix) if suffix.isdigit() else suffix)
    return (1, int(text) if text.isdigit() else text)


def main(argv: list[str] | None = None) -> int:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    parser = argparse.ArgumentParser(description="Validate and list AutoDesignMaker plugins.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--list-stages", action="store_true")
    args = parser.parse_args(argv)
    manager = PluginManager()
    if args.list_stages:
        for stage_id in manager.list_stages():
            print(stage_id)
    if args.validate:
        errors = manager.validate()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("Plugin manifest validation passed")
    if not args.list_stages and not args.validate:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
