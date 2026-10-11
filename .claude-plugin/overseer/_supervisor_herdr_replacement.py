"""Durable authorization boundary for a ready-declared Herdr replacement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import herdr_identity
import registry
import signals
from _supervisor_launch_profile import ClaudeLaunchPlan

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["ReplacementFailure", "begin_herdr_replacement"]

# Kept as the module-local persistence seam used by deterministic failure tests.
_durable_write = _herdr_replacement_store.durable_write


@dataclass(frozen=True, kw_only=True)
class ReplacementFailure:
    reason: str
    condition: str


def _record(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    launch: ClaudeLaunchPlan,
    snapshot: _herdr_replacement_process.ReplacementSnapshot,
) -> tuple[dict[str, object] | None, str]:
    decoded = herdr_identity.decode_target(value=target)
    server = cast(herdr_identity.HerdrPaneTarget, decoded.herdr)
    round_record = registry.read_round_record(
        repo=track.repo,
        topic=track.topic,
        stamp_path=sup.stamp_path,
    )
    declared = signals.read_state(repo=track.repo, topic=track.topic)
    identity = cast(str, round_record.session_identity)
    predecessor = _herdr_replacement_process.predecessor(snapshot=snapshot, identity=identity)
    if declared is None:
        return None, "ready declaration changed before durable binding"
    if predecessor is None:
        return None, "predecessor process identity was reused or disappeared"
    if snapshot.shell.pid == predecessor.pid:
        return None, "root shell was exec-replaced by the predecessor"
    return {
        "version": 1,
        "phase": "before-stop",
        "target": target,
        "server": {
            "socket_path": server.socket_path,
            "pid": server.server_pid,
            "starttime": server.server_starttime,
            "pane_id": server.pane_id,
        },
        "runtime": "claude",
        "predecessor": {
            "pid": predecessor.pid,
            "starttime": predecessor.starttime,
            "process_group": snapshot.foreground_group,
        },
        "shell": _herdr_replacement_process.process_record(process=snapshot.shell),
        "round": {
            "ready_mtime": declared.mtime,
            "round_at": round_record.at,
            "session_identity": identity,
        },
        "launch": {
            "command": launch.command,
            "cwd": track.repo,
            "env": dict(launch.env),
        },
    }, ""


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
        message=f"Herdr replacement refused before signal: {reason}",
        condition=condition,
    )
    return ReplacementFailure(reason=reason, condition=condition)


def begin_herdr_replacement(
    *, sup: Supervisor, track: registry.Track, target: str, launch: ClaudeLaunchPlan
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
            transaction, reason = _record(
                sup=sup,
                track=track,
                target=target,
                launch=launch,
                snapshot=snapshot,
            )
            if transaction is None:
                return _refuse(sup=sup, track=track, target=target, reason=reason)
            _durable_write(
                path=scratch / _herdr_replacement_store.RECORD_NAME,
                value=transaction,
            )
            transaction["phase"] = "signal-attempted"
            _durable_write(
                path=scratch / _herdr_replacement_store.RECORD_NAME,
                value=transaction,
            )
            predecessor = cast(dict[str, object], transaction["predecessor"])
            _ = pane.herdr_terminate(
                session=target,
                process_group=cast(int, predecessor["process_group"]),
            )
            stopped = pane.herdr_replacement_snapshot(session=target)
            if _herdr_replacement_process.predecessor_still_live(
                transaction=transaction, snapshot=stopped
            ):
                return _refuse(
                    sup=sup,
                    track=track,
                    target=target,
                    reason="predecessor survived the one termination attempt",
                    condition="herdr-predecessor-survived",
                )
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
