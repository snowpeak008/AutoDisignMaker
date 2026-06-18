from src.core.context import StageContext
from src.core.plugin_manager import PluginManager


def test_plugin_manifest_loads_all_stages():
    manager = PluginManager()
    stages = manager.list_stages()
    assert stages[:4] == ["D1", "D2", "D3", "D4"]
    assert stages[-1] == "15"
    assert not manager.validate()


def test_design_stage_runs_in_test_context():
    plugin = PluginManager().load_stage("D1")
    result = plugin.run(StageContext(stage_id="D1", test_mode=True))
    assert result.ok
    assert result.outputs["domainCount"] >= 1

