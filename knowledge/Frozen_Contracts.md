# Frozen Contracts

- `orchestrator.py` remains the main entrypoint.
- Each step module exposes `run(context)`.
- Each stage writes `validation_report.json`.
- Artifact layer reports are additive files under each stage directory.
- Compatibility wrappers are not part of the current runtime surface.
