# Cutover Report

Date: 2026-06-07

## Current Runtime

The current project is cut over to a deterministic no-agent-runtime pipeline.

- Entry point: `orchestrator.py`
- Stage modules: `steps/`
- Source inputs: `source_artifacts/`
- Artifact contract: `artifact_layer/registry.json`
- Dependency graph: `artifact_layer/dependency_graph.json` and `outputs/dependency_graph.json`
- Knowledge base: `knowledge/`
- Outputs: `outputs/artifacts/stage_00` through `outputs/artifacts/stage_15`

## Historical Content

Historical source material is still usable as project-owned input after cutover. The current project reads it from `source_artifacts/`, not from the retired runtime output directory.

The retired source directory was moved out of the current project during cutover.

## Verification

```powershell
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
```

Expected result:

```text
all stages: success
artifact reviews: success
artifact validations: success
```

## Cutover Rules

- Do not run retired stage entry files.
- Do not read source inputs from the retired output directory.
- Do not restore retired snapshots into the current project.
- Add new reusable source material under `source_artifacts/`.
- Add project rules and decisions under `knowledge/`.
