# Build And Troubleshooting

## Build

```bash
python scripts/build.py
python scripts/verify_build.py
```

`AutoDesignMaker.spec` uses paths relative to the spec file, so the project can
be moved before building. The build includes `data/` and `config/app.toml`.

## Startup Checks

CLI and GUI entry points validate:

- `data/design/domains`
- `data/schemas`
- `src/plugins/plugin_manifest.json`
- `ucos/knowledge`

Missing or empty data raises `RuntimeError: Data integrity check failed` with a
per-path error list.

## Config Errors

`config/app.toml` is required. Missing files raise `FileNotFoundError`; invalid
TOML raises `ValueError` with the file path and parser detail.
