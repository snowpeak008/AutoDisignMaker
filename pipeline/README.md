# Pipeline Overview

AutoDesignMaker uses a deterministic no-agent-runtime pipeline.

- Entry point: `core.main`
- Step modules: `pipeline/step_00_*` through `pipeline/step_16_*`
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
- Step 07: Art Style Generation & Confirmation
- Step 08: Design To Plan
- Step 09: Art Plan
- Step 10: Asset Alignment
- Step 11: Development Execution
- Step 12: Art Production
- Step 13: Integration Validation
- Step 14: Build Package
- Step 15: Delta Patch
- Step 16: Migration Audit
