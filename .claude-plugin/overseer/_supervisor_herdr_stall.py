"""Surface a durable Herdr replacement that a tick could not advance."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _herdr_replacement_store
import _supervisor_herdr_dead_generation
import _supervisor_herdr_recovery
import _supervisor_launch
import registry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["STALL_CONDITION", "reconcile_and_alert"]

STALL_CONDITION = "herdr-replacement-stalled"


def _recorded_phase(*, track: registry.Track) -> object:
    scratch = _herdr_replacement_store.scratch_path(track=track)
    try:
        transaction = _herdr_replacement_store.read_transaction(
            path=scratch / _herdr_replacement_store.RECORD_NAME
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return "unknown"
    return "unknown" if transaction is None else transaction.get("phase")


def _stall_reason(*, row: RowView, act: bool) -> str | None:
    """Why the replacement did not advance, or None when it did.

    A refused or failed reconcile names its own reason. A read-only reconcile on an
    acting tick means the recorded pane was unavailable, so nothing could act on the
    transaction at all; that is a stall too.
    """
    if row.status == "replacement-failed":
        return row.note
    if not act:
        return "recorded Herdr pane is unavailable"
    return None


def reconcile_and_alert(
    *, sup: Supervisor, track: registry.Track, target: str, act: bool, alert: bool
) -> RowView | None:
    """Reconcile an exact durable transaction, alerting when an acting tick stalls on it.

    `alert` is the tick's own `act`, so the read-only `list` path never alerts, while an
    acting tick that can only reconcile read-only (its pane is gone) still does. The
    alert is edge-triggered by `Supervisor.alert`, so an unchanged stall reports once.

    An acting tick first retires a record whose server generation is provably gone
    (overseer-nztq44): nothing it names can be acted on again, so it would otherwise
    refuse the track forever. That runs on `alert`, not `act`, because a track still
    naming the dead generation reaches here only through the read-only reconcile.
    """
    if alert:
        _ = _supervisor_herdr_dead_generation.retire_dead_generation(
            sup=sup, track=track, target=target
        )
    row = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=sup, track=track, target=target, act=act
    )
    reason = None if row is None or not alert else _stall_reason(row=row, act=act)
    if reason is not None:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message=f"herdr replacement stalled at phase {_recorded_phase(track=track)}: {reason}",
            condition=STALL_CONDITION,
        )
    return row
