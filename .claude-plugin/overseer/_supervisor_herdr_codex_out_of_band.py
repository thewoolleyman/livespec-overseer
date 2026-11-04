"""Name a live Codex process in a replacement's pane that the replacement does not own."""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, cast

import _herdr_replacement_process

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["third_generation_identity"]


def _is_codex(*, process: _herdr_replacement_process.ProcessObservation) -> bool:
    """Whether the process is the Codex binary itself, not a launcher that execs it."""
    names = {PurePath(process.executable).name}
    names.update(PurePath(argument).name for argument in process.argv[:1])
    return "codex" in names


def _is_recorded(
    *, process: _herdr_replacement_process.ProcessObservation, record: dict[str, object]
) -> bool:
    return process.pid == record.get("pid") and process.starttime == record.get("starttime")


def third_generation_identity(
    *, sup: Supervisor, topic: str, target: str, transaction: dict[str, object]
) -> str | None:
    """The identity of a live foreground Codex that is neither recorded generation.

    A managed Codex carrier holds no rollout file open, so a hand-restarted successor
    cannot be told apart by rollout.  The evidence is the pane's own foreground process:
    its pid and /proc start time, inside the retained shell the replacement recorded.
    Nothing here reads a rollout body or compares rollout recency, and nothing signals,
    launches or pastes into the pane.  A recorded generation anywhere in the foreground
    means the replacement still owns it, so no identity is returned.
    """
    records = [transaction.get(key) for key in ("predecessor", "successor", "shell", "server")]
    if not all(isinstance(record, dict) for record in records):
        return None
    predecessor, successor, shell, server = (
        cast("dict[str, object]", record) for record in records
    )
    pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
    snapshot = pane.herdr_replacement_snapshot(session=target)
    group = snapshot.foreground_group
    if _herdr_replacement_process.process_record(process=snapshot.shell) != shell or group in {
        snapshot.shell.process_group,
        shell.get("pid"),
        server.get("pid"),
    }:
        return None
    live = sorted(
        (
            process
            for process in snapshot.processes
            if process.process_group == group
            and process.session_id == snapshot.shell.session_id
            and _is_codex(process=process)
        ),
        key=lambda process: process.pid,
    )
    if not live or any(
        _is_recorded(process=process, record=record)
        for process in live
        for record in (predecessor, successor)
    ):
        return None
    return f"codex:{live[0].pid}:{live[0].starttime}:{topic}"
