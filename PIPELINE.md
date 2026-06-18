# Pipeline

The project uses a deterministic no-agent-runtime pipeline.

## Run

```powershell
python orchestrator.py --from-step 0 --stop-step 15 --auto-approve
```

For first-time setup, single-step runs, output locations, and troubleshooting, see `Docs/NEW_PROJECT_RUNBOOK.md`.

## Layers

```text
Stage
  -> Artifact
      -> Task
          -> Reviewer
              -> Validator
```

## Directories

- `steps/`: stage modules imported by orchestrator.
- `artifact_layer/`: artifact registry and dependency graph.
- `knowledge/`: project knowledge base.
- `source_artifacts/`: reusable source inputs owned by the current project.
- `outputs/artifacts/`: generated outputs and reports.
- `save/`: authoritative saved project states. The active `source_artifacts/`
  and `outputs/` directories are only a runtime sandbox.

On GUI startup the active workspace is reset to an empty structure. Previous
work is restored only when the operator explicitly loads a save from `save/`.
Each save stores `workspace/`, `snapshots/`, `timeline.jsonl`,
`save_manifest.json`, and `save_file_map.json`.

Source artifact directory names are not the contract. Stage imports first read
`package_manifest.json` and match stable `source_id` / `package_type` values.
Directory glob matching exists only as a legacy fallback for old packages that
do not have a manifest yet.

## Required Reports

Each stage writes:

- `artifact_index.json`
- `reference_manifest.json`
- `validation_report.json`
- `artifact_layer_manifest.json`
- `artifact_reviews.json`
- `artifact_validation_layer.json`

`artifact_index.json` is the stage summary. `reference_manifest.json` is the
machine-readable file lineage contract: it lists local files, source imports,
upstream stage files, hashes, and artifact dependency relations. Downstream
stages consume upstream files through this manifest and `UPSTREAM_REFERENCE.json`
records rather than copying whole upstream artifact directories.
