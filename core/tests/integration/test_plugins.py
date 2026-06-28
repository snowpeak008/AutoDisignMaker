from __future__ import annotations

from core.context import StageContext
from core.plugin_manager import PluginManager


def _run_stage(stage_id: str):
    plugin = PluginManager().load_stage(stage_id)
    result = plugin.run(StageContext(stage_id=stage_id, test_mode=True))
    assert result.ok
    return result


def test_plugin_manifest_loads_all_stages():
    manager = PluginManager()
    stages = manager.list_stages()
    assert stages[:4] == ["D1", "D2", "D3", "D4"]
    assert stages[-1] == "16"
    assert not manager.validate()


def test_design_stage_runs_in_test_context():
    result = _run_stage("D1")
    assert result.outputs["domainCount"] >= 1


def test_design_stages_write_specific_artifacts():
    _run_stage("D1")
    _run_stage("D2")
    _run_stage("D3")

    from core.paths import ARTIFACTS_DIR

    assert (ARTIFACTS_DIR / "stage_d1" / "design_portrait.json").exists()
    assert (ARTIFACTS_DIR / "stage_d2" / "design_domains.json").exists()
    assert (ARTIFACTS_DIR / "stage_d3" / "design_validation_report.json").exists()


def test_development_stage_imports_without_path_side_effect_failure():
    plugin = PluginManager().load_stage("00")

    assert plugin.stage_id == "00"
