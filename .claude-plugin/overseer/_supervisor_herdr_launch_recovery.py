"""Launch a durable Herdr successor only from its original idle shell."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import herdr_replacement_process
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["launch_recorded_successor"]


def launch_recorded_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> str | None:
    """Fence launch intent, then submit the frozen profile exactly once."""
    pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
    scratch = _herdr_replacement_store.scratch_path(track=track)
    with _herdr_replacement_store.transaction_lock(
        path=scratch / _herdr_replacement_store.LOCK_NAME
    ):
        current = _herdr_replacement_store.read_transaction(
            path=scratch / _herdr_replacement_store.RECORD_NAME
        )
        if (
            current is None
            or current != transaction
            or current.get("phase") != "stopped-awaiting-shell"
        ):
            return "durable replacement changed before successor launch"
        snapshot = pane.herdr_replacement_snapshot(session=target)
        if not _herdr_replacement_process.retained_shell_is_idle(
            transaction=current,
            snapshot=snapshot,
        ):
            return "original retained shell is absent or no longer idle"
        predecessor = cast(dict[str, object], current["predecessor"])
        predecessor_pid = cast(int, predecessor["pid"])
        try:
            observed_starttime = herdr_replacement_process.proc_starttime(pid=predecessor_pid)
        except OSError as exc:
            return f"recorded predecessor generation is unreadable: {exc}"
        if observed_starttime is not None:
            return "recorded predecessor PID is still occupied by a process generation"
        current["phase"] = "launch-attempted"
        _herdr_replacement_store.durable_write(
            path=scratch / _herdr_replacement_store.RECORD_NAME,
            value=current,
        )
        launch = cast(dict[str, object], current["launch"])
        _ = pane.herdr_launch(
            session=target,
            cwd=cast(str, launch["cwd"]),
            command=cast(str, launch["command"]),
            env=cast(dict[str, str | None], launch["env"]),
        )
    return None
