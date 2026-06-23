# ADR 2026-06-23: Draft, Archive, And Execution Object Semantics

## Status

Proposed

## Context

The 2026-06-21 draft/archive change moved runtime output to
`drafts/{session_id}/` and kept formal saves under `saves/{save_id}/` as
`manifest.json` plus `workspace/`. A remaining ambiguity is whether execution
objects and pipeline artifacts are edit-time draft data, formal archive data, or
both.

## Decision

Use the draft as the only write target during editing and pipeline execution.
Formal saves are explicit archive results.

- Draft contains current execution-object store, pipeline artifacts, temporary
  maps, timeline, checkpoints, and runtime control files.
- Formal save contains user-recoverable state: project manifest, workspace,
  project settings, verified design project, selected source package references,
  and optionally selected final pipeline deliverables.
- Explicit save copies recoverable objects from draft to formal save.
- Autosave may update draft but must not mutate the formal archive unless the UI
  action is explicitly a save.
- Pipeline intermediate artifacts are rebuildable by default. Final deliverables
  can be promoted into formal save when the user marks them as retained outputs.

## Migration

- Existing `save_manifest.json` remains readable and should be rewritten as
  `manifest.json` on next explicit save.
- Existing workspace execution-object stores remain valid import sources.
- If a formal save lacks pipeline artifacts, load should not treat that as
  corruption; the pipeline can regenerate draft artifacts.

## Consequences

- GUI load can restore the formal design project without resurrecting stale
  transient draft files.
- Pipeline runs stay isolated and repeatable per session.
- A future implementation should add a visible "promote deliverables to archive"
  action instead of silently copying every artifact.
