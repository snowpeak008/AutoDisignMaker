# Steps 0-2 Human-Led Redesign Implementation Plan

This plan turns `HUMAN_LED_GAMEPLAY_DESIGN_PROTOCOL.md` into concrete script
work. It intentionally separates protocol design from implementation so the
current code can be migrated safely.

## 1. Target Script Responsibilities

| Script | New Responsibility | Keep Name? |
|---|---|---|
| `idea_intake.py` | Step 0 creative point extraction, prototype generation, user selection, modification loop | Yes, for compatibility |
| `demo_crew.py` | Step 1 gameplay framework iteration around the approved prototype | Yes, for compatibility |
| `design_crew.py` | Step 2 orchestrator for 2A/2B/2C only | Yes |
| `design_step_2a.py` | Per-subsystem design and approval loop | Rewrite |
| `design_step_2b.py` | Compile approved design into AI understanding script | Rewrite |
| `design_step_2c.py` | Generate development system design | Rewrite |
| `human_led_design_common.py` | Shared gates, status, JSON parsing, folder naming | New shared helper |

## 2. Step 0 Implementation

### Inputs

```text
my_game_idea.txt
```

### Agent Prompt Goal

Generate 4-6 gameplay prototype candidates from the raw idea. The agent must
not pick a winner.

### Required JSON

```json
{
  "schema_version": "1.0",
  "artifact_type": "prototype_selection_round",
  "source_text": "",
  "creative_points": [],
  "play_prototypes": [],
  "open_questions": []
}
```

### Interaction

1. Show prototype cards.
2. Ask for IDs, `none`, or exit.
3. For each selected ID, ask for optional modification notes.
4. Regenerate selected prototypes with notes.
5. If one prototype remains, ask whether to enter step 1.

### Outputs

```text
creative_points.json
prototype_candidates.json
prototype_cards.md
selected_play_prototype.json
selection_history.json
open_questions.json
```

## 3. Step 1 Implementation

### Inputs

```text
selected_play_prototype.json
selection_history.json
```

### Agent Prompt Goal

Design the high-level gameplay framework and subsystem queue. The agent must
stay at framework level.

### Required JSON

```json
{
  "schema_version": "1.0",
  "artifact_type": "gameplay_framework",
  "player_goal": "",
  "session_structure": "",
  "core_loop": [],
  "main_actions": [],
  "progression_frame": {},
  "resource_or_state_frame": {},
  "challenge_frame": {},
  "feedback_frame": {},
  "failure_and_recovery": {},
  "content_scope": {},
  "subsystem_list": [],
  "framework_questions": []
}
```

### Interaction

Loop until the human approves:

```text
是否同意当前玩法框架并进入步骤2A？y/n
```

If `n`, collect revision notes and regenerate the framework.

### Outputs

```text
gameplay_framework.json
gameplay_framework.md
subsystem_queue.json
framework_revision_history.json
framework_approval.json
```

## 4. Step 2A Implementation

### Inputs

```text
gameplay_framework.json
subsystem_queue.json
```

### Agent Prompt Goal

Design exactly one subsystem at a time.

### Required JSON Per Subsystem

```json
{
  "schema_version": "1.0",
  "artifact_type": "subsystem_design",
  "system_id": "",
  "system_name": "",
  "player_purpose": "",
  "owned_actions": [],
  "owned_states": [],
  "owned_resources": [],
  "rules": [],
  "feedback": [],
  "failure_cases": [],
  "dependencies": [],
  "open_questions": [],
  "implementation_notes_for_later": []
}
```

### Interaction

For every subsystem:

```text
是否同意当前子系统设计？y=确认并设计下一个系统，n=输入修改方案后重做当前系统
```

### Outputs

```text
systems/{system_id}/system_design.json
systems/{system_id}/system_design.md
systems/{system_id}/approval.json
approved_subsystems.json
subsystem_revision_history.json
```

## 5. Step 2B Implementation

### Inputs

```text
gameplay_framework.json
approved_subsystems.json
```

### Agent Prompt Goal

Translate approved design into compact AI-readable JSON. No new gameplay facts.

### Required JSON

```json
{
  "schema_version": "1.0",
  "artifact_type": "ai_design_script",
  "game_identity": {},
  "player_loop": [],
  "systems": [],
  "actions": [],
  "states": [],
  "resources": [],
  "events": [],
  "rules": [],
  "dependencies": [],
  "terminology": [],
  "open_questions": [],
  "source_trace": []
}
```

### Validation

Implement deterministic checks:

- every system maps to `approved_subsystems`;
- every source trace points to framework or subsystem files;
- no unapproved open question appears as a rule;
- terminology IDs are unique;
- no field requires parsing Markdown prose.

### Outputs

```text
ai_design_script.json
ai_design_script.md
terminology_index.json
source_trace.json
script_validation.json
```

## 6. Step 2C Implementation

### Inputs

```text
ai_design_script.json
approved_subsystems.json
gameplay_framework.json
```

### Agent Prompt Goal

Generate development-facing system/function decomposition.

### Required JSON

```json
{
  "schema_version": "1.0",
  "artifact_type": "development_system_design",
  "development_systems": [],
  "features": [],
  "functions": [],
  "data_objects": [],
  "state_changes": [],
  "events": [],
  "ui_feedback_needs": [],
  "asset_hooks": [],
  "acceptance_checks": [],
  "dependencies": [],
  "unknowns_for_human_or_engineer": [],
  "skill_usage_plan": []
}
```

### Skill Use

Create skills only for high-repeat transformations:

- `development-system-decomposer`
- `acceptance-check-writer`
- `dev-contract-normalizer`
- `feature-overlap-reviewer`
- `system-spec-table-writer`

Do not create skills for product decisions.

### Outputs

```text
development_system_design.json
development_system_design.md
feature_matrix.json
function_inventory.json
skill_usage_plan.json
development_open_questions.json
approval.json
```

## 7. Migration Order

1. Add new status/gate helpers if existing `run_with_review_gate` cannot support selection lists and per-item notes.
2. Rewrite `idea_intake.py` for step 0 selection loop.
3. Rewrite `demo_crew.py` for framework iteration.
4. Replace `design_crew.py` phase list with `2a/2b/2c`.
5. Rewrite `design_step_2a.py`, `design_step_2b.py`, and `design_step_2c.py`.
6. Remove the old autonomous design-freeze flow.
7. Update step 3 to prefer `development_system_design.json`.
8. Add schemas for each new artifact.
9. Run a full steps 0-2 dry run before re-enabling later pipeline steps.

## 8. Acceptance Criteria

The redesign is complete when:

- step 0 can reject all, keep multiple, revise selected prototypes, and approve one;
- step 1 loops until framework approval;
- step 2A confirms every subsystem individually;
- step 2B creates AI script without adding new design facts;
- step 2C lists development systems/functions for every approved subsystem;
- all human decisions are recorded in JSON histories;
- no stage proceeds based only on an AI recommendation.
