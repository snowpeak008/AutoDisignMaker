# AutoDesignMaker

AutoDesignMaker merges the migrated DevFlow development pipeline with the
commercial game design decision tool.

## Run

```bash
python src/main.py --list-stages
python src/main.py --stage D1 --test-mode
python scripts/validate_structure.py
```

The GUI entry point is:

```bash
python src/gui_app.py
```

Formal DevFlow runs require `project_settings.json` to contain a valid Unity
project path and Unity Editor executable path.

## Layout

- `src/core/`: path, configuration, context, and plugin infrastructure.
- `src/plugins/`: D1-D4 design plugins and 00-15 development stage delegates.
- `design_tool/`: migrated design engine compatibility package.
- `data/design/`: migrated design domains, templates, schemas, and prompt data.
- `steps/`, `tools/`, `orchestrator.py`: migrated DevFlow runtime.
- `ucos/` and `memory/`: migrated cognitive memory systems.
- `workspace/`: user projects, exports, saves, outputs, and migration targets.

