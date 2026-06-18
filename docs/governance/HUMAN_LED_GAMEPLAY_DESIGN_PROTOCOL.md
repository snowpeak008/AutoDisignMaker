# Human-Led Gameplay Design Protocol

Version: 1.0

This protocol replaces the previous "AI freezes design facts" posture for
steps 0-2. The design phase is now human-led: AI proposes, expands, rewrites,
structures, and checks; the human selects, edits, rejects, and approves.

The goal is not to force AI to prove a complete design graph. The goal is to
help the human rapidly explore and refine gameplay, then produce structured
artifacts that downstream agents can understand.

## 1. Core Principle

AI must not make final design decisions.

AI may:

- extract creative points from a short prompt;
- generate candidate gameplay prototypes;
- rewrite candidates according to human notes;
- expand an approved idea into a gameplay framework;
- design subsystem drafts one by one;
- convert approved design into AI-readable JSON scripts;
- decompose approved systems into development-facing feature work;
- use skills for repetitive analysis, formatting, decomposition, or validation.

AI must not:

- silently choose the winning gameplay direction;
- delete candidates because it thinks they are weak;
- freeze a mechanic without human approval;
- turn unresolved ideas into committed development requirements;
- use validation failure as a reason to prune human-intended design;
- continue to the next step without explicit human approval.

## 2. New Step Map

| Stage | Name | Human Role | AI Role | Main Output |
|---|---|---|---|---|
| `0` | Creative Point And Prototype Selection | Select, reject, modify, approve entry to step 1 | Extract creative points and draft several core gameplay prototypes | `selected_play_prototype.json` |
| `1` | Gameplay Framework Iteration | Edit and approve the overall in-game framework | Build and revise the gameplay framework | `gameplay_framework.json` |
| `2A` | Subsystem Design Approval Loop | Approve each subsystem one by one | Draft and revise each subsystem | `approved_subsystems.json` |
| `2B` | AI Understanding Script Compile | Confirm structured script reflects approved design | Convert approved framework/subsystems into compact JSON scripts | `ai_design_script.json` |
| `2C` | Development System Design | Approve development-facing system/function breakdown | Decompose every system and function into development work | `development_system_design.json` |

There is no autonomous design freeze in these stages. "Freeze" means the human
has explicitly approved the current artifact for downstream use.

## 3. Step 0: Creative Point And Prototype Selection

### Input

The input may be one sentence or a few sentences:

```text
my_game_idea.txt
```

### AI Task

The agent reads the short idea and produces:

- `creative_points`: the concrete creative content points found in the text;
- `interpretation_notes`: how the agent understood ambiguous parts;
- `play_prototypes`: several simple core gameplay prototypes;
- `prototype_cards`: human-readable cards for comparison;
- `open_questions`: things the idea does not specify.

Each prototype must be small and inspectable. It should include:

```text
prototype_id
title
core_player_action
core_loop
primary_tension
failure_or_loss_condition
one_minute_play_example
why_it_matches_source
risks
what_needs_human_decision
```

### Human Gate

After prototypes are shown, the human can:

- enter `none` or `0`: reject all prototypes and regenerate;
- enter one or more IDs: keep those prototypes;
- enter modification notes for each kept prototype;
- approve one prototype to enter step 1;
- continue revising if the selected prototype is still not right.

If only one prototype is selected, the script must ask:

```text
是否进入步骤1？y=进入，n=继续输入修改方向
```

If `n`, the human enters another modification direction and step 0 repeats only
for the selected prototype. If `y`, the selected prototype becomes the step 1
input.

### Output

```text
Shared/{Project}_Concept_{date}_v{version}/
  creative_points.json
  prototype_candidates.json
  prototype_cards.md
  selected_play_prototype.json
  selection_history.json
  open_questions.json
```

## 4. Step 1: Gameplay Framework Iteration

### Input

```text
selected_play_prototype.json
selection_history.json
```

### AI Task

The agent designs the high-level in-game framework:

```text
player_goal
session_structure
core_loop
main_actions
progression_frame
resource_or_state_frame
challenge_frame
feedback_frame
failure_and_recovery
content_scope
subsystem_list
framework_questions
```

The framework is not a subsystem design and not a development plan. It is the
shape of the game as the player will experience it.

### Human Gate

The framework is shown to the human. The human can:

- approve it and enter step 2A;
- provide modification notes;
- reject it and return to step 0;
- request a narrower or wider framework.

This step loops until the human explicitly approves:

```text
是否同意当前玩法框架并进入步骤2A？y/n
```

If `n`, the human must enter a modification direction and the agent revises the
framework. The agent must not proceed to subsystem design without `y`.

### Output

```text
Shared/{Project}_GameplayFramework_{date}_v{version}/
  gameplay_framework.json
  gameplay_framework.md
  subsystem_queue.json
  framework_revision_history.json
  framework_approval.json
```

## 5. Step 2A: Subsystem Design Approval Loop

### Input

```text
gameplay_framework.json
subsystem_queue.json
```

### AI Task

The agent designs one subsystem at a time. A subsystem draft should include:

```text
system_id
system_name
player_purpose
owned_actions
owned_states
owned_resources
rules
feedback
failure_cases
dependencies
open_questions
implementation_notes_for_later
```

The agent must not design the next subsystem until the current subsystem is
approved.

### Human Gate

For each subsystem:

```text
是否同意当前子系统设计？y=确认并设计下一个系统，n=输入修改方案后重做当前系统
```

If `n`, the human enters a modification plan and the agent revises only the
current subsystem. The loop continues until every subsystem in the queue is
approved.

The human may also:

- add a new subsystem to the queue;
- remove an unapproved subsystem;
- split a subsystem;
- merge two unapproved subsystems;
- return to step 1 if the framework itself is wrong.

### Output

```text
Shared/{Project}_SubsystemDesign_{date}_v{version}/
  subsystem_queue.json
  systems/{system_id}/system_design.json
  systems/{system_id}/system_design.md
  systems/{system_id}/approval.json
  approved_subsystems.json
  subsystem_revision_history.json
```

## 6. Step 2B: AI Understanding Script Compile

### Input

```text
gameplay_framework.json
approved_subsystems.json
```

### AI Task

The agent converts approved human-facing design into compact AI-readable JSON
scripts. This is not a design decision stage. It is a translation stage.

The output should help downstream agents quickly understand:

```text
game_identity
player_loop
systems
actions
states
resources
events
rules
dependencies
terminology
open_questions
source_trace
```

The script must preserve the approved design. It may normalize, index, and
summarize; it must not add mechanics.

### Validation

Validation checks structure and traceability only:

- every JSON fact has a source in the approved framework or subsystem design;
- every system ID maps to an approved subsystem;
- no unapproved open question becomes a committed rule;
- terminology is consistent;
- downstream consumers can locate each system/function quickly.

This stage should not attempt to prove complete economic closure or complete
development feasibility. Those are later design/development questions.

### Output

```text
Shared/{Project}_AIDesignScript_{date}_v{version}/
  ai_design_script.json
  ai_design_script.md
  terminology_index.json
  source_trace.json
  script_validation.json
```

## 7. Step 2C: Development System Design

### Input

```text
ai_design_script.json
approved_subsystems.json
gameplay_framework.json
```

### AI Task

The agent designs the development-facing system breakdown. It should list every
system and every function that likely needs development work:

```text
development_systems
features
functions
data_objects
state_changes
events
ui_feedback_needs
asset_hooks
acceptance_checks
dependencies
unknowns_for_human_or_engineer
```

This is still not implementation. It is the bridge into program requirements
and planning.

### Skill Use

Skills are appropriate in high-repeat stages:

| Repetitive Work | Recommended Skill |
|---|---|
| Expand each approved subsystem into features/functions | `development-system-decomposer` |
| Convert feature descriptions into acceptance checks | `acceptance-check-writer` |
| Normalize data/event/function names | `dev-contract-normalizer` |
| Detect duplicate or overlapping features | `feature-overlap-reviewer` |
| Produce repeated per-system tables | `system-spec-table-writer` |

Skills must not choose product scope. They only expand, normalize, compare, or
format the human-approved design.

### Human Gate

The human reviews the development system design and may:

- approve it for step 3;
- request changes to specific systems/functions;
- return to step 2A for subsystem redesign;
- return to step 1 if the whole framework is wrong.

### Output

```text
Shared/{Project}_DevelopmentDesign_{date}_v{version}/
  development_system_design.json
  development_system_design.md
  feature_matrix.json
  function_inventory.json
  skill_usage_plan.json
  development_open_questions.json
  approval.json
```

## 8. State And Control Rules

Every stage writes a status file under:

```text
Shared/.checkpoints/
```

Each human gate must record:

```text
stage_id
artifact_path
status
available_actions
selected_action
human_notes
updated_at
```

Allowed statuses:

```text
generating
waiting_for_human_selection
waiting_for_human_revision
accepted
rejected_all
regenerating
failed
```

The pipeline must never treat an AI recommendation as acceptance. Acceptance
requires explicit human input.

## 9. Migration From Old Step 0-2

New flow:

```text
0 prototype selection -> 1 gameplay framework -> 2A subsystem approval
-> 2B AI design script -> 2C development system design
```

The old autonomous direction-freeze implementation has been removed from the
active code path. The early design loop is now human-led and inspectable.
