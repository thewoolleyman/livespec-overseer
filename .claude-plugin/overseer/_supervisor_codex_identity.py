"""Codex session identity for a live carrier whose rollout file is held elsewhere.

:mod:`codex_sessions` joins a live Codex process to its session through the rollout
file that process holds OPEN, and that join is exact wherever the premise holds. Codex
0.159 onward breaks the premise: persistence runs in a SHARED managed app-server, so a
carrier in a pane can hold no rollout file descriptor at all while one app-server holds
the rollouts of many independent sessions. Measured 2026-10-14 (work-item
``overseer-iffpgw``): a working Codex track in herdr pane ``w2H:p3`` yielded no
``codex:<uuid>`` identity, so the daemon could neither supervise it nor say anything
truthful about it, and its row read ``session-gone``.

This module supplies the missing identity, from the evidence that remains::

    pid  --(comm == "codex")-->     a real Codex TUI carrier
    pid  --/proc/<pid>/cwd-->       the repository that session runs in
    pid  --/proc/<pid>/environ-->   CODEX_HOME, hence its ACTIVE state database
    every live carrier + descendant --open fds--> the LIVE session id set
    (live id, carrier cwd) --(state database `threads` row)--> THIS carrier's session

Three properties of that chain are load-bearing:

- **The live-id set is deliberately UNATTRIBUTED.** The walk is not stopped at a
  sibling carrier, because the set answers "which sessions are live on this host" and
  never "whose session is this". A shared app-server is therefore no obstacle, and no
  step here can attribute one session to another carrier's track by process proximity —
  which is exactly the mis-attribution the shared daemon made possible.
- **Attribution comes from the state database, and only when it is UNIQUE.** A live id
  counts for a carrier only when the database's own ``threads`` row names that
  carrier's repository, and the answer is taken only when EXACTLY ONE live id does. Two
  live sessions in one repository leave BOTH unidentified rather than naming either:
  naming the wrong one would bind a track to another session's pane, so ambiguity fails
  closed.
- **Nothing is inferred from a rollout's write time.** The most recently written rollout
  under a cwd is not evidence about a process, and a carrier whose identity cannot be
  established from the chain above stays unidentified. That is a REPORTABLE condition
  (``session_id is None`` on a carrier that exists), not the same fact as "no Codex is
  running here".

**No rollout body is ever opened.** The live-id set comes from fd FILENAMES, and the
repository binding from the state database, which is a different file entirely — the
invariant :mod:`codex_sessions` and :mod:`_codex_runtime_model` both keep.

The host seams arrive as a :class:`codex_sessions.CodexHostReaders` bundle supplied by
the caller rather than built here, so this module imports nothing from
:mod:`_supervisor_codex_adoption`, which is one of its consumers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import _codex_runtime_model
import claude_sessions
import codex_sessions
import registry
import signals
from _seams import PidToOptionalBytes

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "CODEX_IDENTITY_PREFIX",
    "CodexPaneCarrier",
    "carrier_session_id",
    "identity_bound_codex_sessions",
    "live_rollout_ids",
    "pane_codex_carriers",
]

# The scheme every recorded Codex session identity carries, as the daemon writes it.
CODEX_IDENTITY_PREFIX = "codex:"


@dataclass(frozen=True, kw_only=True)
class CodexPaneCarrier:
    """One live Codex carrier inside a terminal pane, and the session it is proven to be.

    ``session_id`` is None when no single live session could be bound to this carrier's
    own repository. That is an UNIDENTIFIED live Codex pane, which is a different fact
    from "this track has no pane" and must never be reported as one.
    """

    pid: int
    coordinate: str
    cwd: str
    session_id: str | None
    # Herdr records the session the agent in THIS pane reports.  Unlike a rollout fd
    # on a shared app-server, this evidence belongs to the carrier rather than to a
    # process tree that may serve several TUIs.
    reported_session_id: str | None = None


def _resolved_codex_home(*, readers: codex_sessions.CodexHostReaders) -> Path:
    """The bundle's Codex home, with its ``None`` resolved to the daemon account's."""
    if readers.codex_home is None:
        return codex_sessions.default_codex_home()
    return Path(readers.codex_home)


def live_rollout_ids(
    *, carriers: list[int], readers: codex_sessions.CodexHostReaders
) -> frozenset[str]:
    """Every Codex session id a live carrier or one of its descendants holds OPEN.

    Unattributed on purpose — see the module header. The walk passes no
    ``carrier_pids``, so it descends through a shared app-server hanging off whichever
    carrier happens to have spawned it; the union is what makes the shared topology
    answerable at all, and nothing downstream reads membership as ownership.

    Unattributed is not unscoped, and the scope is re-asserted HERE rather than trusted
    from the caller: a carrier running under another Codex home contributes nothing,
    and its fd table is not opened to find that out. So every id in the union is one
    this daemon's index could name and its database could bind, which is what keeps the
    set a liveness answer rather than a census of the host.
    """
    home = _resolved_codex_home(readers=readers)
    ids: set[str] = set()
    for pid in carriers:
        if not codex_sessions.carrier_in_codex_home(
            pid=pid, codex_home=home, environ_of=readers.environ_of
        ):
            continue
        ids.update(
            codex_sessions.carrier_rollout_ids(
                pid=pid,
                fd_targets_of=readers.fd_targets_of,
                children_of=readers.children_of,
            )
        )
    return frozenset(ids)


def carrier_session_id(
    *,
    pid: int,
    cwd: str,
    candidates: frozenset[str],
    codex_home: str | os.PathLike[str] | None,
    environ_of: PidToOptionalBytes,
    reported_session_id: str | None = None,
) -> str | None:
    """The ONE live session this carrier's own state database binds to its repository.

    ``candidates`` is the live-id set, so a thread the database remembers but nothing is
    running is never a candidate. The carrier's own ``CODEX_HOME`` selects the database,
    exactly as the runtime-model reader resolves it, and the ACTIVE database is the only
    one consulted. Ambiguity and every unusable-source condition resolve to None.
    """
    home = _codex_runtime_model.carrier_codex_home(
        pid=pid, environ_of=environ_of, fallback=codex_home
    )
    database = _codex_runtime_model.active_state_database(
        codex_home=home if home is not None else codex_sessions.default_codex_home()
    )
    if database is None:
        return None
    bound = [
        candidate
        for candidate in sorted(candidates)
        if _codex_runtime_model.read_state_database_repository(
            database=database, session_id=candidate, cwd=cwd
        )
    ]
    if reported_session_id is not None:
        return reported_session_id if reported_session_id in bound else None
    return bound[0] if len(bound) == 1 else None


def _reported_session_id(*, sup: Supervisor, coordinate: str) -> str | None:
    """The terminal backend's per-pane Codex session report, if this driver has one.

    Legacy tmux has no comparable report, so a missing reader is deliberately an
    absence of evidence rather than an error.  The mixed Herdr driver supplies this
    narrow read; keeping the optional call here lets older, injected pane doubles keep
    their ordinary read-only behavior.
    """
    reader = getattr(sup.tmux, "pane_agent_session", None)
    if not callable(reader):
        return None
    value = reader(session=coordinate)
    return value if isinstance(value, str) and value else None


def pane_codex_carriers(
    *,
    sup: Supervisor,
    pane_pid_to_session: dict[int, str],
    readers: codex_sessions.CodexHostReaders,
) -> tuple[CodexPaneCarrier, ...]:
    """Every live Codex carrier that resolves to a terminal pane, with its identity.

    A carrier outside any pane, or one whose cwd cannot be read, is dropped: the daemon
    can neither observe nor drive it, and without a repository nothing can be bound.
    Order follows the ``/proc`` pid scan, so the answer is deterministic.

    The scan is scoped to carriers running under THIS daemon's Codex home
    (:func:`codex_sessions.codex_carriers`) before any of it is read. Pane membership
    alone would not do it: a daemon whose environment names no explicit tmux socket
    resolves the AMBIENT tmux server's panes too, so the operator's own Codex sessions
    arrive carrying perfectly good coordinates. Their threads live in a different state
    database and their rollouts can never be named by this daemon's index, so the only
    thing including them can do is add live ids for an ambiguity refusal to count.
    """
    carriers = list(
        codex_sessions.codex_carriers(
            codex_home=_resolved_codex_home(readers=readers),
            pids_of_comm=readers.pids_of_comm,
            environ_of=readers.environ_of,
            foreground_pgrp_of=readers.foreground_pgrp_of,
        ).scoped
    )
    candidates = live_rollout_ids(carriers=carriers, readers=readers)
    found: list[CodexPaneCarrier] = []
    for pid in carriers:
        coordinate = claude_sessions.resolve_tmux_session(
            pid=pid, pane_pid_to_session=pane_pid_to_session, ppid_of=sup.ppid_of
        )
        cwd = readers.cwd_of(pid=pid)
        if coordinate is None or not cwd:
            continue
        reported = _reported_session_id(sup=sup, coordinate=coordinate)
        found.append(
            CodexPaneCarrier(
                pid=pid,
                coordinate=coordinate,
                cwd=cwd,
                session_id=carrier_session_id(
                    pid=pid,
                    cwd=cwd,
                    candidates=candidates,
                    codex_home=readers.codex_home,
                    environ_of=sup.environ_of,
                    reported_session_id=reported,
                ),
                reported_session_id=reported,
            )
        )
    return tuple(found)


def identity_bound_codex_sessions(
    *,
    sup: Supervisor,
    pane_pid_to_session: dict[int, str],
    readers: codex_sessions.CodexHostReaders,
) -> dict[tuple[str, str], codex_sessions.CodexSession]:
    """Identified carriers keyed as the per-tick live map, bound by RECORDED identity.

    The Codex index cannot name these sessions — a fresh rollout carries no
    ``thread_name`` — so the topic comes from the mapping store instead, and only from a
    row whose ``observed_session_identity`` the daemon itself wrote while that session
    was provably alive. That is narrower than guessing from a repo cwd or a topic-like
    pane name: the recorded identity has to match exactly, the carrier has to be running
    inside that row's repository, and two rows recording one identity bind nothing.
    """
    rows = registry.read_valid_mapping(store_path=sup.store_path)
    bound: dict[tuple[str, str], codex_sessions.CodexSession] = {}
    for carrier in pane_codex_carriers(
        sup=sup, pane_pid_to_session=pane_pid_to_session, readers=readers
    ):
        if carrier.session_id is None:
            continue
        identity = f"{CODEX_IDENTITY_PREFIX}{carrier.session_id}"
        names = codex_sessions.read_thread_names(codex_home=_resolved_codex_home(readers=readers))
        claiming = [
            row
            for row in rows
            if (
                row.observed_session_identity == identity
                or (
                    carrier.reported_session_id is not None
                    and names.get(carrier.session_id)
                    == registry.tmux_id(
                        repo=row.repo,
                        topic=row.topic,
                        colliding=sup.colliding_topics,
                    )
                )
            )
            and signals.path_in_repo(pane_current_path=carrier.cwd, repo=row.repo)
        ]
        if len(claiming) != 1:
            continue
        bound[(carrier.coordinate, claiming[0].topic)] = codex_sessions.CodexSession(
            pid=carrier.pid,
            name=claiming[0].topic,
            cwd=carrier.cwd,
            session_id=carrier.session_id,
        )
    return bound
