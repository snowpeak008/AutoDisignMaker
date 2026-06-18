"""Simple file logger for the no-CrewAI pipeline."""

from __future__ import annotations

from pathlib import Path

from pipeline.state import OUTPUTS_DIR, now_iso


class PipelineLogger:
    def __init__(self) -> None:
        self.log_dir = OUTPUTS_DIR / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "pipeline.log"

    def info(self, message: str) -> None:
        line = f"[{now_iso()}] {message}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def error(self, message: str) -> None:
        self.info("ERROR: " + message)
