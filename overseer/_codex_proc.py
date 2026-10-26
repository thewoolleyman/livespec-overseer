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

from _codex_session_models import CODEX_COMM
from _seams import (
    CommToPidList,
    PidToIntList,
    PidToOptionalBytes,
    PidToOptionalInt,
    PidToOptionalStr,
    PidToStrList,
)

# `proc_comm` / `proc_children` / `proc_environ` are GENERIC /proc readers that happen to
# live in `claude_sessions`, which already hosts the runtime-agnostic readers used for
# Codex (`has_active_subshell` — the Codex busy fallback — is built on them). Reusing
# them beats duplicating a reader into a sibling module.
from claude_sessions import proc_children, proc_comm, proc_environ

__all__: list[str] = [
    "CODEX_HOME_ENV",
    "HOME_ENV",
    "MAX_HELPER_PROCESSES",
    "CodexCarriers",
    "CodexHostReaders",
    "carrier_codex_scope",
    "carrier_in_codex_home",
    "carrier_rollout_ids",
    "codex_carriers",
    "open_rollout_id",
    "open_rollout_ids",
    "proc_cwd",
    "proc_environ_value",
    "proc_fd_targets",
    "proc_foreground_pgrp",
    "proc_pids_of_comm",
    "rollout_id",
]

# The two environment variables Codex itself resolves its home from, in this order.
CODEX_HOME_ENV = "CODEX_HOME"
HOME_ENV = "HOME"

# `<home>/.codex` — the layout Codex uses when nothing names a home explicitly.
_CODEX_HOME_RELATIVE = ".codex"

# `rollout-<iso-ts>-<uuid>.jsonl`. Anchored on the trailing uuid + extension so a
# rollout is never confused with a sibling file in the same tree.
_ROLLOUT_RE = re.compile(
    r"rollout-.*-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$"
)

# How many helper processes below one identity carrier the rollout walk will visit. A
# Codex session's helper sits one level down and brings a handful of processes with it;
# the bound is what keeps a pathological (or cyclic) process tree from stalling a tick.
MAX_HELPER_PROCESSES = 64
_STAT_REQUIRED_FIELDS = 6


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


def proc_foreground_pgrp(*, pid: int) -> int | None:
    """The foreground terminal process group of ``pid``, or None when it has none.

    A Codex TUI runs in its pane terminal's foreground group. Its app-server helpers
    create detached sessions instead, even when their ``comm`` and cwd match the TUI.
    ``stat`` fields 5, 7, and 8 are the process group, controlling terminal, and
    terminal foreground group respectively.
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    cut = raw.rfind(")")
    if cut == -1:
        return None
    fields = raw[cut + 1 :].split()
    if len(fields) < _STAT_REQUIRED_FIELDS:
        return None
    try:
        pgrp = int(fields[2])
        tty_number = int(fields[4])
        foreground_pgrp = int(fields[5])
    except ValueError:
        return None
    if tty_number == 0 or foreground_pgrp <= 0 or pgrp != foreground_pgrp:
        return None
    return foreground_pgrp


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


def proc_environ_value(
    *, pid: int, name: str, environ_of: PidToOptionalBytes = proc_environ
) -> str | None:
    """One NON-EMPTY value a live process declares in its environment, else None.

    The single parse of ``/proc/<pid>/environ`` in this package: an unreadable environ,
    an absent key and an empty value are one answer — "this process declares nothing" —
    so every caller fails soft in the same direction.
    """
    for item in (environ_of(pid=pid) or b"").split(b"\0"):
        key, separator, value = item.decode(errors="replace").partition("=")
        if separator and key == name and value:
            return value
    return None


@dataclass(frozen=True, kw_only=True)
class CodexHostReaders:
    """Everything needed to read live Codex sessions off ONE host, as one value.

    These six travel together — every consumer that wants live Codex sessions wants
    all of them — and the tmux-joining wrappers in :mod:`codex_sessions` carry the join
    seams on top, which is more parameters than a signature can state readably. Bundling
    the host side keeps those wrappers legible and makes "the host reading surface" a
    thing that can be named, defaulted, and faked in one move.

    ``environ_of`` is here for ONE purpose: :func:`codex_carriers` asks each carrier
    which Codex home it runs under, and that question has to be answered before the
    cwd and fd readers are allowed anywhere near it. ``foreground_pgrp_of`` establishes
    that the process is the pane TUI rather than a detached app-server helper.

    The defaults are the real host, so ``CodexHostReaders()`` reads this machine; the
    beside-tests build one from fakes and never touch the real ``/proc`` or ``~/.codex``.
    """

    codex_home: str | os.PathLike[str] | None = None
    pids_of_comm: CommToPidList = proc_pids_of_comm
    cwd_of: PidToOptionalStr = proc_cwd
    fd_targets_of: PidToStrList = proc_fd_targets
    children_of: PidToIntList = proc_children
    environ_of: PidToOptionalBytes = proc_environ
    foreground_pgrp_of: PidToOptionalInt = proc_foreground_pgrp


@dataclass(frozen=True, kw_only=True)
class CodexCarriers:
    """Every live Codex carrier on the host, split by whether it is THIS daemon's.

    ``scoped`` is the set whose evidence may be read; ``all_pids`` is kept because the
    rollout walk needs it for a different job — it stops at ANY TUI carrier, in or out of
    scope, so a ``codex resume`` launched from another session's shell tool is never
    attributed to the carrier that spawned it. That stop-set is pid identity alone and
    reads nothing from a process, which is why it stays host-wide.
    """

    all_pids: tuple[int, ...]
    scoped: tuple[int, ...]


def carrier_codex_scope(*, pid: int, environ_of: PidToOptionalBytes, fallback: Path) -> Path:
    """The Codex home THIS carrier runs under, resolved the way Codex resolves it.

    ``CODEX_HOME`` when the carrier declares a non-empty one, else ``<HOME>/.codex``
    from the ``HOME`` it declares — the shape a process that simply inherited the
    account's home takes, which is every ordinary Codex session. A carrier that
    declares NEITHER (an environ this daemon cannot read at all) resolves to
    ``fallback``, the daemon's own home: exclusion needs POSITIVE evidence of another
    home, so an unreadable environ can never hide a live track.
    """
    declared = proc_environ_value(pid=pid, name=CODEX_HOME_ENV, environ_of=environ_of)
    if declared is not None:
        return Path(declared)
    home = proc_environ_value(pid=pid, name=HOME_ENV, environ_of=environ_of)
    return fallback if home is None else Path(home) / _CODEX_HOME_RELATIVE


def carrier_in_codex_home(
    *,
    pid: int,
    codex_home: Path,
    environ_of: PidToOptionalBytes = proc_environ,
) -> bool:
    """Whether this carrier runs under ``codex_home`` — the one scope test, shared.

    Asked by the enumerations in :func:`codex_carriers` AND by every reader that would
    otherwise take a caller's word for which carriers it may read. Keeping the test in
    the reader rather than only in the enumeration is deliberate: a public function
    that quietly reads whatever pid it is handed is a footgun, and the whole point of
    the scope is that a foreign carrier's fd table is never opened.

    The comparison resolves both sides, so a symlinked home, a relative declaration and
    a ``~`` in either path all compare as the directory they name.
    """
    scope = carrier_codex_scope(pid=pid, environ_of=environ_of, fallback=codex_home)
    return scope.expanduser().resolve() == codex_home.expanduser().resolve()


def codex_carriers(
    *,
    codex_home: Path,
    pids_of_comm: CommToPidList = proc_pids_of_comm,
    environ_of: PidToOptionalBytes = proc_environ,
    foreground_pgrp_of: PidToOptionalInt | None = None,
) -> CodexCarriers:
    """Live Codex carriers, scoped to the ones running under ``codex_home``.

    The scan itself is host-wide and has to be: ``comm`` plus membership in a terminal
    foreground group identifies a Codex TUI. A detached helper can share the binary's
    ``comm`` and repository cwd, so cannot be a carrier without terminal evidence. What
    is scoped is which of those carriers count as EVIDENCE, and the Codex home is the
    seam the daemon's own joins already turn on —
    the index that names a session, the rollout filenames that carry its id and the
    state database that binds it to a repository all live under ONE home. A carrier
    under a different one cannot be named by this daemon's index and cannot have a row
    in its database, so reading it adds nothing but another candidate for an ambiguity
    refusal to count.

    On a fleet host every carrier shares the daemon account's home, declared or
    inherited, so ``scoped`` is ``all_pids`` and nothing narrows. It narrows exactly
    where it should: a daemon supervising a sandboxed Codex world (the isolated live
    exercise) stops reading the operator's real sessions, and the fleet daemon stops
    reading the exercise's stub.
    """
    foreground = proc_foreground_pgrp if foreground_pgrp_of is None else foreground_pgrp_of
    found = tuple(pid for pid in pids_of_comm(comm=CODEX_COMM) if foreground(pid=pid) is not None)
    return CodexCarriers(
        all_pids=found,
        scoped=tuple(
            pid
            for pid in found
            if carrier_in_codex_home(pid=pid, codex_home=codex_home, environ_of=environ_of)
        ),
    )


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
