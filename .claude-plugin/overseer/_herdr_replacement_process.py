"""Process-shaped Herdr observations and replacement safety predicates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

__all__: list[str] = [
    "ProcessObservation",
    "ReplacementPane",
    "ReplacementResult",
    "ReplacementSnapshot",
    "predecessor",
    "predecessor_still_live",
    "process_record",
    "proven_successor",
    "replacement_still_owned",
    "retained_shell_is_idle",
]


class ProcessObservation(Protocol):
    pid: int
    starttime: str
    executable: str
    argv: Sequence[str]
    process_group: int
    session_id: int


class ReplacementSnapshot(Protocol):
    shell: ProcessObservation
    foreground_group: int
    processes: Sequence[ProcessObservation]


class ReplacementResult(Protocol):
    ok: bool
    error: str


class ReplacementPane(Protocol):
    def herdr_replacement_snapshot(self, *, session: str) -> ReplacementSnapshot: ...

    def herdr_terminate(self, *, session: str, process_group: int) -> ReplacementResult: ...

    def herdr_launch(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: Mapping[str, str | None],
    ) -> ReplacementResult: ...


def predecessor(*, snapshot: ReplacementSnapshot, identity: str) -> ProcessObservation | None:
    _, pid_text, starttime, _ = identity.split(":", 3)
    pid = int(pid_text)
    for process in snapshot.processes:
        if process.pid == pid and process.starttime == starttime:
            return process
    return None


def process_record(*, process: ProcessObservation) -> dict[str, object]:
    return {
        "pid": process.pid,
        "starttime": process.starttime,
        "executable": process.executable,
        "argv": list(process.argv),
        "process_group": process.process_group,
        "session_id": process.session_id,
    }


def predecessor_still_live(
    *, transaction: Mapping[str, object], snapshot: ReplacementSnapshot
) -> bool:
    recorded = cast(dict[str, object], transaction["predecessor"])
    return any(
        process.pid == recorded["pid"] and process.starttime == recorded["starttime"]
        for process in snapshot.processes
    )


def replacement_still_owned(
    *, transaction: Mapping[str, object], snapshot: ReplacementSnapshot
) -> bool:
    """Reverify the exact predecessor, shell, and signal group together."""
    predecessor_record = cast(dict[str, object], transaction["predecessor"])
    shell_record = cast(dict[str, object], transaction["shell"])
    server_record = cast(dict[str, object], transaction["server"])
    process_group = cast(int, predecessor_record["process_group"])
    return all(
        (
            predecessor_still_live(transaction=transaction, snapshot=snapshot),
            process_record(process=snapshot.shell) == shell_record,
            snapshot.foreground_group == process_group,
            process_group != shell_record["pid"],
            process_group != server_record["pid"],
        )
    )


def retained_shell_is_idle(
    *, transaction: Mapping[str, object], snapshot: ReplacementSnapshot
) -> bool:
    shell = cast(dict[str, object], transaction["shell"])
    return (
        snapshot.shell.pid == shell["pid"]
        and snapshot.shell.starttime == shell["starttime"]
        and snapshot.shell.executable == shell["executable"]
        and snapshot.foreground_group == snapshot.shell.process_group
    )


def proven_successor(
    *,
    transaction: Mapping[str, object],
    snapshot: ReplacementSnapshot,
    identity: str,
) -> ProcessObservation | None:
    """Return the distinct runtime generation proven inside the retained pane.

    A runtime PID need not lead its foreground process group: both Claude and Codex
    can run below a launcher.  The group must nevertheless have a live leader in the
    original shell session, and neither that group nor the runtime may reuse the
    predecessor identity.
    """
    predecessor_record = cast(dict[str, object], transaction["predecessor"])
    shell_record = cast(dict[str, object], transaction["shell"])
    server_record = cast(dict[str, object], transaction["server"])
    try:
        successor = predecessor(snapshot=snapshot, identity=identity)
    except (TypeError, ValueError):
        successor = None
    group = snapshot.foreground_group
    leader = next((process for process in snapshot.processes if process.pid == group), None)
    valid = successor is not None and all(
        (
            not predecessor_still_live(transaction=transaction, snapshot=snapshot),
            successor.pid != predecessor_record["pid"],
            process_record(process=snapshot.shell) == shell_record,
            group not in {shell_record["pid"], server_record["pid"]},
            successor.process_group == group,
            successor.session_id == snapshot.shell.session_id,
            leader is not None,
            False if leader is None else leader.session_id == snapshot.shell.session_id,
        )
    )
    return successor if valid else None
