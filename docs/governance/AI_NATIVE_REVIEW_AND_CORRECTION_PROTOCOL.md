# AI-Native Review And Correction Protocol

Version: 1.0

This protocol defines the machine-readable review and correction handoff produced by step 5 and step 6.

It is not a natural-language review template. It is a contract for:

```text
Shared/{Project}_ProgReview_*/program_review_report.json
Shared/{Project}_ArtReview_*/art_review_report.json
Shared/Correction_*/correction_queue.json
```

## 1. Purpose And Boundary

Step 5 and step 6 are gates. They do not create requirements or design facts.

They may only:

1. Validate machine contracts from previous stages.
2. Record evidence-backed findings.
3. Route root causes to the earliest stage that can repair them.
4. Generate a correction queue for selected automatic fixes.
5. Record forced pass decisions and their unresolved risk.

Primary machine outputs:

```text
program_review_report.json
art_review_report.json
correction_queue.json
```

Secondary human outputs:

```text
completeness.md
contract_consistency.md
authority_review.md
acceptability.md
category.md
drift_review.md
spec_quality.md
classification.md
verdict.md
review.md
correction_queue.md
known_design_gaps.md
```

Markdown is evidence and explanation only. If Markdown contradicts the JSON report or JSON correction queue, JSON is authoritative.

## 2. Authority Order

| Priority | Source | Authority |
|---:|---|---|
| 1 | Reviewed machine contract | Facts under review. |
| 2 | Source protocol of reviewed contract | Rules the reviewed contract promised to follow. |
| 3 | This review protocol | Review, routing, gate, and correction rules. |
| 4 | Review report JSON | Machine review evidence and verdict. |
| 5 | Correction queue JSON | Machine repair entry point. |
| 6 | Markdown files | Human-readable evidence only. |

Review agents must not treat Markdown as the primary fact source when a reviewed JSON contract exists.

## 3. Review Report Envelope

Every review report must expose these JSON object fields:

```text
schema_version
generated_at
consumer_stage
source_review_protocol
reviewed_contract
reviewed_contract_protocol
reviewed_contract_schema_version
verdict
scores
findings
classification_summary
routing_summary
gate_decision
quality
```

Required semantics:

| Field | Meaning |
|---|---|
| `consumer_stage` | `step_5_program_requirements_review` or `step_6_art_requirements_review`. |
| `source_review_protocol` | Path to this protocol. |
| `reviewed_contract` | Path to the machine contract under review. |
| `reviewed_contract_protocol` | Protocol path recorded by the reviewed contract. |
| `reviewed_contract_schema_version` | Schema version of the reviewed contract. |
| `verdict` | `PASS`, `FAIL`, or `FORCED_PASS`. |
| `findings` | Evidence-backed issues. |
| `routing_summary` | Counts by root-cause stage and auto-correction eligibility. |
| `gate_decision` | Human or automatic gate outcome. |
| `quality` | Validation and blocker summary for the report itself. |

## 4. Finding Contract

Each finding must expose these JSON object fields:

```text
finding_id
severity
category
source_refs
broken_rule
root_cause_stage
affected_ids
affected_files
auto_correctable
suggested_correction_type
evidence
```

Allowed severity values:

```text
LOW
MEDIUM
HIGH
CRITICAL
BLOCK
WARNING
```

Allowed root-cause stages:

```text
design
progreq
artreq
human_gap
unmapped
```

Rules:

1. A finding must identify a broken rule or missing contract field.
2. A finding must route to the earliest repairable stage.
3. `auto_correctable` may be true only when the repair target is `design`, `progreq`, or `artreq`.
4. `human_gap` findings are not auto-correctable.
5. `unmapped` findings must block automatic patch routing.

## 5. Step 5 Program Review Profile

Step 5 reviews:

```text
program_requirements_contract.json
```

Primary checks:

1. Program contract envelope is present.
2. `source_contract_protocol` exists.
3. `quality.blockers` from step 3 are carried into review findings.
4. Systems, contracts, entities, events, authority, acceptance, and path bindings are internally coherent.
5. Findings route to `progreq` unless the source design handoff lacks a required fact.
6. Findings route to `design` only for missing or contradictory source game facts.
7. Findings route to `human_gap` only when no automatic stage can decide the missing product/design choice.

Required report files:

```text
program_review_report.json
program_review_report_validation.json
```

## 6. Step 6 Art Review Profile

Step 6 reviews:

```text
art_requirements_contract.json
asset_registry.json
```

Primary checks:

1. Art contract envelope is present.
2. `source_contract_protocol` exists.
3. `quality.blockers` from step 4 are carried into review findings.
4. Assets have stable IDs and source facts.
5. Visual states and UX signal bindings cover required upstream facts.
6. Drift checks with `BLOCK` are review blockers.
7. Findings route to `artreq` unless VisualDNA, ArtRules, or design handoff facts are missing or contradictory.
8. Findings route to `design` only for missing source visual/game facts or governance rules.

Required report files:

```text
art_review_report.json
art_review_report_validation.json
```

## 7. Correction Queue Envelope

Every correction queue must expose these JSON object fields:

```text
schema_version
generated_at
source_review_protocol
source_review
source_review_report
reviewed_contract
corrections
rerun_plan
blocked_items
```

Required semantics:

| Field | Meaning |
|---|---|
| `source_review_protocol` | Path to this protocol. |
| `source_review` | Review output directory. |
| `source_review_report` | Review report JSON that produced the queue. |
| `reviewed_contract` | Contract that was reviewed before producing corrections. |
| `corrections` | Selected automatic repair items. |
| `rerun_plan` | Ordered stages and commands that should run after applying the queue. |
| `blocked_items` | Findings that could not be automatically routed. |

## 8. Correction Item Contract

Each correction must expose these JSON object fields:

```text
correction_id
selected
target_stage
conflict_type
severity
correction_type
source_finding_id
affected_ids
affected_systems
affected_files
entities
source_system
target_system
required_change
forbidden_change
detail
```

Rules:

1. `target_stage` must be `design`, `progreq`, `artreq`, `human_gap`, or `unmapped`.
2. Automatic patch scripts may only execute selected corrections with `target_stage` in `design`, `progreq`, or `artreq`.
3. `human_gap` and `unmapped` corrections must be listed in `blocked_items`.
4. `affected_files` must be present for `progreq` and `artreq` targets.
5. `required_change` must be positive and scoped.
6. `forbidden_change` must prevent inventing unrelated facts.

## 9. Rerun Plan

The rerun plan is a machine-readable repair route.

Required fields:

```text
rerun_plan.required_stages
rerun_plan.commands
rerun_plan.reason
```

Rules:

1. Design fixes run before requirement fixes.
2. Program fixes rerun step 3 then step 5.
3. Art fixes rerun step 4 then step 6.
4. If a queue contains only `human_gap` or `unmapped`, `commands` must be empty.
5. If a design fix affects both program and art downstream, rerun plan must include both affected review lines when known.

## 10. Gate Decision

Gate decision records how the review outcome was handled.

Allowed outcomes:

```text
pass
needs_correction
forced_pass
forced_pass_no_selection
failed_to_parse
```

Rules:

1. `forced_pass` must record unresolved blocker and design gap counts.
2. `needs_correction` must record a correction queue path.
3. A PASS review with non-empty blockers is invalid unless outcome is `forced_pass`.

## 11. Forbidden Patterns

Step 5 and step 6 must not:

1. Modify design, program requirements, or art requirements directly.
2. Create new design facts in review prose.
3. Route requirement extraction errors to `design`.
4. Route missing source facts to `progreq` or `artreq`.
5. Generate a correction queue without a source review report.
6. Generate automatic patch commands for `human_gap` or `unmapped` items.
7. Treat Markdown as authoritative when a machine contract exists.

