from __future__ import annotations

from core.adapters.claude_code_model_adapter import ClaudeCodeModelAdapter
from core.adapters.codex_adapter import CodexAdapter
from core.adapters.openai_adapter import OpenAIAdapter
from core.adapters.registry import get_adapter
from core.config.ai_config import AIProfile, ImageConfig, LLMConfig
from core.config.loader import get_pipeline_adapter


def test_adapter_from_profile_openai() -> None:
    profile = AIProfile(
        id="relay",
        name="Relay",
        adapter="openai",
        llm=LLMConfig(source="api", base_url="https://relay.example/v1", api_key="sk-test", model="gpt-4o"),
        image=ImageConfig(enabled=False, source="none"),
    )

    adapter = get_adapter(profile.adapter, profile=profile)

    assert isinstance(adapter, OpenAIAdapter)
    assert adapter._config["default_model"] == "gpt-4o"


def test_adapter_from_profile_codex() -> None:
    profile = AIProfile(
        id="codex",
        name="Codex",
        adapter="codex",
        llm=LLMConfig(source="cli", cli_path="custom-codex", model="gpt-5.5"),
    )

    adapter = get_adapter(profile.adapter, profile=profile)

    assert isinstance(adapter, CodexAdapter)
    assert adapter.cli_path == "custom-codex"


def test_adapter_from_profile_claude() -> None:
    profile = AIProfile(
        id="claude",
        name="Claude",
        adapter="claude",
        llm=LLMConfig(source="cli", cli_path="custom-claude", model="claude-sonnet-4-6"),
    )

    adapter = get_adapter(profile.adapter, profile=profile)

    assert isinstance(adapter, ClaudeCodeModelAdapter)
    assert adapter.cli_path == "custom-claude"


def test_get_pipeline_adapter_uses_active_ai_profile(tmp_path, monkeypatch) -> None:
    from core.config import ai_config

    path = tmp_path / "ai_config.json"
    config = ai_config.create_default_config()
    config.dev.active_entry_id = "codex_cli"
    ai_config.save_ai_config(config, path=path)
    monkeypatch.setattr(ai_config, "AI_CONFIG_PATH", path)

    adapter = get_pipeline_adapter()

    assert isinstance(adapter, CodexAdapter)
