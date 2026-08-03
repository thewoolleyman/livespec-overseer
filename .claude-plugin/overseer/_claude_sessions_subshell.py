"""Runtime-agnostic descendant shell activity detection."""

from __future__ import annotations

from _claude_sessions_proc import proc_children, proc_cmdline, proc_comm, proc_starttime
from _seams import PidToIntList, PidToOptionalBytes, PidToOptionalStr

__all__: list[str] = [
    "has_active_subshell",
]

# Shell process names. Most are task shells, but some agent runtimes also create
# short startup wrapper shells before launching long-lived MCP helpers; start-time
# evidence below separates those startup shells from later background work.
_SHELL_COMMS = frozenset({"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"})

# Startup wrapper shells must be close to the runtime process that spawned them;
# anything later than this deterministic raw-tick margin is task work or
# ambiguous enough to keep the session busy.
STARTUP_SHELL_MARGIN_TICKS = 1000


def _starttime_ticks(*, value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _runtime_starttime_ticks(
    *,
    direct_children: list[int],
    comm_of: PidToOptionalStr,
    starttime_of: PidToOptionalStr,
) -> int | None:
    """Earliest direct non-shell child starttime, or None when ambiguous."""
    starts: list[int] = []
    for pid in direct_children:
        comm = comm_of(pid=pid)
        if comm is None:
            return None
        if comm.lower() in _SHELL_COMMS:
            continue
        ticks = _starttime_ticks(value=starttime_of(pid=pid))
        if ticks is None:
            return None
        starts.append(ticks)
    return min(starts) if starts else None


def _descendant_shell_pids(
    *,
    root_pid: int,
    direct_children: list[int],
    children_of: PidToIntList,
    comm_of: PidToOptionalStr,
    max_nodes: int,
) -> list[int]:
    seen: set[int] = set()
    shell_pids: list[int] = []
    stack = list(direct_children)
    while stack and len(seen) < max_nodes:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if pid == root_pid:
            stack.extend(children_of(pid=pid))
            continue
        comm = comm_of(pid=pid)
        if comm is not None and comm.lower() in _SHELL_COMMS:
            shell_pids.append(pid)
        stack.extend(children_of(pid=pid))
    return shell_pids


def _shell_argvs_by_starttime(
    *,
    shell_pids: list[int],
    baseline: int,
    starttime_of: PidToOptionalStr,
    cmdline_of: PidToOptionalBytes,
) -> tuple[set[bytes], list[int]] | None:
    startup_shell_argvs: set[bytes] = set()
    late_shell_pids: list[int] = []
    for pid in shell_pids:
        shell_start = _starttime_ticks(value=starttime_of(pid=pid))
        if shell_start is None or shell_start < baseline:
            return None
        if shell_start - baseline > STARTUP_SHELL_MARGIN_TICKS:
            late_shell_pids.append(pid)
            continue
        shell_argv = cmdline_of(pid=pid)
        if shell_argv is not None:
            startup_shell_argvs.add(shell_argv)
    return startup_shell_argvs, late_shell_pids


def _late_shell_has_startup_twin(
    *,
    pid: int,
    startup_shell_argvs: set[bytes],
    cmdline_of: PidToOptionalBytes,
) -> bool:
    shell_argv = cmdline_of(pid=pid)
    return shell_argv is not None and shell_argv in startup_shell_argvs


def has_active_subshell(
    *,
    root_pid: int,
    children_of: PidToIntList = proc_children,
    comm_of: PidToOptionalStr = proc_comm,
    starttime_of: PidToOptionalStr = proc_starttime,
    cmdline_of: PidToOptionalBytes = proc_cmdline,
    max_nodes: int = 512,
) -> bool:
    """True if a DESCENDANT shell is later task work, not runtime startup plumbing.

    ``root_pid`` is the tmux pane's process (the login shell); its descendants are
    the session runtime (claude/codex/node/bun) and that runtime's own children. A
    later Claude/Codex background command runs as a shell subprocess of the runtime,
    so a descendant shell born after ``STARTUP_SHELL_MARGIN_TICKS`` means the session
    has ACTIVE BACKGROUND WORK and is not idle — even when the pane shows an empty
    prompt. A shell born within that raw ``/proc`` starttime-tick margin from the
    runtime baseline is startup infrastructure and is ignored. Missing, unreadable,
    inconsistent or otherwise ambiguous start-time evidence fails busy. ``root_pid``
    ITSELF (the login shell) is excluded — only its descendants count. Runtime-agnostic.
    The walk is bounded (``max_nodes``) with a visited-set, so a cycle or a huge tree
    still terminates. The ``/proc`` readers are injected so the beside-tests drive it
    with fakes and never touch real ``/proc``.
    """
    direct_children = list(children_of(pid=root_pid))
    shell_pids = _descendant_shell_pids(
        root_pid=root_pid,
        direct_children=direct_children,
        children_of=children_of,
        comm_of=comm_of,
        max_nodes=max_nodes,
    )
    if not shell_pids:
        return False
    baseline = _runtime_starttime_ticks(
        direct_children=direct_children, comm_of=comm_of, starttime_of=starttime_of
    )
    if baseline is None:
        return True
    classified = _shell_argvs_by_starttime(
        shell_pids=shell_pids,
        baseline=baseline,
        starttime_of=starttime_of,
        cmdline_of=cmdline_of,
    )
    if classified is None:
        return True
    startup_shell_argvs, late_shell_pids = classified
    for pid in late_shell_pids:
        if not _late_shell_has_startup_twin(
            pid=pid,
            startup_shell_argvs=startup_shell_argvs,
            cmdline_of=cmdline_of,
        ):
            return True
    return False
