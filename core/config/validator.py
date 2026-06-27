"""AI configuration validation helpers."""

from __future__ import annotations

import shutil
import subprocess
import json
from dataclasses import dataclass, field

from core.config.ai_config import (
    APIEntry,
    AIConfig,
    AIProfile,
    API_CONFIG_TYPES,
    CODEX_FILE_CONFIG_TYPES,
    CUSTOM_CONFIG_TYPES,
    LOCAL_CLI_TYPES,
    SUPPORTED_ADAPTERS,
    TYPE_LABELS,
)
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

    def validate_entry(self, entry: APIEntry, *, check_cli: bool = False) -> ValidationResult:
        result = ValidationResult()
        label = entry.label or TYPE_LABELS.get(entry.config_type, entry.id)
        if entry.config_type in LOCAL_CLI_TYPES:
            cli_path = "claude" if "claude" in entry.config_type else "codex"
            if check_cli:
                available, info = self.check_cli_availability(cli_path)
                if not available:
                    result.errors.append(f"{label}: CLI '{cli_path}' is unavailable: {info}")
                else:
                    result.warnings.append(f"CLI '{cli_path}' available: {info}")
        elif entry.config_type in API_CONFIG_TYPES:
            if not entry.api_url:
                result.errors.append(f"{label}: missing api_url")
            if not entry.api_key:
                result.errors.append(f"{label}: missing api_key")
        if entry.config_type in CUSTOM_CONFIG_TYPES and entry.extra_json.strip():
            try:
                data = json.loads(entry.extra_json)
            except json.JSONDecodeError as exc:
                result.errors.append(f"{label}: invalid extra_json ({exc.msg})")
            else:
                if not isinstance(data, dict):
                    result.errors.append(f"{label}: extra_json must be a JSON object")
        if entry.config_type in CODEX_FILE_CONFIG_TYPES:
            pass
        return result

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
        if config.schema_version != 3:
            result.errors.append(f"Unsupported AI config schema_version: {config.schema_version}")
        for category in (config.dev, config.image, config.completion):
            entry_ids = [entry.id for entry in category.entries]
            if len(entry_ids) != len(set(entry_ids)):
                result.errors.append(f"{category.category_id}: entry IDs must be unique")
            if category.active_entry_id and category.active_entry_id not in set(entry_ids):
                result.errors.append(f"{category.category_id}: active entry does not exist")
            for entry in category.entries:
                if entry.id == category.active_entry_id:
                    result.extend(self.validate_entry(entry, check_cli=check_cli))
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
