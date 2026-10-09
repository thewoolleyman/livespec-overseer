"""Fresh daemon-process evidence below one tmux pane's retained shell."""

from __future__ import annotations

import claude_sessions
import daemon_liveness
from _seams import PidToIntList, PidToOptionalBytes

__all__: list[str] = ["MAX_DESCENDANT_PROCESSES", "daemon_descendant_command"]

# A real daemon is one direct child today.  The wider bound permits ordinary
# launcher wrappers without letting corrupt or cyclic process evidence hold the
# public bootstrap indefinitely.
MAX_DESCENDANT_PROCESSES = 64


def daemon_descendant_command(
    *,
    root_pid: int,
    children_of: PidToIntList = claude_sessions.proc_children,
    cmdline_of: PidToOptionalBytes = claude_sessions.proc_cmdline,
    max_processes: int = MAX_DESCENDANT_PROCESSES,
) -> str | None:
    """Return a fresh daemon command below ``root_pid``, or ``None`` fail-closed.

    The root is deliberately excluded.  A tmux pane shell is commonly started
    with ``bash -c '<overseerd command>'``, so its own command line can mention
    ``overseerd`` even after the child has died.  Only a live descendant's
    ``/proc`` command line establishes daemon liveness.
    """
    pending = list(children_of(pid=root_pid))
    seen = {root_pid}
    while pending and len(seen) < max_processes:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        raw = cmdline_of(pid=pid)
        if raw is not None:
            command = raw.replace(b"\0", b" ").decode(errors="replace").strip()
            if daemon_liveness.is_daemon_command(text=command):
                return command
        pending.extend(children_of(pid=pid))
    return None
