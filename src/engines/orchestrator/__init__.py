"""Compatibility facade for the migrated DevFlow orchestrator."""

from orchestrator import main, run_range, run_step


class Orchestrator:
    """Small object wrapper around the migrated functional orchestrator API."""

    def run_range(
        self,
        from_step: int = 0,
        stop_step: int = 15,
        *,
        auto_approve: bool = True,
        skip_actual_dev_preflight: bool = False,
    ) -> int:
        return run_range(
            from_step,
            stop_step,
            auto_approve=auto_approve,
            skip_actual_dev_preflight=skip_actual_dev_preflight,
        )


__all__ = ["Orchestrator", "main", "run_range", "run_step"]

