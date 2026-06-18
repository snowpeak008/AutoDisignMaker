# Development Handoff

Current runtime:

- `orchestrator.py` is the only supported pipeline entry point.
- `steps/step*.py` expose `run(context)` for orchestrator imports.
- Direct step module execution routes back through orchestrator.
- `source_artifacts/` contains reusable project source material.
- `outputs/artifacts/stage_XX/` contains generated stage outputs.
- `artifact_layer/registry.json` defines artifact, task, reviewer, validator, and dependency contracts.
- `knowledge/` stores deterministic project knowledge.

Validation commands:

```powershell
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
python -m compileall orchestrator.py steps tools problem_resolver.py run_pipeline.py
```
