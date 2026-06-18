"""OpenAI-compatible adapter."""

from __future__ import annotations

from pathlib import Path

from adapters.base import ModelAdapter, ModelResult, ModelTask
from tools.config_loader import build_llm, get_api_config


BASE_DIR = Path(__file__).resolve().parent.parent


def _read_input_files(task: ModelTask) -> str:
    chunks: list[str] = []
    for filename in task.input_files:
        path = Path(filename)
        if not path.is_absolute():
            path = BASE_DIR / path
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            chunks.append(f"### {filename}\n[read failed: {exc}]")
            continue
        chunks.append(f"### {filename}\n{text}")
    return "\n\n".join(chunks)


class OpenAIAdapter(ModelAdapter):
    def generate(self, task: ModelTask) -> ModelResult:
        try:
            cfg = get_api_config("llm")
            llm = build_llm(cfg, temperature=0.0)
            file_context = _read_input_files(task)
            prompt = task.prompt
            if file_context:
                prompt = f"{prompt}\n\nInput file contents:\n{file_context}"
            text = llm.invoke(prompt)
        except Exception as exc:
            return ModelResult(task_id=task.task_id, status="failed", errors=[str(exc)])
        return ModelResult(task_id=task.task_id, status="success", text=text)
