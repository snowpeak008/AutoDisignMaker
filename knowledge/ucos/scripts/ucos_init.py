from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_IDS = [
    "working_memory",
    "stm_entry",
    "episode",
    "semantic_fact",
    "pattern",
    "failure",
    "skill",
    "goal",
    "plan",
    "task",
]


ATOMIC_SKILLS = [
    ("read_file", ["file", "read"], ["file_path"], ["devflow", "pipeline"]),
    ("write_file", ["file", "write"], ["file_path", "content"], ["devflow"]),
    ("search", ["search", "text"], ["query"], ["devflow", "pipeline"]),
    ("summarize", ["summary"], ["content"], ["devflow"]),
    ("generate_json", ["json", "generate"], ["schema", "content"], ["devflow"]),
    ("validate_schema", ["json", "schema", "validate"], ["target_path"], ["devflow", "pipeline"]),
    ("diff_compare", ["diff"], ["left", "right"], ["devflow"]),
    ("extract_facts", ["facts"], ["content"], ["devflow"]),
    ("tag_classify", ["tags"], ["content"], ["devflow"]),
    ("run_command", ["command"], ["command"], ["devflow", "pipeline"]),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="devflow")
    args = parser.parse_args(argv)
    root = Path.cwd()
    initialize(root, args.domain)
    print(f"[ucos_init] initialized UCOS at {root / 'ucos'} for domain={args.domain}")
    return 0


def initialize(root: Path, domain: str = "devflow") -> None:
    now = _now()
    pipeline_total = _pipeline_total(root)
    dirs = [
        "ucos/identity",
        "ucos/knowledge/working",
        "ucos/knowledge/short_term/entries",
        "ucos/knowledge/episodic/episodes",
        "ucos/knowledge/semantic/staging",
        "ucos/knowledge/semantic/facts",
        "ucos/knowledge/patterns/entries",
        "ucos/knowledge/failures/entries",
        "ucos/capability/skills/atomic",
        "ucos/capability/skills/procedure",
        "ucos/capability/skills/domain",
        "ucos/capability/skills/expert",
        "ucos/capability/skills/meta",
        "ucos/execution/world_model/domain_models",
        "ucos/execution/goals",
        "ucos/execution/plans",
        "ucos/execution/workflows",
        "ucos/output/formatters",
        "ucos/adapters",
        "ucos/engines",
        "ucos/schemas",
        "ucos/plugins/devflow/knowledge",
        "ucos/plugins/devflow/skills",
        "ucos/plugins/devflow/schemas",
        "ucos/scripts",
        "ucos/_checkpoints",
        ".claude",
    ]
    for directory in dirs:
        (root / directory).mkdir(parents=True, exist_ok=True)

    for schema_id in SCHEMA_IDS:
        _write_json(root / "ucos" / "schemas" / f"{schema_id}.schema.json", _schema(schema_id))

    _write_json(
        root / "ucos" / "identity" / "profile.json",
        {
            "schema_version": "1.0",
            "identity_id": "ucos_default",
            "role": "GameArchitect",
            "principles": [
                "Contract First",
                "Fact Driven",
                "Explicit Structure",
                "Source Traceability",
                "Domain Agnostic",
                "AI Native Architecture",
            ],
            "philosophy": "先设计契约，再写实现；所有结论来自事实，不来自假设",
            "updated_at": now[:10],
        },
    )
    _write_json(
        root / "ucos" / "identity" / "constraints.json",
        {
            "schema_version": "1.0",
            "forbidden_actions": [
                {"action": "edit_generated_files", "targets": ["CLAUDE.md", "AGENTS.md", "README.md"], "reason": "由 ucos_sync.py 生成"},
                {"action": "delete_registry", "targets": ["artifact_layer/registry.json"], "reason": "产物依赖图权威来源"},
                {"action": "restore_deprecated", "targets": ["*_crew.py"], "reason": "已废弃架构"},
                {"action": "bypass_orchestrator", "targets": ["outputs/"], "reason": "必须通过治理入口"},
            ],
        },
    )
    _write_json(
        root / "ucos" / "identity" / "objectives.json",
        {
            "schema_version": "1.0",
            "objectives": [
                "Build a reusable cognitive substrate for DevFlow and future AI workflows.",
                "Keep decisions traceable to explicit facts and constraints.",
            ],
            "updated_at": now,
        },
    )
    _write_json(
        root / "ucos" / "identity" / "policy.json",
        {
            "schema_version": "1.0",
            "autonomy_level": 1,
            "levels": {
                "0": "只读+建议，任何写操作需人工确认",
                "1": "自动写 Working/STM；Semantic 写入 staging 区，需人工 merge",
                "2": "全自动写入，定期 human review",
            },
            "auto_write_tiers": ["working", "short_term"],
            "staged_write_tiers": ["semantic"],
            "human_review_interval_days": 7,
        },
    )

    _write_json(
        root / "ucos" / "knowledge" / "working" / "context.json",
        {
            "schema_version": "1.0",
            "session_id": f"sess_{datetime.now():%Y%m%d}_bootstrap",
            "domain": domain,
            "active_save_id": "",
            "active_save_name": "",
            "pipeline_progress": {
                "passed": 0,
                "total": pipeline_total,
                "last_passed": -1,
            },
            "updated_at": now,
            "ttl_hours": 4,
        },
    )
    _write_json(root / "ucos" / "knowledge" / "working" / "blockers.json", {"schema_version": "1.0", "blockers": [], "updated_at": now})
    _write_json(root / "ucos" / "knowledge" / "working" / "next_actions.json", {"schema_version": "1.0", "actions": [], "updated_at": now})
    for path in [
        "ucos/knowledge/short_term/index.json",
        "ucos/knowledge/episodic/index.json",
        "ucos/knowledge/semantic/index.json",
        "ucos/knowledge/patterns/index.json",
        "ucos/knowledge/failures/index.json",
    ]:
        _write_json(root / path, {"schema_version": "1.0", "entries": []})
    _write_json(root / "ucos" / "knowledge" / "semantic" / "facts" / "domain_general.json", {"schema_version": "1.0", "domain": "general", "facts": []})
    _write_json(root / "ucos" / "knowledge" / "semantic" / "facts" / f"domain_{domain}.json", {"schema_version": "1.0", "domain": domain, "facts": []})

    skill_ids = []
    edges: dict[str, list[str]] = {}
    for name, capabilities, inputs, tags in ATOMIC_SKILLS:
        skill_id = f"skill_{name}_v1"
        skill_ids.append(skill_id)
        edges[skill_id] = []
        _write_json(root / "ucos" / "capability" / "skills" / "atomic" / f"{name}.json", _skill(skill_id, name, "atomic", 1, capabilities, inputs, tags))
    _write_json(root / "ucos" / "capability" / "skills" / "meta" / "skill_selector.json", _skill("skill_skill_selector_v1", "skill_selector", "meta", 5, ["skill", "select"], ["target_stage"], ["devflow", "pipeline"]))
    _write_json(root / "ucos" / "capability" / "skills" / "meta" / "workflow_composer.json", _skill("skill_workflow_composer_v1", "workflow_composer", "meta", 5, ["workflow", "compose"], ["tasks"], ["devflow", "pipeline"]))
    skill_ids.extend(["skill_skill_selector_v1", "skill_workflow_composer_v1"])
    edges["skill_skill_selector_v1"] = ["skill_search_v1"]
    edges["skill_workflow_composer_v1"] = ["skill_skill_selector_v1"]
    _write_json(root / "ucos" / "capability" / "registry.json", {"schema_version": "1.0", "skills": skill_ids, "updated_at": now})
    _write_json(root / "ucos" / "capability" / "dependency_graph.json", {"schema_version": "1.0", "edges": edges, "updated_at": now})

    nodes = [f"stage_{i:02d}" for i in range(16)]
    graph_edges = [{"from": f"stage_{i:02d}", "to": f"stage_{i + 1:02d}", "type": "precedes"} for i in range(15)]
    dependencies = {f"stage_{i:02d}": [f"stage_{j:02d}" for j in range(i)] for i in range(16)}
    _write_json(root / "ucos" / "execution" / "world_model" / "causal_graph.json", {"schema_version": "1.0", "nodes": nodes, "edges": graph_edges})
    _write_json(root / "ucos" / "execution" / "world_model" / "dependency_map.json", {"schema_version": "1.0", "dependencies": dependencies})
    _write_json(root / "ucos" / "execution" / "world_model" / "domain_models" / f"{domain}_model.json", {"schema_version": "1.0", "domain": domain, "stages": nodes})
    _write_json(root / "ucos" / "execution" / "active_session.json", {"schema_version": "1.0", "active_goal_id": "", "active_plan_id": "", "updated_at": now})

    _write_json(root / "ucos" / "plugins" / "devflow" / "plugin.json", {"schema_version": "1.0", "plugin_id": "devflow", "domain": "devflow", "skills_path": "skills", "knowledge_path": "knowledge", "schemas_path": "schemas", "status": "active"})
    _write_json(root / ".claude" / "settings.json", _claude_settings(root))


def _schema(schema_id: str) -> dict[str, Any]:
    common = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"ucos/schemas/{schema_id}.schema.json",
        "type": "object",
        "required": ["schema_version"],
        "properties": {"schema_version": {"type": "string"}},
        "additionalProperties": True,
    }
    required_by_schema = {
        "working_memory": ["schema_version", "session_id", "domain", "pipeline_progress", "updated_at"],
        "stm_entry": ["schema_version", "stm_id", "type", "title", "content", "source", "importance", "created_at", "last_accessed", "current_relevance"],
        "episode": ["schema_version", "episode_id", "title", "domain", "goal", "outcome", "created_at"],
        "semantic_fact": ["schema_version", "fact_id", "type", "fact", "source", "confidence", "review_required", "version", "created_at"],
        "pattern": ["schema_version", "pattern_id", "name", "category", "domain", "problem", "solution", "source_episodes", "confidence", "created_at"],
        "failure": ["schema_version", "failure_id", "title", "status", "severity", "domain", "failure", "created_at"],
        "skill": ["skill_id", "name", "type", "level", "version", "status", "domain", "description", "capabilities", "dependencies", "trigger_rule", "input_schema", "output_schema", "anti_patterns", "episode_refs"],
        "goal": ["schema_version", "goal_id", "title", "domain", "description", "success_criteria", "created_at", "status"],
        "plan": ["schema_version", "plan_id", "goal_id", "tasks", "created_at", "fact_snapshot_hash"],
        "task": ["schema_version", "task_id", "title", "required_skills", "dependencies", "status"],
    }
    common["required"] = required_by_schema.get(schema_id, common["required"])
    return common


def _skill(skill_id: str, name: str, skill_type: str, level: int, capabilities: list[str], inputs: list[str], tags: list[str]) -> dict[str, Any]:
    return {
        "skill_id": skill_id,
        "name": name,
        "type": skill_type,
        "level": level,
        "version": "1.0.0",
        "status": "active",
        "domain": "general" if skill_type in {"atomic", "meta"} else "devflow",
        "description": f"Bootstrap skill for {name}.",
        "capabilities": capabilities,
        "dependencies": [],
        "trigger_rule": {"required_context_tags": tags, "required_inputs": inputs, "confidence_threshold": 0.7},
        "input_schema": {"type": "object", "properties": {item: {"type": "string"} for item in inputs}, "required": inputs},
        "output_schema": {"type": "object", "properties": {}, "required": []},
        "anti_patterns": [],
        "episode_refs": [],
    }


def _claude_settings(root: Path) -> dict[str, Any]:
    sync_path = root / "ucos" / "scripts" / "ucos_sync.py"
    command = f'python "{sync_path}"'
    return {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [{"type": "command", "command": f"{command} --event post_tool"}],
                }
            ],
            "Stop": [
                {
                    "matcher": ".*",
                    "hooks": [{"type": "command", "command": f"{command} --event session_end"}],
                }
            ],
        }
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pipeline_total(root: Path) -> int:
    try:
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        from core.registry import max_step_number

        return max_step_number() + 1
    except Exception:
        return 18


if __name__ == "__main__":
    raise SystemExit(main())
