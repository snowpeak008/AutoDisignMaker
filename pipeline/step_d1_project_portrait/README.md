# Project Overview

This project uses a deterministic no-agent-runtime pipeline.

- Entry point: `orchestrator.py`
- Step modules: `steps/step0_*.py` through `steps/step15_*.py`
- Source inputs: `source_artifacts/`
- Generated outputs: `outputs/artifacts/stage_XX/`
- Governance layer: `artifact_layer/`, `knowledge/`, reviewers, validators, and dependency graph.

