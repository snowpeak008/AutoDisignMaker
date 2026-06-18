# Runtime Standards

- No external agent orchestration runtime is required.
- DAG metadata is deterministic JSON.
- Reviewer output is advisory unless it marks an issue as `error`.
- Validator output is authoritative for artifact pass/fail.
- The pipeline can stay sequential while preserving dependency graph semantics.

