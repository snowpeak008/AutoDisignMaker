"""Codex CLI backed image generation tool."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from core.paths import PROJECT_ROOT
from core.utils.base_tool import BaseTool
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs


def _codex_home(override: str | None = None) -> Path:
    value = override or os.getenv("CODEX_HOME") or os.getenv("CODEX_WORKSPACE")
    return Path(value).expanduser() if value else Path.home() / ".codex"


def _codex_command() -> str:
    command = (
        shutil.which("codex.cmd")
        or shutil.which("codex.exe")
        or shutil.which("codex")
    )
    if not command:
        raise RuntimeError("Codex CLI was not found on PATH.")
    return command


def _snapshot_pngs(directory: Path) -> dict[Path, int]:
    return {
        path: path.stat().st_mtime_ns
        for path in directory.rglob("*.png")
        if path.is_file()
    }


def _new_or_updated_pngs(directory: Path, before: dict[Path, int]) -> list[Path]:
    candidates = []
    for path in directory.rglob("*.png"):
        if not path.is_file():
            continue
        previous = before.get(path)
        current = path.stat().st_mtime_ns
        if previous is None or current > previous:
            candidates.append(path)
    return candidates


def _saved_pngs_from_output(text: str) -> list[Path]:
    saved_lines = [
        line
        for line in text.splitlines()
        if re.search(r"\b(saved|generated|output)\b|已保存|保存", line, re.IGNORECASE)
    ]
    paths = _png_paths_from_text("\n".join(saved_lines))
    return paths if paths else _png_paths_from_text(text)


def _png_paths_from_text(text: str) -> list[Path]:
    paths: list[Path] = []
    pattern = (
        r"(?:^|[\s:：`\"'])"
        r"((?:[A-Za-z]:\\|/)"
        r"(?:[^\r\n`<>\"'\\/:*?|]+[/\\])*"
        r"[^\r\n`<>\"'\\/:*?|]+?\.png)"
        r"(?=$|[\s`<>\"'）),.;:：，。])"
    )
    for match in re.finditer(pattern, text):
        path = Path(match.group(1).strip())
        if path.is_file():
            paths.append(path)
    return paths


def _session_pngs_from_output(text: str, generated_dir: Path) -> list[Path]:
    paths: list[Path] = []
    pattern = (
        r"session id:\s*"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    )
    for match in re.finditer(pattern, text, re.IGNORECASE):
        session_dir = generated_dir / match.group(1)
        if session_dir.is_dir():
            paths.extend(path for path in session_dir.glob("*.png") if path.is_file())
    return paths


class CodexCLIImageGenerator(BaseTool):
    name: str = "Codex CLI Image Generator"
    description: str = "通过本地 Codex CLI 内置 image_gen 工具生成图片。"

    def _run(
        self,
        prompt: str,
        output_dir: str = ".",
        output_format: str = "png",
        timeout: int = 300,
        codex_home: str | None = None,
        **_: object,
    ) -> str:
        if output_format.lower() != "png":
            raise RuntimeError("Codex CLI image generation currently supports PNG output only.")

        home = _codex_home(codex_home)
        generated_dir = home / "generated_images"
        generated_dir.mkdir(parents=True, exist_ok=True)
        before = _snapshot_pngs(generated_dir)
        task_prompt = "\n".join(
            [
                "Use the image_gen tool to generate exactly one game art style reference image.",
                "Do not edit repository files.",
                "Save the result as a PNG image.",
                "",
                "Art direction:",
                str(prompt),
            ]
        )
        result = subprocess.run(
            [
                _codex_command(),
                "exec",
                "--cd",
                str(PROJECT_ROOT),
                "--sandbox",
                "workspace-write",
                "--skip-git-repo-check",
            ],
            input=task_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            **hidden_subprocess_kwargs(
                stdin=None,
                env=child_process_env({"CODEX_HOME": str(home)}),
            ),
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Codex CLI image generation failed: {message[:500]}")

        output_text = "\n".join(
            part for part in (result.stdout or "", result.stderr or "") if part
        )
        after = _saved_pngs_from_output(output_text)
        if not after:
            after = _session_pngs_from_output(output_text, generated_dir)
        if not after:
            after = _new_or_updated_pngs(generated_dir, before)
        if not after:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or "no CLI output"
            raise RuntimeError(
                f"Codex CLI completed but no new PNG was found in {generated_dir}. {detail[:500]}"
            )

        newest = max(after, key=lambda path: path.stat().st_mtime_ns)
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / newest.name
        if dest.exists() and dest.resolve() != newest.resolve():
            dest = target_dir / f"codex_{newest.stat().st_mtime_ns}_{newest.name}"
        if dest.resolve() != newest.resolve():
            shutil.copy2(newest, dest)
        return f"saved: {dest}"
