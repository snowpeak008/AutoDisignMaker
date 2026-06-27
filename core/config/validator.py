"""AI configuration validation helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

from core.config.ai_config import AIConfig, AIProfile, SUPPORTED_ADAPTERS
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def extend(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


class AIConfigValidator:
    """Validate AI profiles without making network calls."""

    def validate_profile(self, profile: AIProfile, *, check_cli: bool = False) -> ValidationResult:
        result = ValidationResult()
        if profile.adapter not in SUPPORTED_ADAPTERS:
            result.errors.append(f"Profile '{profile.name}': unsupported adapter '{profile.adapter}'")
            return result

        if profile.adapter == "openai":
            if profile.llm.source != "api":
                result.errors.append(f"Profile '{profile.name}': openai adapter requires API LLM source")
            if not profile.llm.base_url:
                result.errors.append(f"Profile '{profile.name}': missing base_url")
            if not profile.llm.api_key:
                result.errors.append(f"Profile '{profile.name}': missing api_key")
            if not profile.llm.model:
                result.errors.append(f"Profile '{profile.name}': missing model")
        elif profile.adapter in {"codex", "claude"}:
            cli_path = profile.llm.cli_path or profile.adapter
            if not cli_path:
                result.errors.append(f"Profile '{profile.name}': missing CLI path")
            elif check_cli:
                available, info = self.check_cli_availability(cli_path)
                if not available:
                    result.errors.append(f"Profile '{profile.name}': CLI '{cli_path}' is unavailable: {info}")
                else:
                    result.warnings.append(f"CLI '{cli_path}' available: {info}")
        elif profile.adapter == "local":
            result.warnings.append(f"Profile '{profile.name}': local adapter is a placeholder")

        if profile.image.enabled:
            if profile.image.source == "api":
                if not profile.image.base_url:
                    result.errors.append(f"Profile '{profile.name}': image generation missing base_url")
                if not profile.image.api_key:
                    result.errors.append(f"Profile '{profile.name}': image generation missing api_key")
                if not profile.image.model:
                    result.errors.append(f"Profile '{profile.name}': image generation missing model")
            elif profile.image.source == "cli_builtin":
                if profile.adapter != "codex":
                    result.errors.append(
                        f"Profile '{profile.name}': only Codex adapter supports built-in image generation"
                    )
            elif profile.image.source != "none":
                result.errors.append(f"Profile '{profile.name}': unsupported image source '{profile.image.source}'")
        return result

    def validate_config(self, config: AIConfig, *, check_cli: bool = False) -> ValidationResult:
        result = ValidationResult()
        if config.schema_version != 2:
            result.errors.append(f"Unsupported AI config schema_version: {config.schema_version}")
        if not config.profiles:
            result.errors.append("AI config has no profiles")
            return result
        profile_ids = [profile.id for profile in config.profiles]
        if len(profile_ids) != len(set(profile_ids)):
            result.errors.append("AI config profile IDs must be unique")
        if config.active_profile_id not in set(profile_ids):
            result.errors.append(f"Active AI profile does not exist: {config.active_profile_id}")
        for profile in config.profiles:
            result.extend(self.validate_profile(profile, check_cli=check_cli))
        return result

    def check_cli_availability(self, cli_path: str) -> tuple[bool, str]:
        command = self._resolve_cli(cli_path)
        if not command:
            return False, "not found on PATH"
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                **hidden_subprocess_kwargs(env=child_process_env()),
            )
        except Exception as exc:
            return False, str(exc)
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            return False, output or f"exit code {result.returncode}"
        return True, output or command

    def _resolve_cli(self, cli_path: str) -> str:
        if cli_path == "codex":
            return shutil.which("codex.cmd") or shutil.which("codex.exe") or shutil.which("codex") or ""
        command = shutil.which(cli_path)
        if command:
            return command
        from pathlib import Path

        custom_path = Path(cli_path).expanduser()
        return str(custom_path) if custom_path.exists() else ""
