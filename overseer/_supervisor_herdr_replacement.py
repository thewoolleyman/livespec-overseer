"""Durable authorization boundary for a ready-declared Herdr replacement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import _herdr_replacement_authorization
import _herdr_replacement_process
import _herdr_replacement_store
import registry
from _supervisor_launch_profile import ClaudeLaunchPlan, CodexLaunchPlan

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["ReplacementFailure", "begin_herdr_replacement"]

# Kept as the module-local persistence seam used by deterministic failure tests.
_durable_write = _herdr_replacement_store.durable_write


@dataclass(frozen=True, kw_only=True)
class ReplacementFailure:
    reason: str
    condition: str


def _refuse(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    reason: str,
    condition: str = "herdr-replacement-refused",
) -> ReplacementFailure:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=target,
        pane=target,
        message=f"Herdr replacement refused: {reason}",
        condition=condition,
    )
    return ReplacementFailure(reason=reason, condition=condition)


def _stop_predecessor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
    pane: _herdr_replacement_process.ReplacementPane,
    record_path: Path,
) -> tuple[_herdr_replacement_process.ReplacementSnapshot | None, ReplacementFailure | None]:
    verified = pane.herdr_replacement_snapshot(session=target)
    if not _herdr_replacement_process.replacement_still_owned(
        transaction=transaction, snapshot=verified
    ) or not _herdr_replacement_authorization.round_still_authorizes(
        sup=sup, track=track, transaction=transaction
    ):
        failure = _refuse(
            sup=sup,
            track=track,
            target=target,
            reason="process ownership or restart authorization changed before signal",
        )
        return None, failure
    transaction["phase"] = "signal-attempted"
    _durable_write(path=record_path, value=transaction)
    predecessor = cast(dict[str, object], transaction["predecessor"])
    terminated = pane.herdr_terminate(
        session=target,
        process_group=cast(int, predecessor["process_group"]),
    )
    if not terminated.ok:
        failure = _refuse(
            sup=sup,
            track=track,
            target=target,
            reason=terminated.error,
            condition="herdr-signal-failed",
        )
        return None, failure
    stopped = pane.herdr_replacement_snapshot(session=target)
    if _herdr_replacement_process.predecessor_still_live(transaction=transaction, snapshot=stopped):
        failure = _refuse(
            sup=sup,
            track=track,
            target=target,
            reason="predecessor survived the one termination attempt",
            condition="herdr-predecessor-survived",
        )
        return None, failure
    return stopped, None


def begin_herdr_replacement(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    launch: ClaudeLaunchPlan | CodexLaunchPlan,
    binding: _herdr_replacement_authorization.ReplacementBinding = (
        _herdr_replacement_authorization.DEFAULT_BINDING
    ),
) -> ReplacementFailure | None:
    """Fence the ready authorization durably, then make its one stop attempt."""
    pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
    scratch = _herdr_replacement_store.scratch_path(track=track)
    try:
        with _herdr_replacement_store.transaction_lock(
            path=scratch / _herdr_replacement_store.LOCK_NAME
        ):
            existing = _herdr_replacement_store.read_transaction(
                path=scratch / _herdr_replacement_store.RECORD_NAME
            )
            snapshot = pane.herdr_replacement_snapshot(session=target)
            if (
                existing is not None
                and existing.get("phase") == "signal-attempted"
                and _herdr_replacement_process.predecessor_still_live(
                    transaction=existing, snapshot=snapshot
                )
            ):
                return _refuse(
                    sup=sup,
                    track=track,
                    target=target,
                    reason="predecessor survived the one termination attempt",
                    condition="herdr-predecessor-survived",
                )
            transaction, reason = _herdr_replacement_authorization.bind_authorization(
                sup=sup,
                track=track,
                target=target,
                launch=launch,
                snapshot=snapshot,
                binding=binding,
            )
            if transaction is None:
                return _refuse(sup=sup, track=track, target=target, reason=reason)
            _durable_write(
                path=scratch / _herdr_replacement_store.RECORD_NAME,
                value=transaction,
            )
            stopped, failure = _stop_predecessor(
                sup=sup,
                track=track,
                target=target,
                transaction=transaction,
                pane=pane,
                record_path=scratch / _herdr_replacement_store.RECORD_NAME,
            )
            if failure is not None:
                return failure
            stopped = cast(_herdr_replacement_process.ReplacementSnapshot, stopped)
            transaction["phase"] = "stopped-awaiting-shell"
            _durable_write(
                path=scratch / _herdr_replacement_store.RECORD_NAME,
                value=transaction,
            )
            if not _herdr_replacement_process.retained_shell_is_idle(
                transaction=transaction, snapshot=stopped
            ):
                return _refuse(
                    sup=sup,
                    track=track,
                    target=target,
                    reason="retained shell is absent or has a foreign foreground process",
                    condition="herdr-shell-not-idle",
                )
            transaction["phase"] = "launch-attempted"
            _durable_write(
                path=scratch / _herdr_replacement_store.RECORD_NAME,
                value=transaction,
            )
            launch_record = cast(dict[str, object], transaction["launch"])
            _ = pane.herdr_launch(
                session=target,
                cwd=cast(str, launch_record["cwd"]),
                command=cast(str, launch_record["command"]),
                env=cast(dict[str, str | None], launch_record["env"]),
            )
    except OSError as exc:
        reason = str(exc)
        return _refuse(sup=sup, track=track, target=target, reason=reason)
    return None
