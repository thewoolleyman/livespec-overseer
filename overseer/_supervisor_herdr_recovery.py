"""Reconcile a durable Herdr replacement before ordinary runtime recognition."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import herdr_identity
import registry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["reconcile_bare_shell"]


def _row(*, track: registry.Track, note: str) -> RowView:
    return RowView(
        topic=track.topic,
        repo=track.repo,
        tmux=track.tmux,
        ctx=None,
        status="replacement-pending",
        note=note,
    )


def _launch_recorded_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> None:
    pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
    scratch = _herdr_replacement_store.scratch_path(track=track)
    with _herdr_replacement_store.transaction_lock(
        path=scratch / _herdr_replacement_store.LOCK_NAME
    ):
        current_record = dict(transaction)
        current_record["phase"] = "launch-attempted"
        _herdr_replacement_store.durable_write(
            path=scratch / _herdr_replacement_store.RECORD_NAME,
            value=current_record,
        )
        launch = cast(dict[str, object], current_record["launch"])
        _ = pane.herdr_launch(
            session=target,
            cwd=cast(str, launch["cwd"]),
            command=cast(str, launch["command"]),
            env=cast(dict[str, str | None], launch["env"]),
        )


def reconcile_bare_shell(
    *, sup: Supervisor, track: registry.Track, target: str, act: bool
) -> RowView | None:
    """Use only an exact durable transaction to cross the bare-shell gate."""
    if herdr_identity.decode_target(value=target).herdr is None:
        return None
    scratch = _herdr_replacement_store.scratch_path(track=track)
    transaction = _herdr_replacement_store.read_transaction(
        path=scratch / _herdr_replacement_store.RECORD_NAME
    )
    if transaction is None or transaction.get("target") != target:
        return None
    phase = transaction.get("phase")
    if phase == "stopped-awaiting-shell" and act:
        _launch_recorded_successor(
            sup=sup,
            track=track,
            target=target,
            transaction=transaction,
        )
    return _row(track=track, note=f"durable Herdr replacement phase: {phase}")
