"""Daemon self re-exec policy at tick boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from _supervisor_view import RESUME_PENDING_NOTE, RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["maybe_reexec"]


def maybe_reexec(*, sup: Supervisor, rows: list[RowView]) -> None:
    """Replace the daemon process image only at a clean acting tick boundary.

    The target resolver owns release/currency/install decisions and returns the
    executable that should replace this process. This layer owns only the daemon
    safety point: do not exec while any session restart interlock is represented
    in the just-rendered tick, and do not repeatedly try the same operation in a
    tight loop if the target keeps being offered.
    """
    target = sup.reexec_target()
    if target is None:
        return
    if _restart_interlock_pending(rows=rows):
        return
    now = sup.now()
    if now - sup.last_reexec_attempt_at < sup.reexec_min_interval_seconds:
        return
    sup.last_reexec_attempt_at = now
    argv = _exec_argv(target=target, current_argv=sup.argv())
    sup.execv(path=str(target), argv=argv)


def _restart_interlock_pending(*, rows: list[RowView]) -> bool:
    return any(_row_restart_pending(row=row) for row in rows)


def _row_restart_pending(*, row: RowView) -> bool:
    if row.status == "restarting":
        return True
    return bool(row.note and row.note.startswith(RESUME_PENDING_NOTE))


def _exec_argv(*, target: Path, current_argv: list[str]) -> list[str]:
    return [str(target), *current_argv[1:]]
