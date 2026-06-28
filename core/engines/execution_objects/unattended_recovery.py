"""Unattended recovery helpers for long-running execution stages."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config.loader import get_config
from core.engines.execution_objects.correction_queue import (
    CorrectionItem,
    CorrectionQueue,
    load_queue,
    save_queue,
    save_queue_json,
)
from core.io import now_iso, rel, write_json, write_text
from core.paths import PROJECT_ROOT


UNATTENDED_PROTOCOL = "unattended_recovery.v1"
REPRODUCTION_COMMAND = (
    "codex exec --cd {PROJECT_ROOT} --sandbox workspace-write --skip-git-repo-check"
)


@dataclass(frozen=True)
class UnattendedExecutionConfig:
    max_auto_repair_attempts: int = 2
    repair_timeout_seconds: int = 120
    continue_independent_tasks: bool = True
    continue_after_completed_with_review: bool = False
    sync_per_group: bool = True
    sync_checkpoint_every_tasks: int = 10
    sync_checkpoint_seconds: int = 600
    enable_step11_auto_repair: bool = True
    enable_step12_auto_repair: bool = False


@dataclass
class FailureEvent:
    stage: int
    task_id: str
    group_id: str
    failure_type: str
    severity: str
    retryable: bool
    auto_repairable: bool
    blocks_dependents: bool
    error_summary: str
    error_hash: str
    raw_errors: list[str]
    changed_files: list[str]
    unexpected_changes: list[str]
    verification_results: list[dict[str, Any]]
    execution_object_id: str
    reproduction_command: str
    reproduction_payload_path: str
    log_paths: list[str]


def unattended_config() -> UnattendedExecutionConfig:
    raw = get_config("pipeline.unattended_execution", {})
    if not isinstance(raw, dict):
        raw = {}
    defaults = UnattendedExecutionConfig()
    return UnattendedExecutionConfig(
        max_auto_repair_attempts=_as_int(
            raw.get("max_auto_repair_attempts"),
            defaults.max_auto_repair_attempts,
        ),
        repair_timeout_seconds=_as_int(
            raw.get("repair_timeout_seconds"),
            defaults.repair_timeout_seconds,
        ),
        continue_independent_tasks=_as_bool(
            raw.get("continue_independent_tasks"),
            defaults.continue_independent_tasks,
        ),
        continue_after_completed_with_review=_as_bool(
            raw.get("continue_after_completed_with_review"),
            defaults.continue_after_completed_with_review,
        ),
        sync_per_group=_as_bool(raw.get("sync_per_group"), defaults.sync_per_group),
        sync_checkpoint_every_tasks=_as_int(
            raw.get("sync_checkpoint_every_tasks"),
            defaults.sync_checkpoint_every_tasks,
        ),
        sync_checkpoint_seconds=_as_int(
            raw.get("sync_checkpoint_seconds"),
            defaults.sync_checkpoint_seconds,
        ),
        enable_step11_auto_repair=_as_bool(
            raw.get("enable_step11_auto_repair"),
            defaults.enable_step11_auto_repair,
        ),
        enable_step12_auto_repair=_as_bool(
            raw.get("enable_step12_auto_repair"),
            defaults.enable_step12_auto_repair,
        ),
    )


def failure_type_policy(failure_type: str) -> tuple[bool, bool]:
    policy = {
        "ai_generation_failed": (True, False),
        "adapter_timeout": (True, False),
        "package_change_failed": (False, True),
        "task_verification_failed": (False, True),
        "unity_compile_failed": (False, True),
        "execution_object_gate_failed": (False, False),
        "unexpected_file_change": (False, False),
        "asset_contract_failed": (False, False),
        "external_config_missing": (False, False),
        "operator_stop": (False, False),
    }
    return policy.get(str(failure_type), (False, False))


def infer_failure_type(record: dict[str, Any], *, default: str = "task_verification_failed") -> str:
    if record.get("unexpected_changes"):
        return "unexpected_file_change"
    if record.get("execution_note") == "Blocked by execution-object workflow before writing project files.":
        return "execution_object_gate_failed"
    package_errors = record.get("package_errors") or []
    if package_errors:
        return "package_change_failed"
    errors = _string_list(record.get("codex_errors"))
    if any("timeout" in item.lower() for item in errors):
        return "adapter_timeout"
    if errors:
        return "ai_generation_failed"
    verification = record.get("verification_results", [])
    if any(
        isinstance(item, dict) and item.get("status") not in {"passed", "deferred"}
        for item in verification
    ):
        return "task_verification_failed"
    return default


def build_failure_event(
    *,
    stage: int,
    record: dict[str, Any],
    failure_type: str | None = None,
    severity: str = "task_failed",
    reproduction_payload_path: str = "",
    log_paths: list[str] | None = None,
) -> FailureEvent:
    resolved_failure_type = failure_type or infer_failure_type(record)
    retryable, auto_repairable = failure_type_policy(resolved_failure_type)
    summary = summarize_record_error(record)
    task_id = str(record.get("task_id") or record.get("asset_id") or "unknown")
    group_id = str(record.get("group_id") or "")
    error_hash = stable_error_hash(
        stage=stage,
        task_id=task_id,
        failure_type=resolved_failure_type,
        error_summary=summary,
    )
    return FailureEvent(
        stage=stage,
        task_id=task_id,
        group_id=group_id,
        failure_type=resolved_failure_type,
        severity=severity,
        retryable=retryable,
        auto_repairable=auto_repairable,
        blocks_dependents=severity in {"task_failed", "dependency_blocking", "stage_blocking"},
        error_summary=summary,
        error_hash=error_hash,
        raw_errors=_string_list(record.get("codex_errors")) + _verification_errors(record),
        changed_files=_string_list(record.get("changed_files")),
        unexpected_changes=_string_list(record.get("unexpected_changes")),
        verification_results=[
            item for item in record.get("verification_results", []) if isinstance(item, dict)
        ],
        execution_object_id=str(record.get("execution_object_id") or ""),
        reproduction_command=REPRODUCTION_COMMAND,
        reproduction_payload_path=reproduction_payload_path,
        log_paths=log_paths or [],
    )


def write_reproduction_payload(
    out_dir: Path,
    *,
    task: dict[str, Any],
    prompt: str,
    adapter_name: str,
    timeout_seconds: int,
    allowed_write_paths: list[str],
    output_files: list[str],
    package_changes: list[dict[str, Any]],
) -> str:
    task_id = str(task.get("task_id") or "unknown")
    path = out_dir / f"reproduction_payload_{_safe_id(task_id)}.md"
    lines = [
        "# Step11 Task Reproduction Payload",
        "",
        f"- task_id: {task_id}",
        f"- adapter: {adapter_name}",
        f"- timeout_seconds: {timeout_seconds}",
        f"- generated_at: {now_iso()}",
        "",
        "## Task",
        "",
        f"- title: {task.get('title', '')}",
        f"- requirement_id: {task.get('requirement_id', '')}",
        f"- phase: {task.get('phase', '')}",
        f"- acceptance: {task.get('acceptance', '')}",
        "",
        "## Output Files",
        "",
        *_bullet_list(output_files),
        "",
        "## Allowed Write Paths",
        "",
        *_bullet_list(allowed_write_paths),
        "",
        "## Package Changes",
        "",
        "```json",
        json.dumps(package_changes, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Original Prompt",
        "",
        prompt,
        "",
    ]
    write_text(path, "\n".join(lines))
    return rel(path)


def upsert_failure_queue(
    out_dir: Path,
    *,
    stage: int,
    events: list[FailureEvent],
    reviewed_contract: str,
    source_review: str,
) -> dict[str, Any]:
    json_path = out_dir / "correction_queue.json"
    md_path = out_dir / "correction_queue.md"
    queue = load_queue(json_path)
    queue.generated_at = now_iso()
    queue.source_review = source_review
    queue.source_review_protocol = UNATTENDED_PROTOCOL
    queue.source_review_report = "unattended_execution_summary.json"
    queue.reviewed_contract = reviewed_contract
    queue.rerun_plan = {
        "required_stages": [str(stage)],
        "commands": [],
        "reason": f"Retry selected Step{stage:02d} correction items after review.",
    }

    by_id = {item.item_id: item for item in queue.items}
    config = unattended_config()
    for event in events:
        item_id = correction_id_for_event(event)
        extras = {
            "status": "pending_auto_repair" if event.auto_repairable else "needs_user_review",
            "task_id": event.task_id,
            "group_id": event.group_id,
            "execution_object_id": event.execution_object_id,
            "failure_type": event.failure_type,
            "retry_count": 0,
            "max_retries": config.max_auto_repair_attempts,
            "auto_repairable": event.auto_repairable,
            "requires_user_decision": not event.auto_repairable,
            "error_hash": event.error_hash,
            "reproduction_command": event.reproduction_command,
            "reproduction_payload_path": event.reproduction_payload_path,
            "log_paths": event.log_paths,
            "next_action": _next_action(event),
            "last_seen_at": now_iso(),
        }
        if item_id in by_id:
            existing = by_id[item_id]
            previous_retry_count = _as_int(existing.extras.get("retry_count"), 0)
            existing.severity = event.severity
            existing.detail = event.error_summary
            existing.affected_files = list(event.changed_files)
            existing.suggested_action = _next_action(event)
            extras["retry_count"] = previous_retry_count
            existing.extras.update(extras)
            continue
        item = CorrectionItem(
            item_id=item_id,
            conflict_type=event.failure_type,
            severity=event.severity,
            detail=event.error_summary,
            correction_type="auto_repair_or_review",
            suggested_action=_next_action(event),
            target_stage="devexec" if stage == 11 else "artprod",
            affected_systems=[event.task_id] if event.task_id else [],
            affected_files=list(event.changed_files),
            extras=extras,
        )
        queue.items.append(item)
        by_id[item_id] = item

    save_queue_json(queue, json_path)
    save_queue(queue, md_path)
    return queue_to_summary(queue)


def queue_to_summary(queue: CorrectionQueue) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    auto_repairable = 0
    for item in queue.items:
        status = str(item.extras.get("status") or "needs_user_review")
        statuses[status] = statuses.get(status, 0) + 1
        if item.extras.get("auto_repairable"):
            auto_repairable += 1
    return {
        "correction_count": len(queue.items),
        "status_counts": statuses,
        "auto_repairable_count": auto_repairable,
    }


def build_resume_cursor(
    *,
    stage: int,
    records: list[dict[str, Any]],
    current_group_id: str = "",
    current_task_id: str = "",
    next_task_id: str = "",
    project_state_tainted: bool = False,
    resume_policy: str | None = None,
) -> dict[str, Any]:
    failed_ids = [
        str(record.get("task_id") or "")
        for record in records
        if str(record.get("task_id") or "")
        and str(record.get("status")) in {"failed", "blocked_by_execution_object"}
    ]
    completed_count = sum(
        1 for record in records if record.get("status") in {"success", "auto_repaired"}
    )
    failed_count = len(failed_ids)
    skipped_count = sum(1 for record in records if str(record.get("status", "")).startswith("skipped"))
    resolved_policy = resume_policy or (
        "cannot_auto_resume" if project_state_tainted else "resume_from_next_unblocked_task"
    )
    return {
        "stage": stage,
        "current_group_id": current_group_id,
        "current_task_id": current_task_id,
        "next_task_id": next_task_id,
        "completed_task_count": completed_count,
        "failed_task_count": failed_count,
        "skipped_task_count": skipped_count,
        "failed_task_ids": failed_ids,
        "project_state_tainted": bool(project_state_tainted),
        "resume_policy": resolved_policy,
        "task_record_source": f"stage_{stage:02d}/DEV-*_execution.json"
        if stage == 11
        else f"stage_{stage:02d}/*_execution.json",
        "skip_report_source": "dependency_skip_report.json",
    }


def write_unattended_summary(
    out_dir: Path,
    *,
    stage: int,
    status: str,
    records: list[dict[str, Any]],
    correction_summary: dict[str, Any],
    resume_cursor: dict[str, Any],
    continue_after_completed_with_review: bool,
) -> dict[str, Any]:
    summary = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "stage": stage,
        "status": status,
        "task_count": len(records),
        "successful_task_count": sum(1 for item in records if item.get("status") == "success"),
        "auto_repaired_task_count": sum(
            1 for item in records if item.get("status") == "auto_repaired"
        ),
        "failed_task_count": sum(
            1
            for item in records
            if str(item.get("status")) in {"failed", "blocked_by_execution_object"}
        ),
        "skipped_task_count": sum(
            1 for item in records if str(item.get("status", "")).startswith("skipped")
        ),
        "review_items_count": int(correction_summary.get("correction_count") or 0),
        "correction_queue": "correction_queue.json",
        "continue_after_completed_with_review": bool(continue_after_completed_with_review),
        "resume_cursor": resume_cursor,
        "correction_summary": correction_summary,
    }
    write_json(out_dir / "unattended_execution_summary.json", summary)
    return summary


def write_pause_resume_log(
    out_dir: Path,
    *,
    stage: int,
    status: str,
    records: list[dict[str, Any]],
    resume_cursor: dict[str, Any],
    correction_summary: dict[str, Any],
    title: str,
) -> None:
    failed = [
        str(record.get("task_id") or "")
        for record in records
        if str(record.get("task_id") or "")
        and str(record.get("status")) in {"failed", "blocked_by_execution_object"}
    ]
    skipped = [
        str(record.get("task_id") or "")
        for record in records
        if str(record.get("task_id") or "")
        and str(record.get("status", "")).startswith("skipped")
    ]
    task_count = len(records)
    successful_count = sum(1 for item in records if item.get("status") == "success")
    needs_human = int(correction_summary.get("correction_count") or 0) > 0
    log = [
        f"# {title}",
        "",
        f"- Current status: {status}",
        f"- Current stage: Step{stage:02d}",
        f"- Current task: {resume_cursor.get('current_task_id') or '-'}",
        f"- Current group: {resume_cursor.get('current_group_id') or '-'}",
        f"- Next resume task: {resume_cursor.get('next_task_id') or '-'}",
        f"- Successful tasks: {successful_count}/{task_count}",
        f"- Failed tasks: {', '.join(failed) if failed else '-'}",
        f"- Skipped tasks: {', '.join(skipped) if skipped else '-'}",
        "- Re-run successful tasks: no; verified successful task records are reused.",
        f"- Resume policy: {resume_cursor.get('resume_policy')}",
        f"- Requires human review: {'yes' if needs_human else 'no'}",
        f"- Project state tainted: {str(resume_cursor.get('project_state_tainted')).lower()}",
    ]
    payloads = sorted(out_dir.glob("reproduction_payload_*.md"))
    if payloads:
        first_payload = rel(payloads[0])
        log.append(
            f"- Reproduction command: {REPRODUCTION_COMMAND} < {first_payload}"
        )
    if status == "stopped":
        log.append("- Recovery meaning: resume from next_task_id; successful tasks are reused.")
    elif status == "completed_with_review":
        log.append(
            "- Recovery meaning: resolve correction_queue.json first, then resume the first unblocked unfinished task."
        )
    elif resume_cursor.get("project_state_tainted"):
        log.append(
            "- Recovery meaning: cannot auto-resume; repair or rollback the project state first."
        )
    elif status == "blocked":
        log.append(
            "- Recovery meaning: no task-level resume point; fix the blocking prerequisite and rerun this stage."
        )
    write_text(out_dir / "pause_resume_log.md", "\n".join(log).rstrip() + "\n")


def dependency_skip_ids(
    *,
    failed_task_ids: set[str],
    current_group_id: str,
    parallel_groups: list[Any],
    dependencies: list[Any],
) -> dict[str, dict[str, Any]]:
    group_by_task: dict[str, str] = {}
    tasks_by_group: dict[str, list[str]] = {}
    group_dependencies: dict[str, set[str]] = {}
    ordered_groups: list[str] = []
    for group in parallel_groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("group_id") or "")
        if not group_id:
            continue
        ordered_groups.append(group_id)
        task_ids = [str(item) for item in group.get("task_ids", []) if str(item)]
        tasks_by_group[group_id] = task_ids
        for task_id in task_ids:
            group_by_task[task_id] = group_id
        group_dependencies[group_id] = {
            str(item) for item in group.get("depends_on_groups", []) if str(item)
        }

    direct_deps: dict[str, set[str]] = {}
    for edge in dependencies:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source and target:
            direct_deps.setdefault(target, set()).add(source)

    failed_groups = {group_by_task.get(task_id, "") for task_id in failed_task_ids}
    failed_groups.discard("")
    if current_group_id:
        failed_groups.add(current_group_id)

    skipped: dict[str, dict[str, Any]] = {}
    current_group_tasks = tasks_by_group.get(current_group_id, [])
    for task_id in current_group_tasks:
        if task_id not in failed_task_ids:
            skipped[task_id] = {
                "status": "skipped_by_failed_group",
                "blocked_by": sorted(failed_task_ids),
            }

    changed = True
    while changed:
        changed = False
        for task_id, deps in direct_deps.items():
            if task_id in failed_task_ids or task_id in skipped:
                continue
            if deps.intersection(failed_task_ids) or deps.intersection(skipped):
                skipped[task_id] = {
                    "status": "skipped_by_dependency",
                    "blocked_by": sorted(deps.intersection(failed_task_ids | set(skipped))),
                }
                changed = True

    tainted_groups = set(failed_groups)
    changed = True
    while changed:
        changed = False
        for group_id, deps in group_dependencies.items():
            if group_id in tainted_groups:
                continue
            if deps.intersection(tainted_groups):
                tainted_groups.add(group_id)
                changed = True

    for group_id in tainted_groups:
        if group_id in failed_groups:
            continue
        for task_id in tasks_by_group.get(group_id, []):
            if task_id not in failed_task_ids:
                skipped[task_id] = {
                    "status": "skipped_by_dependency",
                    "blocked_by": sorted(failed_task_ids),
                }
    return skipped


def stable_error_hash(
    *, stage: int, task_id: str, failure_type: str, error_summary: str
) -> str:
    normalized = " ".join(str(error_summary or "").lower().split())
    seed = f"{stage}|{task_id}|{failure_type}|{normalized}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def correction_id_for_event(event: FailureEvent) -> str:
    return f"CQ-ST{event.stage:02d}-{event.task_id}-{event.failure_type}-{event.error_hash}"


def summarize_record_error(record: dict[str, Any]) -> str:
    errors = _string_list(record.get("codex_errors"))
    if errors:
        return "; ".join(errors[:3])[:500]
    if record.get("unexpected_changes"):
        return f"Unexpected file changes: {', '.join(_string_list(record.get('unexpected_changes')))}"
    verification_errors = _verification_errors(record)
    if verification_errors:
        return "; ".join(verification_errors[:3])[:500]
    if record.get("error"):
        return str(record.get("error"))[:500]
    return "Task requires review."


def _verification_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for item in record.get("verification_results", []):
        if isinstance(item, dict) and item.get("status") not in {"passed", "deferred"}:
            message = item.get("message") or item.get("error") or item.get("id")
            if message:
                errors.append(str(message))
    return errors


def _next_action(event: FailureEvent) -> str:
    if event.auto_repairable:
        return "Run bounded repair prompt and repeat focused verification."
    if event.retryable:
        return "Retry the original task invocation without modifying files."
    return "Review the failure and decide whether to repair, rollback, or skip."


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value:
        return [str(value)]
    return []


def _bullet_list(values: list[str]) -> list[str]:
    return [f"- {item}" for item in values] or ["-"]


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return text or "unknown"


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _as_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
