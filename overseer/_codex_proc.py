"""Host ``/proc`` evidence for Codex rollout ownership.

The process-table half of :mod:`codex_sessions`, which re-exports every name here and
remains the whole consumer surface. This module answers one question — WHICH live
process holds WHICH Codex rollout open — and nothing about what that rollout means; the
index lookup that turns a session id into a plan topic, the cwd that names the
repository, and the tmux join all stay with the join in the façade.

The split is the seam the façade already had between its "host couplings" and "the
join" sections, and it fell here because the Codex 0.150 helper walk
(:func:`carrier_rollout_ids`) belongs entirely to this side: it is fd tables and process
parentage, built on the same injected readers, and it consults nothing else.

**Secrets caution — nothing here reads a rollout's contents.** Rollout ``.jsonl`` files
are full session transcripts. The ownership question is answered from the FILENAME (for
the id) and ``/proc`` alone, so no rollout is opened. Keep it that way.

Stdlib-only. Every host coupling is injected at the call boundary, so the beside-tests
drive fd tables and process trees with fakes and never touch the real ``/proc``.
"""

from __future__ import annotations

import os
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from _seams import CommToPidList, PidToIntList, PidToOptionalStr, PidToStrList

# `proc_comm` / `proc_children` are GENERIC /proc readers that happen to live in
# `claude_sessions`, which already hosts the runtime-agnostic readers used for Codex
# (`has_active_subshell` — the Codex busy fallback — is built on them). Reusing them
# beats duplicating a reader into a sibling module.
from claude_sessions import proc_children, proc_comm

__all__: list[str] = [
    "MAX_HELPER_PROCESSES",
    "CodexHostReaders",
    "carrier_rollout_ids",
    "open_rollout_id",
    "open_rollout_ids",
    "proc_cwd",
    "proc_fd_targets",
    "proc_pids_of_comm",
    "rollout_id",
]

# `rollout-<iso-ts>-<uuid>.jsonl`. Anchored on the trailing uuid + extension so a
# rollout is never confused with a sibling file in the same tree.
_ROLLOUT_RE = re.compile(
    r"rollout-.*-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$"
)

# How many helper processes below one identity carrier the rollout walk will visit. A
# Codex session's helper sits one level down and brings a handful of processes with it;
# the bound is what keeps a pathological (or cyclic) process tree from stalling a tick.
MAX_HELPER_PROCESSES = 64


# --------------------------------------------------------------------------- #
# Host couplings: /proc readers. Injected into the pure readers below.
# --------------------------------------------------------------------------- #


def proc_fd_targets(*, pid: int) -> list[str]:
    """Every open fd's target path for ``pid`` — fail-soft to [] (dead pid / EPERM)."""
    out: list[str] = []
    try:
        entries = list(Path(f"/proc/{pid}/fd").iterdir())
    except OSError:
        return out
    for entry in entries:
        try:
            out.append(str(entry.readlink()))
        except OSError:
            continue  # the fd closed underneath us; skip it
    return out


def proc_cwd(*, pid: int) -> str | None:
    """``/proc/<pid>/cwd`` resolved, or None if unreadable."""
    try:
        return str(Path(f"/proc/{pid}/cwd").readlink())
    except OSError:
        return None


def proc_pids_of_comm(*, comm: str) -> list[int]:
    """Every live pid whose ``/proc/<pid>/comm`` equals ``comm`` — fail-soft to []."""
    out: list[int] = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return out
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if proc_comm(pid=pid) == comm:
            out.append(pid)
    return sorted(out)


@dataclass(frozen=True, kw_only=True)
class CodexHostReaders:
    """Everything needed to read live Codex sessions off ONE host, as one value.

    These five travel together — every consumer that wants live Codex sessions wants
    all of them — and the tmux-joining wrappers in :mod:`codex_sessions` carry the join
    seams on top, which is more parameters than a signature can state readably. Bundling
    the host side keeps those wrappers legible and makes "the host reading surface" a
    thing that can be named, defaulted, and faked in one move.

    The defaults are the real host, so ``CodexHostReaders()`` reads this machine; the
    beside-tests build one from fakes and never touch the real ``/proc`` or ``~/.codex``.
    """

    codex_home: str | os.PathLike[str] | None = None
    pids_of_comm: CommToPidList = proc_pids_of_comm
    cwd_of: PidToOptionalStr = proc_cwd
    fd_targets_of: PidToStrList = proc_fd_targets
    children_of: PidToIntList = proc_children


# --------------------------------------------------------------------------- #
# Pure readers over those couplings: filename -> id, and pid -> the ids it owns.
# --------------------------------------------------------------------------- #


def rollout_id(*, path: str) -> str | None:
    """The session id embedded in a rollout FILENAME, or None if not a rollout."""
    match = _ROLLOUT_RE.search(path or "")
    return match.group(1) if match else None


def open_rollout_ids(*, pid: int, fd_targets_of: PidToStrList = proc_fd_targets) -> list[str]:
    """The session ids of all rollout files ``pid`` holds OPEN, in fd iteration order.

    This is the structural liveness link Codex otherwise lacks. The fd table can hold
    more than one rollout, so callers must decide which id is meaningful for their
    purpose instead of treating the first fd as the process identity.
    """
    ids: list[str] = []
    for target in fd_targets_of(pid=pid):
        found = rollout_id(path=target)
        if found is not None:
            ids.append(found)
    return ids


def open_rollout_id(*, pid: int, fd_targets_of: PidToStrList = proc_fd_targets) -> str | None:
    """The first rollout id ``pid`` holds OPEN, or None if it holds none.

    Kept for callers/tests that need only the structural fact that a rollout fd is open.
    Identity selection for named sessions must use :func:`open_rollout_ids` and prefer an
    indexed id.
    """
    ids = open_rollout_ids(pid=pid, fd_targets_of=fd_targets_of)
    return ids[0] if ids else None


def carrier_rollout_ids(
    *,
    pid: int,
    carrier_pids: frozenset[int] = frozenset(),
    fd_targets_of: PidToStrList = proc_fd_targets,
    children_of: PidToIntList = proc_children,
    max_nodes: int = MAX_HELPER_PROCESSES,
) -> list[str]:
    """Every rollout id held OPEN under the identity carrier ``pid``, its OWN fds first.

    Codex 0.150 runs a session's persistence in a helper process the TUI spawns, so the
    carrier that holds the identity — the ``comm == codex`` process in the tmux pane,
    whose cwd is the repository — may hold no rollout fd of its own while its helper
    holds one. Reading only the carrier's fd table therefore loses every fresh session;
    reading the helper AS the session records the helper's cwd, which is not the
    repository. Walking DOWN from the carrier keeps both facts with their right owners.

    Own fds come first so an established session — which still holds its own rollout —
    is answered exactly as before, and so the caller's existing preference for an
    INDEXED id continues to favour the carrier's own rollout over a helper's.

    ``carrier_pids`` are the other live carriers, and the walk stops at any of them
    WITHOUT descending: a ``codex resume`` launched from another session's shell tool is
    a descendant of that session but is its OWN identity, and attributing its rollout to
    the parent would name the parent's track after someone else's topic. The walk is
    bounded by ``max_nodes`` with a visited set, so a deep, wide, or cyclic process tree
    still terminates inside one tick. Fail-soft throughout: an unreadable process
    contributes nothing rather than raising.
    """
    ids = open_rollout_ids(pid=pid, fd_targets_of=fd_targets_of)
    seen: set[int] = {pid}
    frontier = deque(children_of(pid=pid))
    while frontier and len(seen) <= max_nodes:
        helper = frontier.popleft()
        if helper in seen or helper in carrier_pids:
            continue
        seen.add(helper)
        ids.extend(open_rollout_ids(pid=helper, fd_targets_of=fd_targets_of))
        frontier.extend(children_of(pid=helper))
    return ids
