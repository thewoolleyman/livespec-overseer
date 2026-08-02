"""claude_sessions.py — read Claude Code's session registry and map each live
NAMED session to the tmux session that holds it, by PID.

Stdlib-only, host-only (see ``registry.py`` header — this whole skill folder is
outside the livespec product gates).

Why this exists: ``adopt`` must learn each running worker's *topic* (its
``claude -n``/``/rename`` display name). That name is NOT in the process argv —
the maintainer's sessions run ``claude --dangerously-skip-permissions`` and are
renamed at runtime — and screen-scraping the input-box border fails whenever the
pane shows a prompt instead of the box (verified live 2026-07-13). But Claude Code
writes the name to a per-session file at ``~/.claude/sessions/<pid>.json``:

    {"pid":1067963,"cwd":"/data/projects/livespec","name":"driver-hook-body",
     "status":"idle","procStart":"34092476", ...}

So the robust, screen-independent source is that file, keyed by the claude PID.
This module reads those files, keeps only LIVE claude processes (the PID is alive
AND its ``/proc/<pid>/stat`` start-time equals the recorded ``procStart`` — an
exact match live 2026-07-13, defending against PID reuse), and joins each to the
tmux session whose pane process-tree contains that PID. The result is a
``(tmux_session, name, cwd)`` mapping that does not depend on anything rendered on
screen, so it works even while a session is waiting on a user prompt.

The ``/proc`` readers (``proc_ppid`` / ``proc_starttime``) are the ONLY host
coupling; they are injected into the pure join functions so the beside-tests drive
everything with fakes and never touch real ``/proc`` or ``~/.claude``.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from _seams import PidToIntList, PidToOptionalInt, PidToOptionalStr

__all__: list[str] = [
    "ClaudeSession",
    "default_sessions_dir",
    "has_active_subshell",
    "map_named_sessions",
    "names_by_tmux_session",
    "proc_children",
    "proc_comm",
    "proc_ppid",
    "proc_starttime",
    "read_live_sessions",
    "resolve_tmux_session",
    "status_by_tmux_session",
]

# A claude PID's parent chain is a handful deep (claude → shell → tmux pane);
# bound the walk so a cycle or a pathological tree can never spin.
_MAX_PARENT_WALK = 64

# /proc/<pid>/stat field 22 is the kernel start-time clock in ticks since boot.
# Startup wrapper shells must be close to the runtime process that spawned them;
# anything later than this deterministic raw-tick margin is task work or
# ambiguous enough to keep the session busy.
STARTUP_SHELL_MARGIN_TICKS = 1000


@dataclass(frozen=True, kw_only=True)
class ClaudeSession:
    """One live, named Claude Code session from the registry."""

    pid: int
    name: str
    cwd: str
    status: str  # Claude's own live self-report: "busy" / "idle" / "waiting" (or "" if absent)
    # How the display name was set. Claude writes "derived" when it AUTO-named the
    # session from the repo directory (`livespec-overseer-01`); a session launched
    # with an explicit `-n <topic>` carries no such marker. That distinction is the
    # only thing separating "this is our track, merely misnamed" (overseer-j1r) from
    # "this is a DIFFERENT topic's session in a reused window" (R2/SF5) — by name
    # alone the two are indistinguishable. Absent ⇒ "" (explicitly named).
    name_source: str = ""


def default_sessions_dir() -> Path:
    """``~/.claude/sessions`` — where Claude Code writes ``<pid>.json`` per session."""
    return Path.home() / ".claude" / "sessions"


# --------------------------------------------------------------------------- #
# The ONE host coupling: /proc readers. Injected into the pure join below.
# --------------------------------------------------------------------------- #


def _proc_stat_fields(*, pid: int) -> list[str] | None:
    """``/proc/<pid>/stat`` split AFTER the ``(comm)`` field, or None if unreadable.

    ``comm`` (field 2) can contain spaces and parentheses, so everything up to and
    including the LAST ``)`` is dropped; the returned list is field 3 onward, i.e.
    ``fields[i]`` is stat field ``i + 3`` (state=fields[0], ppid=fields[1],
    starttime=fields[19]).
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    cut = raw.rfind(")")
    if cut == -1:
        return None
    return raw[cut + 1 :].split()


# Indices into the post-``)`` remainder of ``/proc/<pid>/stat`` that
# :func:`_proc_stat_fields` returns. The kernel numbers stat's fields from 1 and
# that remainder begins at field 3, so the field numbered F sits at index F - 3.
_PPID_INDEX = 1  # stat field 4
_STARTTIME_INDEX = 19  # stat field 22


def proc_ppid(*, pid: int) -> int | None:
    """The parent PID of ``pid`` from ``/proc/<pid>/stat`` (field 4), or None."""
    fields = _proc_stat_fields(pid=pid)
    if fields is None or len(fields) <= _PPID_INDEX:
        return None
    try:
        return int(fields[_PPID_INDEX])
    except ValueError:
        return None


def proc_starttime(*, pid: int) -> str | None:
    """The process start-time of ``pid`` from ``/proc/<pid>/stat`` (field 22), or None.

    Returned as a string to compare byte-for-byte against the registry's
    ``procStart`` (also a string). None if the process is gone / unreadable — which
    the caller treats as "not live".
    """
    fields = _proc_stat_fields(pid=pid)
    if fields is None or len(fields) <= _STARTTIME_INDEX:
        return None
    return fields[_STARTTIME_INDEX]


# Shell process names. Most are task shells, but some agent runtimes also create
# short startup wrapper shells before launching long-lived MCP helpers; start-time
# evidence below separates those startup shells from later background work.
_SHELL_COMMS = frozenset({"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"})


def proc_comm(*, pid: int) -> str | None:
    """``/proc/<pid>/comm`` (the process's command name), or None if unreadable."""
    try:
        return (
            Path(f"/proc/{pid}/comm").read_text(encoding="utf-8", errors="replace").strip() or None
        )
    except OSError:
        return None


def proc_children(*, pid: int) -> list[int]:
    """Direct child PIDs of ``pid`` via ``/proc/<pid>/task/<pid>/children`` ([] on error)."""
    try:
        data = Path(f"/proc/{pid}/task/{pid}/children").read_text(encoding="utf-8")
    # ValueError is defence-in-depth here, not a live hazard: the kernel writes this
    # file as ASCII pids and spaces, so it cannot fail to decode. Widened anyway so
    # every read boundary in the package carries ONE rule rather than two.
    except (OSError, ValueError):
        return []
    out: list[int] = []
    for token in data.split():
        with contextlib.suppress(ValueError):
            out.append(int(token))
    return out


# --------------------------------------------------------------------------- #
# Pure functions over injected data (fully testable with fakes).
# --------------------------------------------------------------------------- #


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


def has_active_subshell(
    *,
    root_pid: int,
    children_of: PidToIntList = proc_children,
    comm_of: PidToOptionalStr = proc_comm,
    starttime_of: PidToOptionalStr = proc_starttime,
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
    if not shell_pids:
        return False
    baseline = _runtime_starttime_ticks(
        direct_children=direct_children, comm_of=comm_of, starttime_of=starttime_of
    )
    if baseline is None:
        return True
    for pid in shell_pids:
        shell_start = _starttime_ticks(value=starttime_of(pid=pid))
        if shell_start is None or shell_start < baseline:
            return True
        if shell_start - baseline > STARTUP_SHELL_MARGIN_TICKS:
            return True
    return False


def read_live_sessions(
    *,
    sessions_dir: str | os.PathLike[str],
    starttime_of: PidToOptionalStr = proc_starttime,
) -> list[ClaudeSession]:
    """Every LIVE, named session in the registry dir.

    A file qualifies only when it parses, carries a non-empty ``name`` + ``cwd`` +
    integer ``pid``, and its ``procStart`` equals the process's current
    ``/proc`` start-time (``starttime_of(pid)``) — so a stale file for a dead PID,
    or one whose PID has been reused by an unrelated process, is dropped
    (fail-soft: any bad/unreadable file is skipped, never raised).
    """
    directory = Path(sessions_dir)
    out: list[ClaudeSession] = []
    try:
        files = sorted(directory.glob("*.json"))
    except OSError:
        return out
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = data.get("pid")
        name = data.get("name")
        name_source = data.get("nameSource")
        cwd = data.get("cwd")
        proc_start = data.get("procStart")
        status = data.get("status")
        if not isinstance(pid, int) or not isinstance(name, str) or not isinstance(cwd, str):
            continue
        if not name or not cwd or proc_start is None:
            continue
        if starttime_of(pid=pid) != str(proc_start):
            continue  # dead PID, or reused by an unrelated process
        out.append(
            ClaudeSession(
                pid=pid,
                name=name,
                cwd=cwd,
                status=status if isinstance(status, str) else "",
                name_source=name_source if isinstance(name_source, str) else "",
            )
        )
    return out


def resolve_tmux_session(
    *,
    pid: int,
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
) -> str | None:
    """The tmux session whose pane process-tree contains ``pid``, or None.

    Walks ``pid`` UP its parent chain; the first ancestor (or ``pid`` itself) that
    is a tmux pane PID gives the owning session. A claude PID's parent is its
    pane's shell (a pane PID), so this resolves in one or two hops; the bounded
    walk plus a visited-set make a cycle or a very deep tree fail-soft to None.
    """
    current = pid
    seen: set[int] = set()
    for _ in range(_MAX_PARENT_WALK):
        session = pane_pid_to_session.get(current)
        if session is not None:
            return session
        if current in seen:
            return None
        seen.add(current)
        parent = ppid_of(pid=current)
        if parent is None or parent <= 0 or parent == current:
            return None
        current = parent
    return None


def map_named_sessions(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    starttime_of: PidToOptionalStr = proc_starttime,
) -> list[tuple[str, str, str]]:
    """``[(tmux_session, name, cwd)]`` for every live named session held in tmux.

    Composes :func:`read_live_sessions` with :func:`resolve_tmux_session`. A live
    session that is not inside any tmux pane (run outside tmux) is omitted. Order
    follows the sorted registry files, so the mapping is deterministic.
    """
    mapped: list[tuple[str, str, str]] = []
    for session in read_live_sessions(sessions_dir=sessions_dir, starttime_of=starttime_of):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is None:
            continue
        mapped.append((tmux_session, session.name, session.cwd))
    return mapped


def status_by_tmux_session(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    starttime_of: PidToOptionalStr = proc_starttime,
) -> dict[str, str]:
    """``{tmux_session: status}`` for every live named Claude session held in tmux.

    Claude Code writes a live ``status`` (``busy`` / ``idle`` / ``waiting``) into each
    session's registry file. This is an AUTHORITATIVE busy signal for an adopted Claude
    session — it is TRUE while the session runs an in-process sub-agent (Task tool), which
    :func:`has_active_subshell` cannot see (a sub-agent spawns no descendant shell) and a
    single pane capture can miss. The daemon folds ``status == "busy"`` into its busy
    check so a sub-agent-running session is never mis-read as idle.

    Same join as :func:`map_named_sessions` (registry ⋈ tmux by PID walk); keyed by the
    tmux session so the daemon can look up a track's session in O(1). When two live
    sessions resolve to the same tmux session (should not happen in practice) the last
    wins, matching the sorted-file iteration order.
    """
    out: dict[str, str] = {}
    for session in read_live_sessions(sessions_dir=sessions_dir, starttime_of=starttime_of):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is not None:
            out[tmux_session] = session.status
    return out


def names_by_tmux_session(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    starttime_of: PidToOptionalStr = proc_starttime,
) -> dict[str, set[str]]:
    """``{tmux_session: {name, ...}}`` — the set of ALL live named Claude session names in
    each tmux session.

    Unlike :func:`status_by_tmux_session` (last-wins, one value per tmux session), this keeps
    EVERY name, so the daemon's identity gate can ask "is a live Claude named ``<topic>`` in
    this tmux session?" even when a HELPER Claude shares the tmux session (a second window/
    split). A last-wins single name would let that helper's name shadow the track's own and
    flap a healthy track to ``session-gone`` (R2 review SF5, 2026-07-18). Same registry ⋈
    tmux PID-walk join as :func:`status_by_tmux_session`.
    """
    out: dict[str, set[str]] = {}
    for session in read_live_sessions(sessions_dir=sessions_dir, starttime_of=starttime_of):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is not None:
            out.setdefault(tmux_session, set()).add(session.name)
    return out
