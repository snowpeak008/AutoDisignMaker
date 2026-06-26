# Pipeline Overview

AutoDesignMaker uses a deterministic no-agent-runtime pipeline.

- Entry point: `core.main`
- Step modules: `pipeline/step_00_*` through `pipeline/step_17_*`
- Source inputs: `drafts/{session}/source_artifacts/`
- Generated outputs: `drafts/{session}/outputs/artifacts/stage_XX/`
- Governance layer: `pipeline/artifact_layer/`, `knowledge/`, reviewers, validators, and dependency graph.

## Active Steps

- Step 00: Idea Intake
- Step 01: Gameplay Framework
- Step 02: Design Review Freeze
- Step 03: Program Requirements
- Step 04: Art Requirements
- Step 05: Program Review
- Step 06: Art Review
- Step 07: Art Style Generation
- Step 08: Art Style Confirmation
- Step 09: Design To Plan
- Step 10: Art Plan
- Step 11: Asset Alignment
- Step 12: Development Execution
- Step 13: Art Production
- Step 14: Integration Validation
- Step 15: Build Package
- Step 16: Delta Patch
- Step 17: Migration Audit
