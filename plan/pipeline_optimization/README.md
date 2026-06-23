# Pipeline Optimization

> Updated: 2026-06-23

## Phase 0 Status

Phase 0 is no longer "fix PLAN-002 if missing." The current workspace showed that the
memory claim and code state were inconsistent: Hades L5 Complete data contains
103 nodes, 39 nodes with `designEntities`, and 47 entities, but
`core/design/export_adapter.py` did not serialize those entities into the DevFlow
`design.md` attachment.

The Phase 0 baseline is now:

- `PLAN-001/PLAN-002` must be verified through the real D4 -> Step 00-06 path.
- D4 export serializes L5 entities as parseable `L5实体` Markdown selections.
- Step 00 writes `core_question_coverage_report.json`.
- Step 01 writes non-empty `core_loop.json` and `system_definitions.json`.
- Step 02 writes `entity_coverage_report.json`, `entity_dependency_graph.json`,
  and `entity_phase_classification.json`.
- Step 03 writes `entity`-derived program requirements and
  `requirement_quality_report.json`.
- Step 04 writes entity-derived assets and `market_research.json` with local fallback.
- Step 05/06 write `intelligent_review_report.json` with severity levels.

## Quality Baseline

Repeatable collection command:

```powershell
python tools/validators/pipeline_quality.py
```

The script reads current draft artifacts under `ARTIFACTS_DIR`. If it is launched
from a new process whose per-session draft is empty, it falls back to the latest
draft that contains the expected stage 00-06 quality artifacts. Use
`--artifacts-dir <path>` to pin a specific artifact root.

It reports:

- question coverage rate
- core loop output rate
- system definition rate
- design entity coverage rate
- requirement binding and placeholder rates
- asset count
- Step 05 warning and blocking issue counts

## Completion Update 2026-06-23

The D4 -> Step 00-06 path now works across separate Python processes:

- D4 source packages are exported into a per-session draft.
- Step source discovery first checks the current draft, then falls back to the
  latest draft containing source packages, then legacy `sandbox/source_artifacts/`.
- Generation uses the same source-root precedence as the importer, so import and
  content generation no longer disagree about available source packages.

Additional fallback behavior is implemented for early or partially populated
designs:

- Step 02 synthesizes up to 47 traceable local entities from design selections
  when no explicit `L5实体` selections exist.
- Step 03 consumes those entities for entity-derived program requirements and
  preserves 100% system binding in the latest verification run.
- Step 04 emits priority and complexity on both selection-derived and
  entity-derived assets.
- Step 06 reports zero warnings for the latest generated art requirements.

Latest verification after bug-fix rerun of `python -m core.main --stage D4` and
`python -m core.main --from-step 0 --stop-step 6 --auto-approve --skip-preflight`:

- question coverage: 0.4
- core loop output: 1.0
- system definition rate: 1.0
- design entity coverage: 0.4563 (47 covered nodes / 103 expected nodes)
- design entity count: 47
- requirement binding: 0.9745
- placeholder rate: 0.0
- asset count: 50
- Step 05 warning/blocking: 4/0

## Implementation Boundary

Step-specific optimization logic lives under the relevant `pipeline/step_*`
directory. Shared runtime orchestration remains in `core/`; no new root-level
runtime directory is introduced.

Older planning blueprints that were found under the root-level `design_plan/`
directory have been archived under `plan/pipeline_optimization/design_plan_archive/`
so the repository root keeps its documented fixed structure.
