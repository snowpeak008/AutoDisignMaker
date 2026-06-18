"""Shared subprocess helpers for GUI-safe background execution."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Mapping


def child_process_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if extra:
        env.update(extra)
    return env


def hidden_subprocess_kwargs(
    *,
    stdin: Any = subprocess.DEVNULL,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return kwargs that keep console subprocesses hidden on Windows."""
    kwargs: dict[str, Any] = {}
    if stdin is not None:
        kwargs["stdin"] = stdin
    if env is not None:
        kwargs["env"] = dict(env)
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs
