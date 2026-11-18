"""Which listed hosts a push pass reaches: every host behind, plus a bounded few refreshes."""

from __future__ import annotations

from caam_delivery_push_state import Host

__all__: list[str] = ["MAX_REFRESHES_PER_PASS", "bounded"]

# Refreshes of a delivery a host already holds are spread over passes rather
# than fanned out to every host at once; a new delivery is never held back.
MAX_REFRESHES_PER_PASS = 2


def bounded(*, hosts: list[Host], state: dict[str, dict[str, object]], sequence: int) -> list[Host]:
    """Every host behind `sequence`, plus at most MAX_REFRESHES_PER_PASS refreshes, oldest first."""
    refreshes = sorted(
        (host for host in hosts if _holds(entry=state.get(host.label, {}), sequence=sequence)),
        key=lambda host: _last_success(entry=state.get(host.label, {})),
    )
    fresh = [
        host for host in hosts if not _holds(entry=state.get(host.label, {}), sequence=sequence)
    ]
    return fresh + refreshes[:MAX_REFRESHES_PER_PASS]


def _holds(*, entry: dict[str, object], sequence: int) -> bool:
    applied = entry.get("sequence")
    return isinstance(applied, int) and applied >= sequence


def _last_success(*, entry: dict[str, object]) -> float:
    success = entry.get("last_success")
    return success if isinstance(success, float) else float("-inf")
