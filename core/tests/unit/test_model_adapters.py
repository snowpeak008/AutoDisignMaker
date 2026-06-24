from __future__ import annotations

from types import SimpleNamespace

from core.adapters.base import ModelResult, ModelTask
from core.adapters.claude_code_model_adapter import ClaudeCodeModelAdapter
from core.adapters.codex import executor as codex_executor
from core.adapters.codex.executor import run_codex_exec
from pipeline.step_02_design_review_freeze.supplement import EntitySupplementAdapter


def test_codex_command_prefers_windows_cmd_shim(monkeypatch) -> None:
    def fake_which(command: str) -> str | None:
        return {
            "codex": r"C:\Users\admin\AppData\Roaming\npm\codex.ps1",
            "codex.cmd": r"C:\Users\admin\AppData\Roaming\npm\codex.cmd",
        }.get(command)

    monkeypatch.setattr(codex_executor.shutil, "which", fake_which)

    assert codex_executor._codex_command().endswith("codex.cmd")


def test_codex_exec_defaults_to_workspace_write_sandbox(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr("core.adapters.codex.executor._codex_command", lambda: "codex")
    monkeypatch.setattr("core.adapters.codex.executor.subprocess.run", fake_run)

    result = run_codex_exec(
        ModelTask(task_id="default_sandbox", prompt="return json", timeout_seconds=12),
        tmp_path,
    )

    args = captured["args"]
    assert result.status == "success"
    assert isinstance(args, list)
    assert args[args.index("--sandbox") + 1] == "workspace-write"
    assert captured["timeout"] == 12


def test_codex_exec_uses_task_sandbox(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr("core.adapters.codex.executor._codex_command", lambda: "codex")
    monkeypatch.setattr("core.adapters.codex.executor.subprocess.run", fake_run)

    result = run_codex_exec(
        ModelTask(task_id="read_stdout", prompt="return json", sandbox="none"),
        tmp_path,
    )

    args = captured["args"]
    assert result.status == "success"
    assert isinstance(args, list)
    assert args[args.index("--sandbox") + 1] == "none"


def test_step02_supplement_uses_stdout_only_codex_sandbox(tmp_path) -> None:
    captured: dict[str, object] = {}

    class CapturingAdapter:
        def generate(self, task: ModelTask) -> ModelResult:
            captured["task"] = task
            return ModelResult(
                task_id=task.task_id,
                status="success",
                text=(
                    '{"supplemented_entities":[{"label":"冥河之刃","kind":"weapon",'
                    '"schema":"weapon.v1","node_id":"combat_node"}]}'
                ),
            )

    adapter = EntitySupplementAdapter(
        cache_dir=tmp_path,
        adapter_name="codex",
        model_adapter=CapturingAdapter(),
    )

    result = adapter.supplement(
        [],
        {"source": "test.md", "raw_text": "Hades roguelike action", "selections": []},
    )

    task = captured["task"]
    assert isinstance(task, ModelTask)
    assert task.sandbox == "none"
    assert result.fallback_used is False


def test_claude_code_model_adapter_uses_task_timeout(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(
        "core.adapters.claude_code_model_adapter._claude_command", lambda: "claude"
    )
    monkeypatch.setattr(
        "core.adapters.claude_code_model_adapter.subprocess.run", fake_run
    )

    adapter = ClaudeCodeModelAdapter(root=tmp_path)
    result = adapter.generate(
        ModelTask(task_id="claude_timeout", prompt="return json", timeout_seconds=7)
    )

    assert result.status == "success"
    assert captured["timeout"] == 7
