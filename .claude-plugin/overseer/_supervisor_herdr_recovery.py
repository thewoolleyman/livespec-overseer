"""Reconcile a durable Herdr replacement before ordinary runtime recognition."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import _supervisor_herdr_completion
import _supervisor_herdr_launch_recovery
import _supervisor_herdr_signal_recovery
import _supervisor_herdr_successor
import herdr_identity
import registry
import signals
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["reconcile_bare_shell"]


def _row(*, track: registry.Track, note: str, status: str = "replacement-pending") -> RowView:
    return RowView(
        topic=track.topic,
        repo=track.repo,
        tmux=track.tmux,
        ctx=None,
        status=status,
        note=note,
    )


def _old_ready_still_present(*, track: registry.Track, transaction: Mapping[str, object]) -> bool:
    state = signals.read_state(repo=track.repo, topic=track.topic)
    recorded_round = cast(dict[str, object], transaction["round"])
    return (
        state is not None
        and state.token == signals.STATE_READY
        and state.mtime == recorded_round["ready_mtime"]
    )


def _recover_launch(
    *, sup: Supervisor, track: registry.Track, target: str, transaction: dict[str, object]
) -> RowView:
    try:
        reason = _supervisor_herdr_launch_recovery.launch_recorded_successor(
            sup=sup,
            track=track,
            target=target,
            transaction=transaction,
        )
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        reason = str(exc)
    if reason is not None:
        return _row(track=track, status="replacement-failed", note=reason)
    return _row(track=track, note="durable Herdr replacement phase: launch-attempted")


def _recover_signal_attempt(
    *, sup: Supervisor, track: registry.Track, target: str, transaction: dict[str, object]
) -> RowView:
    current, reason = _supervisor_herdr_signal_recovery.recover_signal_attempt(
        sup=sup,
        track=track,
        target=target,
        transaction=transaction,
    )
    if reason is not None or current is None:
        return _row(track=track, status="replacement-failed", note=reason or "invalid record")
    return _recover_launch(sup=sup, track=track, target=target, transaction=current)


def _recover_resume(
    *, sup: Supervisor, track: registry.Track, target: str, transaction: dict[str, object]
) -> RowView:
    try:
        reason = _supervisor_herdr_successor.resume_proven_successor(
            sup=sup,
            track=track,
            target=target,
            transaction=transaction,
        )
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        reason = str(exc)
    if reason is not None:
        return _row(track=track, status="replacement-failed", note=reason)
    return _row(track=track, note="durable Herdr replacement phase: completed")


def _reconcile_completed(
    *, sup: Supervisor, track: registry.Track, transaction: dict[str, object], act: bool
) -> RowView | None:
    if not _old_ready_still_present(track=track, transaction=transaction):
        return None
    if not act:
        return _row(
            track=track,
            status="replacement-failed",
            note="completed Herdr replacement still has its old ready declaration",
        )
    reason = _supervisor_herdr_completion.complete_replacement_round(sup=sup, track=track)
    if reason is not None:
        return _row(track=track, status="replacement-failed", note=reason)
    return None


def _reconcile_read_only(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> RowView:
    phase = transaction.get("phase")
    if phase == "signal-attempted":
        try:
            pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
            snapshot = pane.herdr_replacement_snapshot(session=target)
            reason = _supervisor_herdr_signal_recovery.signal_attempt_refusal(
                transaction=transaction,
                snapshot=snapshot,
            )
        except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
            reason = str(exc)
        if reason is not None:
            return _row(track=track, status="replacement-failed", note=reason)
    return _row(track=track, note=f"durable Herdr replacement phase: {phase}")


def _reconcile_active(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> RowView:
    phase = transaction.get("phase")
    if phase == "signal-attempted":
        return _recover_signal_attempt(
            sup=sup,
            track=track,
            target=target,
            transaction=transaction,
        )
    if phase == "stopped-awaiting-shell":
        return _recover_launch(sup=sup, track=track, target=target, transaction=transaction)
    if phase in {
        "launch-attempted",
        "rename-attempted",
        "successor-observed",
        "resume-attempted",
    }:
        return _recover_resume(sup=sup, track=track, target=target, transaction=transaction)
    return _row(track=track, note=f"durable Herdr replacement phase: {phase}")


def _reconcile_transaction(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
    act: bool,
) -> RowView | None:
    phase = transaction.get("phase")
    if phase == "completed":
        return _reconcile_completed(sup=sup, track=track, transaction=transaction, act=act)
    if not act:
        return _reconcile_read_only(
            sup=sup,
            track=track,
            target=target,
            transaction=transaction,
        )
    return _reconcile_active(
        sup=sup,
        track=track,
        target=target,
        transaction=transaction,
    )


def reconcile_bare_shell(
    *, sup: Supervisor, track: registry.Track, target: str, act: bool
) -> RowView | None:
    """Use only an exact durable transaction to cross the bare-shell gate."""
    if herdr_identity.decode_target(value=target).herdr is None:
        return None
    scratch = _herdr_replacement_store.scratch_path(track=track)
    try:
        transaction = _herdr_replacement_store.read_transaction(
            path=scratch / _herdr_replacement_store.RECORD_NAME
        )
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        return _row(
            track=track,
            status="replacement-failed",
            note=f"malformed durable Herdr replacement: {exc}",
        )
    if transaction is None:
        return None
    if transaction.get("target") != target:
        return _row(
            track=track,
            status="replacement-failed",
            note="durable Herdr replacement does not match the live backend generation and pane",
        )
    return _reconcile_transaction(
        sup=sup,
        track=track,
        target=target,
        transaction=transaction,
        act=act,
    )
