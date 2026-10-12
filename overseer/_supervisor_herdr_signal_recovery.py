"""Recover the durable boundary after a Herdr termination signal."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import herdr_replacement_process
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["recover_signal_attempt", "signal_attempt_refusal"]


def signal_attempt_refusal(
    *,
    transaction: Mapping[str, object],
    snapshot: _herdr_replacement_process.ReplacementSnapshot | None = None,
) -> str | None:
    """Refuse unless the recorded predecessor generation is proven absent."""
    predecessor = cast(dict[str, object], transaction["predecessor"])
    refusal = herdr_replacement_process.predecessor_exit_refusal(
        pid=cast(int, predecessor["pid"]),
        starttime=cast(str, predecessor["starttime"]),
    )
    if refusal is not None:
        return refusal[0]
    if snapshot is not None and _herdr_replacement_process.predecessor_still_live(
        transaction=transaction,
        snapshot=snapshot,
    ):
        return "predecessor survived the one termination attempt"
    return None


def recover_signal_attempt(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> tuple[dict[str, object] | None, str | None]:
    """Fence transition from one signal attempt to the never-attempted launch."""
    scratch = _herdr_replacement_store.scratch_path(track=track)
    try:
        with _herdr_replacement_store.transaction_lock(
            path=scratch / _herdr_replacement_store.LOCK_NAME
        ):
            current = _herdr_replacement_store.read_transaction(
                path=scratch / _herdr_replacement_store.RECORD_NAME
            )
            if (
                current is None
                or current != transaction
                or current.get("phase") != "signal-attempted"
            ):
                return None, "durable replacement changed while proving predecessor exit"
            pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
            snapshot = pane.herdr_replacement_snapshot(session=target)
            reason = signal_attempt_refusal(transaction=current, snapshot=snapshot)
            if reason is not None:
                return None, reason
            current["phase"] = "stopped-awaiting-shell"
            _herdr_replacement_store.durable_write(
                path=scratch / _herdr_replacement_store.RECORD_NAME,
                value=current,
            )
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        return None, str(exc)
    return current, None
