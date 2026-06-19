# Fused Pipeline Optimization Plan

The current project uses a deterministic runtime with these layers:

```text
Stage
  -> Artifact
      -> Task
          -> Reviewer
              -> Validator
```

The bottom execution contract is:

- `orchestrator.py`
- `steps/step*.py`
- `artifact_layer/registry.json`
- `knowledge/`
- `source_artifacts/`
- `outputs/artifacts/`

Historical design material may be reused only after it has been adopted into `source_artifacts/`.

