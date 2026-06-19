# Plugin Development Standard

All stage plugins implement `src.core.stage_plugin.StagePlugin`.

Required methods:

- `stage_id`: stable identifier such as `D1` or `00`.
- `execute(context)`: performs the stage and returns `StageResult`.

Optional validators:

- `validate_inputs(context)`
- `validate_outputs(context)`

