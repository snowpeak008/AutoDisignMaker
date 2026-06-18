# Architecture

AutoDesignMaker uses a compatibility-first integration.

The stable project root is located with `.project_root`. New code imports paths
from `src.core.paths`; migrated code that still derives paths from its module
location now lives at the project root so those relative calculations resolve
inside AutoDesignMaker.

`src.core.plugin_manager.PluginManager` loads stage plugins from
`src/plugins/plugin_manifest.json`. D1-D4 run the migrated design engine in
`design_tool/`. Stages 00-15 delegate to the migrated deterministic DevFlow
orchestrator.

The design tool keeps its original `design_tool` package name for import
compatibility, but its data root is redirected to `data/design/`.

