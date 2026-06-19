"""Minimal local tool base class used by migrated tool wrappers."""

from __future__ import annotations


class BaseTool:
    name: str = ""
    description: str = ""

    def run(self, *args, **kwargs):
        return self._run(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def _run(self, *args, **kwargs):
        raise NotImplementedError(f"{self.__class__.__name__} must implement _run().")
