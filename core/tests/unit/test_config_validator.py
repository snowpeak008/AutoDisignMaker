from __future__ import annotations

from types import SimpleNamespace

from core.config.ai_config import AIProfile, ImageConfig, LLMConfig
from core.config.validator import AIConfigValidator


def test_validate_openai_profile_accepts_complete_api_config() -> None:
    profile = AIProfile(
        id="relay",
        name="Relay",
        adapter="openai",
        llm=LLMConfig(source="api", base_url="https://relay.example/v1", api_key="sk-test", model="gpt-4o"),
        image=ImageConfig(enabled=False, source="none"),
    )

    result = AIConfigValidator().validate_profile(profile)

    assert result.is_valid


def test_validate_openai_profile_reports_missing_api_key() -> None:
    profile = AIProfile(
        id="relay",
        name="Relay",
        adapter="openai",
        llm=LLMConfig(source="api", base_url="https://relay.example/v1", api_key="", model="gpt-4o"),
    )

    result = AIConfigValidator().validate_profile(profile)

    assert not result.is_valid
    assert any("api_key" in item for item in result.errors)


def test_validate_cli_profile_checks_availability(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout="codex-cli 0.141.0", stderr="")

    monkeypatch.setattr(
        "core.config.validator.shutil.which",
        lambda command: "codex" if command == "codex" else None,
    )
    monkeypatch.setattr("core.config.validator.subprocess.run", fake_run)
    profile = AIProfile(
        id="codex",
        name="Codex",
        adapter="codex",
        llm=LLMConfig(source="cli", cli_path="codex", model="gpt-5.5"),
        image=ImageConfig(enabled=True, source="cli_builtin", cli_path="codex"),
    )

    result = AIConfigValidator().validate_profile(profile, check_cli=True)

    assert result.is_valid
    assert captured["args"] == ["codex", "--version"]


def test_validate_image_cli_builtin_requires_codex() -> None:
    profile = AIProfile(
        id="claude",
        name="Claude",
        adapter="claude",
        llm=LLMConfig(source="cli", cli_path="claude"),
        image=ImageConfig(enabled=True, source="cli_builtin", cli_path="claude"),
    )

    result = AIConfigValidator().validate_profile(profile)

    assert not result.is_valid
    assert any("Codex" in item for item in result.errors)
