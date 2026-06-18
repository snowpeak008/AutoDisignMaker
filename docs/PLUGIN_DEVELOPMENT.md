# Plugin Development

AutoDesignMaker stages implement `src.core.stage_plugin.StagePlugin`.

## Stage Contract

- `stage_id`: stable identifier such as `D1` or `00`.
- `title`: human-readable stage title.
- `execute(context)`: writes artifacts under `context.artifact_dir` and returns `StageResult`.
- `validate_inputs(context)` and `validate_outputs(context)`: optional guard hooks.

Register new stages in `src/plugins/plugin_manifest.json`.

## Validation

Run:

```bash
python src/core/plugin_manager.py --validate --list-stages
python src/main.py --stage D1 --test-mode
```

Development stages delegate to the migrated DevFlow runtime through
`src.engines.orchestrator`, so stage imports do not depend on the caller's
current `sys.path`.
