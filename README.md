# AutoDesignMaker

AutoDesignMaker merges the migrated DevFlow development pipeline with the
commercial game design decision tool.

## ⚠️ Git 提交规则（强制）

**每次优化、修复或功能添加后，必须立即提交到 Git。**

详细规范请参考：[docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)

快速提交：
```bash
git add .
git commit -m "类型: 描述修改内容"
git push origin master
```

## Run

```bash
python src/main.py --list-stages
python src/main.py --stage D1 --test-mode
python scripts/validate_structure.py
```

Build and verify the packaged executable with:

```bash
python scripts/build.py
python scripts/verify_build.py
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
