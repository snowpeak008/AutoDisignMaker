"""OpenAI-compatible adapter."""

from __future__ import annotations

from pathlib import Path

from core.adapters.base import ModelAdapter, ModelResult, ModelTask
from core.config.loader import build_llm, get_api_config, normalize_openai_base_url


BASE_DIR = Path(__file__).resolve().parents[2]


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
    def __init__(self) -> None:
        self._config: dict[str, object] | None = None

    def configure(self, **kwargs) -> "OpenAIAdapter":
        profile = kwargs.get("profile")
        if profile is not None:
            llm = getattr(profile, "llm", None)
            self._config = {
                "api_key": getattr(llm, "api_key", ""),
                "base_url": normalize_openai_base_url(getattr(llm, "base_url", "")),
                "model": f"{getattr(llm, 'provider', 'openai')}/{getattr(llm, 'model', 'gpt-5.5')}",
                "default_model": getattr(llm, "model", "gpt-5.5"),
                "provider": getattr(llm, "provider", "openai"),
                "reasoning_effort": getattr(llm, "reasoning_effort", None),
            }
            return self
        model = str(kwargs.get("model") or kwargs.get("default_model") or "gpt-5.5")
        provider = str(kwargs.get("provider") or "openai")
        self._config = {
            "api_key": str(kwargs.get("api_key") or ""),
            "base_url": normalize_openai_base_url(str(kwargs.get("base_url") or "")),
            "model": f"{provider}/{model}",
            "default_model": model,
            "provider": provider,
            "reasoning_effort": kwargs.get("reasoning_effort"),
        }
        return self

    def generate(self, task: ModelTask) -> ModelResult:
        try:
            cfg = dict(self._config or get_api_config("llm"))
            llm = build_llm(cfg, temperature=0.0)
            file_context = _read_input_files(task)
            prompt = task.prompt
            if file_context:
                prompt = f"{prompt}\n\nInput file contents:\n{file_context}"
            text = llm.invoke(prompt)
        except Exception as exc:
            return ModelResult(task_id=task.task_id, status="failed", errors=[str(exc)])
        return ModelResult(task_id=task.task_id, status="success", text=text)
