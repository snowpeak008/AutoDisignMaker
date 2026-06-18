# Path Independence Protocol

Project code must derive internal paths from `src.core.paths.PROJECT_ROOT`.

Do not hardcode local machine paths. User-selected external paths, such as a
Unity project path, belong in `project_settings.json` or `config/app.toml`.

Run this before handoff:

```bash
python scripts/check_hardcoded_paths.py
```

