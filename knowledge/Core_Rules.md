# Core Rules

- Keep `steps/step*.py` as the bottom execution contract.
- Store stage outputs under `outputs/artifacts/stage_XX/`.
- Do not fabricate missing historical artifacts; mark missing source groups explicitly.
- Every artifact must declare tasks, reviewers, validators, dependencies, and knowledge references.
- A stage-level success flag is not enough to prove all artifacts are correct.

