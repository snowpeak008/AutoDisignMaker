# Decision 015: Artifact Layer Wraps Migrated Steps

Date: 2026-06-07

Decision:

The artifact layer is added above the migrated 0-15 step runtime. It does not replace the bottom `steps/step*.py` execution contract.

Reason:

This preserves compatibility while allowing artifact-level task decomposition, review, validation, dependency graph scheduling, and project knowledge references.

