# No-CrewAI Pipeline Refactor Development Plan

## Decision Summary

This refactor is necessary.

The current project has repeatedly failed in CrewAI-managed phases because large context, sequential agent orchestration, and remote model timeouts are coupled into one execution layer. The project should keep the useful concepts from the old flow, such as agents, skills, staged outputs, validation, review, rollback, and frozen design contracts, but remove CrewAI as the runtime dependency.

The new system will be controlled by:

```text
python pipeline.py
```

The new execution model:

```text
ProjectController
-> Workflow Engine
-> Stage
-> Artifact
-> Task
-> Executor
-> Adapter.generate()
-> Reviewer
-> Validator
```

Codex becomes the primary execution worker for code and file generation. Other models can still be used through adapters with a shared `generate()` interface.

## Required Repository Layout

Target root:

```text
<legacy-newdemotower>/
```

New layout:

```text
project/
鈹溾攢鈹€ pipeline.py
鈹溾攢鈹€ pipeline/
鈹?  鈹溾攢鈹€ controller.py
鈹?  鈹溾攢鈹€ workflow.py
鈹?  鈹溾攢鈹€ state.py
鈹?  鈹溾攢鈹€ registry.py
鈹?  鈹溾攢鈹€ checkpoint.py
鈹?  鈹溾攢鈹€ rollback.py
鈹?  鈹溾攢鈹€ logger.py
鈹?  鈹斺攢鈹€ contracts.py
鈹溾攢鈹€ stages/
鈹?  鈹溾攢鈹€ stage_00_idea.py
鈹?  鈹溾攢鈹€ stage_01_framework.py
鈹?  鈹溾攢鈹€ stage_02_design.py
鈹?  鈹溾攢鈹€ stage_03_program_requirements.py
鈹?  鈹溾攢鈹€ stage_04_art_requirements.py
鈹?  鈹溾攢鈹€ stage_05_program_review.py
鈹?  鈹溾攢鈹€ stage_06_art_review.py
鈹?  鈹溾攢鈹€ stage_07_program_plan.py
鈹?  鈹溾攢鈹€ stage_08_art_plan.py
鈹?  鈹溾攢鈹€ stage_09_asset_alignment.py
鈹?  鈹溾攢鈹€ stage_10_code_execution.py
鈹?  鈹斺攢鈹€ stage_11_art_execution.py
鈹溾攢鈹€ docs/
鈹?  鈹溾攢鈹€ governance/
鈹?  鈹斺攢鈹€ plans/
鈹溾攢鈹€ outputs/
鈹?  鈹溾攢鈹€ state/
鈹?  鈹溾攢鈹€ logs/
鈹?  鈹溾攢鈹€ checkpoints/
鈹?  鈹溾攢鈹€ artifacts/
鈹?  鈹斺攢鈹€ reviews/
鈹溾攢鈹€ prompts/
鈹?  鈹溾攢鈹€ agents/
鈹?  鈹溾攢鈹€ stages/
鈹?  鈹斺攢鈹€ reviewers/
鈹溾攢鈹€ adapters/
鈹?  鈹溾攢鈹€ base.py
鈹?  鈹溾攢鈹€ codex_adapter.py
鈹?  鈹溾攢鈹€ openai_adapter.py
鈹?  鈹溾攢鈹€ local_adapter.py
鈹?  鈹斺攢鈹€ registry.py
鈹溾攢鈹€ codex/
鈹?  鈹溾攢鈹€ executor.py
鈹?  鈹溾攢鈹€ task_builder.py
鈹?  鈹溾攢鈹€ file_guard.py
鈹?  鈹斺攢鈹€ result_parser.py
鈹斺攢鈹€ knowledge/
    鈹溾攢鈹€ core_rules/
    鈹溾攢鈹€ design_decisions/
    鈹溾攢鈹€ frozen_contracts/
    鈹溾攢鈹€ naming_conventions/
    鈹斺攢鈹€ runtime_standards/
```

The existing `Shared/`, `Docs/`, `tools/`, and `*_crew.py` files should remain during migration as source references and compatibility artifacts. They should not be the new runtime entrypoint.

## Priority 1: Remove CrewAI Runtime Influence

This is the first implementation priority.

### Why

The current failures are not isolated prompt issues. The failure pattern is structural:

- CrewAI holds the phase together as one model-driven process.
- CrewAI retries hide the real phase boundary.
- CrewAI task outputs are only available after whole task completion.
- A single model timeout can invalidate a large amount of work.
- Tools are wrapped in `BaseTool`, making them look CrewAI-specific even when they are normal Python or CLI operations.

### Required Changes

Create new scripts that do not import:

```text
crewai
crewai_tools
Agent
Task
Crew
Process
LLM
```

The old files can stay temporarily:

```text
program_requirements_crew.py
design_to_plan_crew.py
dev_supervisor_crew.py
...
```

But the new runtime must use:

```text
python pipeline.py
```

### Acceptance Criteria

```text
python pipeline.py status
python pipeline.py resume
python pipeline.py run
```

must execute without importing CrewAI.

Verification command:

```text
python -c "import pipeline; print('ok')"
```

should not require CrewAI to be installed.

## Layer 1: ProjectController

ProjectController owns project state. It does not generate content.

Responsibilities:

- Current project status
- Current stage
- Frozen stage list
- Rollback status
- Log paths
- Current artifact registry
- Human approval state
- Last successful checkpoint

State file:

```text
outputs/state/project_state.json
```

State shape:

```json
{
  "project_id": "newdemotower",
  "current_stage": 3,
  "status": "in_progress",
  "frozen_stages": [0, 1, 2],
  "rollback": {
    "active": false,
    "target_stage": null
  },
  "last_checkpoint": "outputs/checkpoints/stage_02_accepted",
  "updated_at": "2026-06-07T00:00:00"
}
```

## Layer 2: Workflow Engine

Workflow Engine strictly executes stages in sequence.

Rule:

```text
No stage skipping.
```

Allowed commands:

```text
python pipeline.py status
python pipeline.py run
python pipeline.py resume
python pipeline.py review
python pipeline.py rollback --stage N
```

Disallowed by default:

```text
python pipeline.py --stage 7
python pipeline.py run --skip
```

The only legal execution target is `current_stage`.

If stage 3 fails, the engine can only:

```text
resume stage 3
retry failed artifact/task in stage 3
rollback to an earlier checkpoint
```

It cannot continue to stage 4.

## Layer 3: Artifact Layer

This optimization is necessary.

### Reason

The old model treats a stage as one success/failure unit. That is not enough.

Example:

```text
Stage 3 success
!=
contracts.md, systems.md, entities.md, events.md, authority.md,
acceptance_criteria.md, and program_requirements_contract.json are all correct.
```

Each stage must contain artifacts. Each artifact must have:

- Inputs
- Outputs
- Generator task
- Reviewer task
- Validator
- Status
- Retry count
- Dependencies
- Checkpoint path

Stage 3 should be represented as:

```text
stage_03_program_requirements
鈹溾攢鈹€ artifact: contracts
鈹溾攢鈹€ artifact: program_structure_spec
鈹溾攢鈹€ artifact: systems
鈹溾攢鈹€ artifact: entities
鈹溾攢鈹€ artifact: events
鈹溾攢鈹€ artifact: authority
鈹溾攢鈹€ artifact: acceptance_criteria
鈹溾攢鈹€ artifact: program_requirements
鈹斺攢鈹€ artifact: program_requirements_contract
```

Artifact state:

```json
{
  "artifact_id": "stage_03.events",
  "stage": 3,
  "status": "validated",
  "inputs": [
    "outputs/artifacts/stage_03/contracts.md",
    "outputs/artifacts/stage_03/systems_index.json"
  ],
  "outputs": [
    "outputs/artifacts/stage_03/events.md"
  ],
  "validator": "validate_events",
  "reviewer": "review_events",
  "dependencies": [
    "stage_03.contracts",
    "stage_03.systems"
  ]
}
```

## Layer 4: Task Execution

Each artifact is produced by one or more tasks.

Task types:

```text
generate
review
validate
repair
assemble
freeze
rollback
```

Task executor responsibilities:

- Build task context from input files
- Call selected adapter
- Enforce allowed output paths
- Save stdout/stderr/model output
- Save before/after file manifests
- Run reviewer
- Run validator
- Decide whether repair is needed

## Layer 5: Model Adapters

This optimization is necessary.

All model calls must go through:

```python
generate(task: ModelTask) -> ModelResult
```

Adapters:

```text
CodexAdapter
OpenAIAdapter
LocalAdapter
NullAdapter
```

Codex is the primary executor because it can inspect files and write outputs.

Other models are optional helpers. They should return structured text or JSON, not control the workflow.

ModelTask:

```json
{
  "task_id": "stage_03.events.generate",
  "agent_id": "event_designer",
  "input_files": [],
  "output_files": [],
  "allowed_write_paths": [],
  "prompt": "",
  "timeout_seconds": 1800
}
```

## Codex Execution Layer

Codex should handle:

- Code writing
- File generation
- Artifact repair
- Local context reading
- Diff-based edits

Codex must not decide workflow success.

Codex command shape:

```text
codex exec --cd <legacy-newdemotower> --sandbox workspace-write -
```

For code execution stages, Codex may use:

```text
--sandbox danger-full-access
```

only when target paths are explicitly constrained by `allowed_write_paths`.

## Agent Preservation Without CrewAI

Agent behavior is preserved as prompt/config files.

Directory:

```text
prompts/agents/
```

Example:

```yaml
agent_id: event_designer
role: Event Designer
goal: Define cross-system events from contracts and system feature indexes.
preferred_adapter: codex
fallback_adapter: openai
capabilities:
  - read_files
  - generate_markdown
  - write_declared_outputs
constraints:
  - Do not invent systems.
  - Bind events to existing contracts.
  - Write only declared output files.
```

This preserves agent specialization without CrewAI.

## Skill Preservation Without CrewAI

This is necessary.

Existing tool capabilities should be converted from CrewAI tools into normal Python modules and optional CLI commands.

Old pattern:

```text
class CompileChecker(BaseTool)
```

New pattern:

```text
def run_compile_check(...)
python -m tools.compile_checker ...
```

Priority tools to preserve:

```text
CompileChecker
GitCLI
Image2Generator
SpriteSheetSlicer
SpriteAtlasPacker
ImageMetadataChecker
EnvironmentChecker
contract_validator
pipeline_execution
snapshot_manager
```

CrewAI wrappers can remain temporarily, but new flow must call pure Python functions or CLI commands.

## Dependency Graph

This optimization is necessary, but not for skipping stages.

The whole workflow remains strictly sequential:

```text
Stage 0 -> Stage 1 -> Stage 2 -> Stage 3 -> ...
```

Inside a stage, artifacts and tasks can use a dependency graph:

```text
contracts
  -> events
  -> program_requirements

systems
  -> events
  -> acceptance
  -> program_requirements

entities
  -> authority
  -> program_requirements
```

Benefits:

- Retry only failed artifact
- Validate artifact dependencies
- Avoid regenerating already valid files
- Support parallel generation inside one stage later
- Detect stale downstream artifacts after upstream changes

Rule:

```text
Dependency graph is allowed inside a stage.
Dependency graph must not allow stage skipping.
```

## Validator First

This optimization is necessary.

The right rule is not "generate then maybe validate".

The right rule:

```text
No artifact exists without a declared validator.
```

Before generating an artifact, the workflow must know:

- Expected output files
- Required schema or format
- Required references
- Forbidden references
- Validator function
- Repair policy

Artifact declaration example:

```json
{
  "artifact_id": "stage_03.program_requirements_contract",
  "outputs": [
    "outputs/artifacts/stage_03/program_requirements_contract.json"
  ],
  "validator": "validate_program_requirements_contract",
  "schema": "docs/governance/schemas/program_requirements_contract.schema.json"
}
```

Generator prompt should include validator requirements before generation.

## Review Pipeline

This optimization is necessary for AI output.

Old:

```text
Generator -> Validator
```

New:

```text
Generator -> Reviewer -> Validator
```

Reviewer role:

- Catch semantic drift
- Catch missing design coverage
- Catch incorrect assumptions
- Check consistency with frozen contracts
- Produce review report

Validator role:

- Schema
- Required fields
- ID references
- Path boundaries
- Frozen file protection
- Deterministic checks

Reviewer can use a model.

Validator must be deterministic Python wherever possible.

## Semantic Memory / Project Knowledge Base

This optimization is necessary.

This is not CrewAI memory. It is a versioned project knowledge base.

Directory:

```text
knowledge/
鈹溾攢鈹€ core_rules/
鈹溾攢鈹€ design_decisions/
鈹溾攢鈹€ frozen_contracts/
鈹溾攢鈹€ naming_conventions/
鈹斺攢鈹€ runtime_standards/
```

Example:

```text
knowledge/design_decisions/Decision_014.md
```

Content:

```markdown
# Decision 014: Event System Uses Publish Subscribe

## Decision
The event system uses publish-subscribe.

## Reason
Avoid tight coupling between systems.

## Date
2026-06-07

## Affected Stages
- stage_03_program_requirements
- stage_07_program_plan
- stage_10_code_execution
```

Why needed:

- Prevent repeated rediscovery
- Keep design decisions stable across stages
- Make frozen contracts readable by Codex and validators
- Reduce prompt size by retrieving only relevant decisions

## Revised Stage 3 Plan

This should be the first migrated functional stage because current work is blocked there.

Stage 3 artifacts:

```text
3.1 contracts
3.2 program_structure_spec
3.3 systems
3.4 entities
3.5 events
3.6 authority
3.7 acceptance_criteria
3.8 program_requirements
3.9 program_requirements_contract
3.10 validation_report
```

Current reusable files:

```text
Shared/Demo_tower_ProgReq_20260607_v1/contracts.md
Shared/Demo_tower_ProgReq_20260607_v1/program_structure_spec.md
Shared/Demo_tower_ProgReq_20260607_v1/systems.md
Shared/Demo_tower_ProgReq_20260607_v1/entities.md
```

Migration behavior:

```text
If valid existing artifacts are found, import them into outputs/artifacts/stage_03/.
Then generate only missing artifacts.
```

No-CrewAI Stage 3 execution:

```text
python pipeline.py run
```

Expected internal execution:

```text
ProjectController loads state
Workflow Engine sees current_stage = 3
Stage 3 loads artifact graph
Existing contracts/systems/entities imported and validated
Codex generates events.md
Reviewer reviews events.md
Validator validates events.md
Codex generates authority.md
Reviewer reviews authority.md
Validator validates authority.md
Codex generates acceptance chunks
Python assembles acceptance_criteria.md
Python assembles program_requirements.md
Python writes program_requirements_contract.json
Validator validates contract JSON
ProjectController marks stage 3 success
```

## Migration Phases

### Phase A: Foundation

Create structure:

```text
pipeline.py
pipeline/
stages/
outputs/
prompts/
adapters/
codex/
knowledge/
```

Implement:

```text
ProjectController
WorkflowEngine
ArtifactRegistry
TaskExecutor
ModelAdapter base
CodexAdapter
Logger
CheckpointManager
```

Acceptance:

```text
python pipeline.py status
python pipeline.py run
```

works without CrewAI imports.

### Phase B: Stage 3 Migration

Implement:

```text
stages/stage_03_program_requirements.py
```

Support importing current partial outputs from:

```text
Shared/Demo_tower_ProgReq_20260607_v1/
```

Acceptance:

```text
python pipeline.py run
```

produces:

```text
outputs/artifacts/stage_03/events.md
outputs/artifacts/stage_03/authority.md
outputs/artifacts/stage_03/acceptance_criteria.md
outputs/artifacts/stage_03/program_requirements.md
outputs/artifacts/stage_03/program_requirements_contract.json
outputs/artifacts/stage_03/validation_report.json
```

### Phase C: Stage 7 and Stage 10 Migration

Stage 7:

```text
program_plan_index
PLAN-xxx.md files
dependency graph
path bindings
```

Stage 10:

```text
Codex executes one PLAN at a time
path guard enforces output_files
compile/test validator runs after each plan
reviewer checks code against plan
```

### Phase D: Remove Runtime CrewAI Imports

After new stages are working, old CrewAI scripts move to:

```text
legacy/crewai/
```

New runtime files must not import CrewAI.

Acceptance:

```text
rg "from crewai|crewai_tools|Crew\\(|Agent\\(|Task\\(" pipeline stages adapters codex
```

returns no matches.

## Risk Assessment

### Artifact Layer

Needed. Without it, stage success is too coarse.

### Dependency Graph

Needed inside stages. Not needed across stages except the existing sequential order.

### Validator First

Needed. Without declared validators, AI output quality is unverifiable.

### Semantic Memory

Needed. It should be a project knowledge base, not chat memory.

### Review Pipeline

Needed. Validator catches deterministic errors; reviewer catches semantic errors.

### Full CrewAI Removal

Needed for the new runtime. Keeping old scripts as references is acceptable during migration.

## Initial Implementation Scope

Do not migrate everything at once.

First executable target:

```text
No-CrewAI Stage 3 completion
```

The first implementation should not touch Unity code generation or art production.

## Go / No-Go Checklist

Before implementation starts, confirm:

```text
[ ] Use <legacy-newdemotower> as root
[ ] Keep old *_crew.py files during phase A/B
[ ] New entrypoint is python pipeline.py
[ ] No stage skipping
[ ] Artifact layer required
[ ] Each artifact has validator before generator
[ ] Review pipeline required
[ ] Codex is primary executor
[ ] Existing Stage 3 partial files may be imported
[ ] Old Shared outputs stay available for compatibility
```


