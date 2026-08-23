"""Fleet-level attention for multiple failed dispatch wait premises."""

from __future__ import annotations

from dataclasses import dataclass

from _supervisor_view import RowView
from _supervisor_wait_target_status import WAIT_TARGET_MISSING_STATUS

__all__: list[str] = [
    "DISPATCH_QUIET_WITH_WAITERS_STATUS",
    "all_clear_relay_text",
    "apply_dispatch_quiet_with_waiters",
    "containment_relay_text",
]

DISPATCH_QUIET_WITH_WAITERS_STATUS = "dispatch-quiet-with-waiters"
_MIN_FAILED_WAITERS = 2
_FABRO_RUN_NOTE_PARTS = 2


@dataclass(frozen=True, kw_only=True)
class FailedWaiter:
    topic: str
    repo: str
    evidence: str


def containment_relay_text(*, evidence: str) -> str:
    return (
        "dispatch-quiet-with-waiters containment supersede-order\n"
        "evidence:\n"
        f"{evidence}\n\n"
        "hold re-dispatch for the named dispatch-shaped waits, verify forge landings "
        "from the recorded evidence, and continue non-dispatch work that does not "
        "depend on those premises.\n\n"
        "This template delivers facts only. It authorizes no restart, no daemon "
        "interlock change, and no act outside the existing foreman floors."
    )


def all_clear_relay_text(*, evidence: str) -> str:
    return (
        "dispatch-quiet-with-waiters all-clear\n"
        "evidence:\n"
        f"{evidence}\n\n"
        "At least one previously failed dispatch premise re-verified, so the aggregate "
        "fleet-level condition is clear.\n\n"
        "This template delivers facts only. It authorizes no restart, no daemon "
        "interlock change, and no act outside the existing foreman floors."
    )


def apply_dispatch_quiet_with_waiters(*, rows: list[RowView]) -> RowView | None:
    failed = [_failed_waiter(row=row) for row in rows if row.status == WAIT_TARGET_MISSING_STATUS]
    waiters = [waiter for waiter in failed if waiter is not None]
    if len(waiters) < _MIN_FAILED_WAITERS:
        return None
    return RowView(
        topic="fleet",
        repo="fleet",
        tmux=None,
        ctx=None,
        status=DISPATCH_QUIET_WITH_WAITERS_STATUS,
        note=_aggregate_note(waiters=waiters),
    )


def _failed_waiter(*, row: RowView) -> FailedWaiter | None:
    if row.note is None:
        return None
    return FailedWaiter(
        topic=row.topic,
        repo=row.repo,
        evidence=f"{row.topic}: {_target_label(note=row.note)} - {row.note}",
    )


def _target_label(*, note: str) -> str:
    parts = note.split()
    if len(parts) >= _FABRO_RUN_NOTE_PARTS and parts[0] == "fabro-run":
        return parts[1]
    return "unknown-target"


def _aggregate_note(*, waiters: list[FailedWaiter]) -> str:
    evidence = "; ".join(waiter.evidence for waiter in waiters)
    return (
        f"{len(waiters)} dispatch-shaped waits failed premise verification "
        "across the recheck window; keyed on failed remote-aware premise "
        f"verification, not local fabro process quiet; {evidence}"
    )
