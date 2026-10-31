"""Surface a durable Herdr replacement that a tick could not advance."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _herdr_replacement_store
import _supervisor_herdr_dead_generation
import _supervisor_herdr_recovery
import _supervisor_launch
import _supervisor_state
import registry
import signals
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["STALL_CONDITION", "reconcile_and_alert"]

STALL_CONDITION = "herdr-replacement-stalled"
_CLAUDE_IDENTITY_FIELD_COUNT = 4


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


def _retire_out_of_band_resume(
    *, sup: Supervisor, track: registry.Track, target: str
) -> str | None:
    """Retire a stalled resume whose pane now proves a different Claude generation.

    The replacement's exact-process fence must never authorize a retry against this
    session.  It has no remaining owner once the pane proves a third generation, so
    retire the transaction and the predecessor's round without touching the pane.
    """
    scratch = _herdr_replacement_store.scratch_path(track=track)
    record = scratch / _herdr_replacement_store.RECORD_NAME
    if not record.exists():
        return None
    try:
        with _herdr_replacement_store.transaction_lock(
            path=scratch / _herdr_replacement_store.LOCK_NAME
        ):
            transaction = _herdr_replacement_store.read_transaction(path=record)
            identity = sup.claude_identity_by_session.get((target, track.topic))
            predecessor = transaction.get("predecessor") if transaction is not None else None
            successor = transaction.get("successor") if transaction is not None else None
            if not (
                transaction is not None
                and transaction.get("phase") == "resume-attempted"
                and transaction.get("runtime") == "claude"
                and transaction.get("target") == target
                and isinstance(identity, str)
                and isinstance(predecessor, dict)
                and isinstance(successor, dict)
                and identity.startswith("claude:")
                and not _matches_recorded_process(
                    identity=identity, record=cast("object", predecessor)
                )
                and not _matches_recorded_process(
                    identity=identity, record=cast("object", successor)
                )
                and _retire_recorded_round(sup=sup, track=track, transaction=transaction)
            ):
                return None
            _ = record.replace(scratch / ".herdr-replacement.retired-out-of-band.json")
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return None
    return identity


def _retire_recorded_round(
    *, sup: Supervisor, track: registry.Track, transaction: dict[str, object]
) -> bool:
    """Clear the on-disk declaration and round only while they are still the recorded ones.

    An out-of-band live session may already have declared its own `ready` or opened a
    newer round; those belong to it and survive the transaction's retirement.  False
    only when clearing the recorded round itself failed.
    """
    recorded = cast("dict[str, object]", transaction["round"])
    state = signals.read_state(repo=track.repo, topic=track.topic)
    current = registry.read_round_record(
        repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path
    )
    ready_is_recorded = state is None or (
        state.token == signals.STATE_READY and state.mtime == recorded["ready_mtime"]
    )
    round_is_recorded = (
        current.malformed_reason is None
        and current.at == recorded["round_at"]
        and current.session_identity == recorded["session_identity"]
    )
    if not (ready_is_recorded and round_is_recorded):
        return True
    return _supervisor_state.clear_state(sup=sup, track=track, preserve_round_on_failure=True)


def _matches_recorded_process(*, identity: str, record: object) -> bool:
    """Whether a Claude identity names the PID generation in a durable record."""
    process = cast("dict[str, object]", record)
    parts = identity.split(":", 3)
    return (
        len(parts) == _CLAUDE_IDENTITY_FIELD_COUNT
        and parts[0] == "claude"
        and parts[1] == str(process.get("pid"))
        and parts[2] == process.get("starttime")
    )


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
        identity = _retire_out_of_band_resume(sup=sup, track=track, target=target)
        if identity is not None:
            sup.log(
                message=(
                    f"retired stalled Herdr replacement for {track.repo}::{track.topic} "
                    f"at pane {target}; phase resume-attempted; live session {identity}"
                )
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
