# AI-Native Requirements Handoff Protocol

Version: 1.0

This protocol defines the machine-readable requirements handoff produced by step 3 and step 4.

It is not a natural-language requirements template. It is a contract for:

```text
Shared/{Project}_ProgReq_*/program_requirements_contract.json
Shared/{Project}_ArtReq_*/art_requirements_contract.json
```

## 1. Purpose And Boundary

Step 2 defines game facts in `design_handoff.json`.

Step 3 and step 4 derive implementation-facing requirements from those facts.

The requirements stages must not create new design facts. They may only:

1. Map source design facts to program systems, contracts, entities, events, authority rules, and acceptance criteria.
2. Map source design facts to visual assets, visual states, UX signal bindings, production specs, and drift checks.
3. Add execution-facing details that do not change gameplay, world, UX, economy, or visual intent.
4. Report missing or ambiguous source facts through review and correction queues.

Primary machine outputs:

```text
program_requirements_contract.json
art_requirements_contract.json
asset_registry.json
program_trace.json
art_trace.json
```

Secondary human outputs:

```text
contracts.md
systems.md
entities.md
events.md
authority.md
acceptance_criteria.md
program_requirements.md
原画需求.md
UI需求.md
特效需求.md
drift_analysis.md
资产清单.md
```

Markdown is a weak rendering. If Markdown contradicts the JSON contract, the JSON contract is authoritative.

## 2. Authority Order

| Priority | Source | Authority |
|---:|---|---|
| 1 | `design_handoff.json` | Source game facts and consumer views. |
| 2 | This requirements protocol | Derivation rules for step 3 and step 4. |
| 3 | `program_requirements_contract.json` | Program requirement facts. |
| 4 | `art_requirements_contract.json` | Art requirement facts. |
| 5 | `asset_registry.json` | Stable asset identity and source mapping. |
| 6 | `program_trace.json` / `art_trace.json` | Provenance and validation evidence. |
| 7 | Markdown files | Human-readable rendering only. |

If a requirement needs a fact that is absent from `design_handoff.json`, the requirement stage must mark a gap. It must not fill the gap with prose.

## 3. Common Contract Envelope

Every step 3 and step 4 contract must expose:

```text
schema_version:
generated_at:
consumer_stage:
source_contract_protocol:
source_design_handoff:
source_design_markdown:
source_coverage:
derivation_policy:
source_files:
quality:
```

Required semantics:

| Field | Meaning |
|---|---|
| `consumer_stage` | `step_3_program_requirements` or `step_4_art_requirements`. |
| `source_contract_protocol` | Path to this protocol. |
| `source_design_handoff` | Path to the consumed step 2 handoff. |
| `source_coverage` | Count, consumer-view presence, and `coverage_gaps` for consumed source fields. |
| `derivation_policy` | Explicit rules for what this stage may derive and must not invent. |
| `source_files` | Human-rendered files used to produce each contract slice. |
| `quality` | Machine-readable validation and blocker summary. |

## 4. Step 3 Program Profile

Step 3 produces:

```text
program_requirements_contract.json
program_trace.json
program_structure_spec.md
program_requirements.md
```

The machine contract must expose:

```text
systems:
contracts:
entities:
events:
authority:
acceptance:
design_fact_bindings:
path_bindings:
```

### 4.1 Systems

Program systems are derived from `design_handoff.consumer_views.program`, `design_handoff.systems`, and relevant `knowledge_units`.

Rules:

1. A program `system_id` must be stable and must not be renamed by later agents.
2. Each system must record its source design system or source design fact where known.
3. Step 3 may split a large design system only when the split is implementation-facing and preserves one traceable source.
4. Step 3 may not merge design systems if doing so hides authority ownership.

Required system item fields:

```text
system_id:
source_design_system_id:
name:
responsibility:
description:
```

### 4.2 Contracts

Contracts represent cross-system communication.

Allowed methods:

```text
query
command
event
```

Rules:

1. Contracts are defined once in the registry.
2. Later system details may bind contracts but may not invent new ones.
3. Event requirements must bind `method: event`.
4. State mutation must route through the authority owner or a registered contract.
5. A contract without source and target systems is invalid.

Required contract item fields:

```text
contract_id:
source_system:
target_system:
method:
inputs:
outputs:
errors:
```

### 4.3 Entities

Entities describe implementation data shape. They are not gameplay authority by themselves.

Rules:

1. Entity fields that represent mutable gameplay facts must be covered by `authority`.
2. Entities must use project field naming conventions.
3. Entities may introduce technical fields only when they do not alter design semantics.

Required entity item fields:

```text
entity_id:
entity_name:
owner_system:
source_text:
```

### 4.4 Events

Events are generated from registered event contracts and source design triggers.

Rules:

1. Events must bind an event contract where known.
2. Event payloads must be compatible with contract outputs.
3. Subscriber systems may be expanded, but the registered target system must remain covered.

Required event item fields:

```text
event_id:
event:
source_text:
```

### 4.5 Authority

Authority maps mutable data to a single owning system.

Rules:

1. Every mutable design fact represented in entities must have one authority entry.
2. Non-owner writes are invalid unless routed through a contract.
3. Missing authority is a step 5 blocker, not a downstream implementation choice.

Required authority item fields:

```text
authority_id:
authority:
source_text:
```

### 4.6 Acceptance

Acceptance criteria are derived from executable scenarios, P0/P1 features, and authority-sensitive behavior.

Rules:

1. P0 and P1 features require at least one acceptance item.
2. Acceptance should preserve Given / When / Then semantics.
3. Negative scenarios from design handoff must produce negative acceptance coverage.

Required acceptance item fields:

```text
acceptance_id:
acceptance:
source_text:
```

### 4.7 Program Path Bindings

Step 3 must bind systems to allowed program paths before step 7 creates plans.

Required path binding item fields:

```text
binding_id:
owner_id:
target_path:
allowed_outputs:
source:
```

## 5. Step 4 Art Profile

Step 4 produces:

```text
art_requirements_contract.json
asset_registry.json
art_trace.json
art_structure_spec.md
原画需求.md
UI需求.md
特效需求.md
```

The machine contract must expose:

```text
visual_language:
assets:
visual_states:
ux_signal_bindings:
drift_checks:
path_bindings:
```

### 5.1 Visual Language

Visual language is a derived constraint set from VisualDNA, ArtRules, and visual units in `design_handoff.json`.

Rules:

1. Visual language may constrain style, material, lighting, readability, and forbidden motifs.
2. It must not invent world lore or gameplay meaning.
3. Tokens should remain short and reusable.

### 5.2 Assets

Assets are stable production targets.

Rules:

1. Every asset must have a stable `asset_id`.
2. Every asset must map to a source visual object, source system, UX signal, or explicit art rule where known.
3. UI and VFX assets must bind to the player decision, state, event, or feedback they communicate.
4. An asset with no source fact and no art rule is invalid.

Required asset item fields:

```text
asset_id:
name:
category:
source_visual_object_id:
source_system_ids:
purpose:
required_readability:
production_specs:
forbidden_visuals:
acceptance_checks:
```

### 5.3 Visual States

Visual states represent stateful variants of assets or UI.

Rules:

1. Stateful UI, VFX, and visual feedback must expose visual states.
2. Visual states must link to a source gameplay state, UX signal, or asset.
3. Missing state coverage is a step 6 review issue.

Required visual state item fields:

```text
visual_state_id:
asset_id:
source_state_id:
state_name:
required_difference:
```

### 5.4 UX Signal Bindings

UX signal bindings ensure art communicates gameplay decisions.

Rules:

1. Every consumed `design_handoff.ux_signals` item that needs visual representation must bind to at least one asset or visual state.
2. Missing signal binding must be reported as a gap.
3. Decorative assets must not claim gameplay signaling authority.

Required UX signal binding item fields:

```text
binding_id:
ux_signal_id:
asset_id:
required_feedback:
timing:
```

### 5.5 Drift Checks

Drift checks compare produced art requirements against VisualDNA and ArtRules.

Rules:

1. Drift checks must identify the asset or global rule being checked.
2. `severity` must be one of `OK`, `WARNING`, `BLOCK`, or `UNKNOWN`.
3. `BLOCK` items must route to step 6 correction.

### 5.6 Art Path Bindings

Step 4 must bind assets to allowed source and exported paths before step 8 creates plans.

Required path binding item fields:

```text
binding_id:
asset_id:
source_path:
target_path:
output_files:
```

## 6. Trace Rules

`program_trace.json` and `art_trace.json` must record:

```text
schema_version:
source_contract_protocol:
source_design_handoff:
source_design_markdown:
source_coverage:
contract_file:
```

Trace files are evidence. They must not introduce facts that are absent from the contract.

## 7. Patch Rules

Patch mode must preserve stable IDs.

Rules:

1. A correction item may regenerate only affected systems, contracts, assets, categories, or cross-cutting checks.
2. Unaffected contract slices should be copied forward or re-derived from the previous version.
3. Patch outputs must keep `source_contract_protocol`.
4. If a patch needs a missing source design fact, it must route back to step 2.
5. If a patch needs a missing derived requirement fact, it must route to step 3 or step 4.

## 8. Quality Gate

The local schema validator must run for each machine contract when a schema exists.

Minimum quality fields:

```text
quality:
  schema:
  valid:
  blockers:
  warnings:
```

Hard blockers:

1. Missing `source_design_handoff`.
2. Missing `source_contract_protocol`.
3. Missing required consumer view in `design_handoff.json`.
4. Missing knowledge units or relations when a structured handoff exists.
5. Program contract with no systems.
6. Program contract with a contract that has no source or target system.
7. Art contract with no assets when visual objects or UX signals exist upstream.
8. Asset without stable `asset_id`.
9. Asset without source design fact, UX signal, visual object, source system, or explicit art rule.
10. Markdown-only requirement fact that is absent from JSON.

## 9. Forbidden Patterns

The requirements stages must not:

1. Treat Markdown as the primary fact source when `design_handoff.json` exists.
2. Add new gameplay rules, resources, economy loops, world facts, or UX promises.
3. Add art assets with no source fact or explicit art rule.
4. Add direct non-owner writes to mutable state.
5. Let later planning or execution stages invent target paths.
6. Hide unresolved gaps inside natural-language prose.

