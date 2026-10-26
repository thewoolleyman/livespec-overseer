"""Live Codex TUI session discovery — the Codex twin of :mod:`claude_sessions`.

Codex sessions are invisible to the daemon: they are not in Claude's registry
(``~/.claude/sessions/<pid>.json``), so ``adopt_sessions`` cannot map a running Codex
session to its plan. This module supplies the missing join, in the same shape
``claude_sessions`` supplies for Claude — a list of live, NAMED sessions carrying
``pid`` / ``name`` (= the plan topic) / ``cwd`` — so adoption can treat the two
runtimes uniformly and ``claude_sessions.resolve_tmux_session`` (already
runtime-agnostic) joins either to its tmux session.

**The join, and why it is exact rather than a heuristic.** Codex keeps no pid-keyed
registry, which is why this looked hard. But a running Codex session **holds its
rollout file open**, and the rollout FILENAME embeds the session id, which
``session_index.jsonl`` maps to the ``thread_name`` — the plan topic::

    pid  --(comm == "codex")-->            a real Codex TUI process
    pid  --/proc/<pid>/fd/*-->             rollout-<ts>-<session id>.jsonl
       (0.150: that fd is held by a HELPER the TUI spawned — see below)
    id   --session_index.jsonl-->          thread_name   == THE PLAN TOPIC
    pid  --/proc/<pid>/cwd-->              THE REPO

Verified end-to-end live (2026-07-16) against a real 2-day-old codex TUI: pid 1682090
→ ``rollout-2026-07-12T06-19-39-019f548d-….jsonl`` → cwd ``/data/projects/openbrain``.
See ``plan/overseer-rewrite/research/codex-ctx-and-restart-evidence.md``.

**Codex 0.150 moved rollout OWNERSHIP off the TUI process, and the fix is a walk, not
a weaker identity test.** Attended host evidence (work-item ``overseer-qmarlj``): a
fresh real TUI in the exact repository persisted its ``/rename`` entry in
``session_index.jsonl``, yet this module returned NO live record for it — while
established sessions, started before the upgrade and still holding their own fd,
remained discoverable. What changed is WHICH process holds the rollout: the session's
persistence now runs in a helper the TUI spawns (Codex's app-server), so the TUI —
the process that carries the identity, sits in the tmux pane, and whose ``cwd`` IS the
repository — holds no rollout fd at all, and the helper's own ``cwd`` is not the
repository. Both halves matter, and reading the helper as if it were the session would
record the WRONG repo.

So the carrier is unchanged (``comm == "codex"``, its ``/proc/<pid>/cwd``) and only the
ROLLOUT lookup widened: :func:`carrier_rollout_ids` reads the carrier's own fds first,
then those of the helper processes it spawned. The walk stops at any process that is
ITSELF a carrier, so a ``codex resume`` launched from another session's shell tool
keeps its own identity instead of being attributed to its parent. Nothing about the
proof is weakened: an exact indexed name plus the carrier's own process cwd are still
both required, and a session with neither is still dropped.

**The carrier scan is host-wide; the EVIDENCE is scoped to one Codex home.** ``comm``
is the only thing that says a process is a Codex carrier, so the scan has to look at
every pid — but a carrier running under a DIFFERENT ``CODEX_HOME`` cannot be named by
the index this module reads, so :func:`codex_carriers` drops it before its cwd or fd
table is read. On a fleet host every carrier shares the daemon account's home and
nothing narrows; it narrows exactly where a second Codex world exists, which is the
isolated live exercise (work-item ``overseer-crjbmp``) — in both directions, so the
fleet daemon does not read the exercise's stub either.

**The adoption precondition: only INDEXED/NAMED sessions can be mapped to a plan.**
An unnamed session carries no topic anywhere, so it cannot be joined to a plan. The
supervisor surfaces live unindexed Codex sessions in watched repos as diagnostic
``codex-unindexed`` rows; it still does not invent a topic or read transcript bodies.

**Secrets caution — this module NEVER reads a rollout's contents.** Rollout ``.jsonl``
files are full session transcripts. The join needs only the FILENAME (for the id) and
``/proc``, so nothing here opens one. Keep it that way.

**Ctx% is deliberately NOT read here.** An earlier cut computed it from the rollout's
``token_count`` events and was WRONG by 2-4 points against Codex's own display, because
that reimplements codex-rs's occupancy formula (which subtracts a ~12k baseline and
excludes reasoning tokens from occupancy) — a private internal that can drift with any
Codex release. Codex renders ``Context N% left`` in its statusline; that is its OWN
number, and ``signals.parse_ctx_remaining`` reads it exactly as it reads Claude's
``Ctx: N% left``. Do not reintroduce a local occupancy formula.

Stdlib-only, like every module in this folder. Every host coupling (``/proc`` reads)
is injected so the beside-tests run with no codex process and no real ``~/.codex``.

The ``/proc`` half — the readers themselves, the rollout-filename parse, and the
carrier walk — lives in :mod:`_codex_proc` and is re-exported here, so this module is
still the whole consumer surface. Patch those names through ``_codex_proc``, which
DEFINES them: a façade re-export can be monkeypatched successfully while the real
reader keeps its own binding, which is a green test over the live host.
"""

from __future__ import annotations

import os
from pathlib import Path

import codex_session_index
from _codex_proc import (
    CODEX_HOME_ENV,
    MAX_HELPER_PROCESSES,
    CodexHostReaders,
    carrier_in_codex_home,
    carrier_rollout_ids,
    codex_carriers,
    open_rollout_id,
    open_rollout_ids,
    proc_cwd,
    proc_environ_value,
    proc_fd_targets,
    proc_foreground_pgrp,
    proc_pids_of_comm,
    rollout_id,
)
from _codex_session_models import CODEX_COMM, CodexSession, UnindexedCodexSession
from _seams import (
    PidToOptionalInt,
)

# `proc_children` is a GENERIC /proc reader that happens to live in `claude_sessions`,
# which already hosts the runtime-agnostic readers used for Codex (`has_active_subshell`
# — the Codex busy fallback — is built on them). Reusing it beats duplicating a reader
# into a sibling module.
from claude_sessions import proc_ppid, resolve_tmux_session

__all__: list[str] = [
    "CODEX_COMM",
    "CODEX_HOME_ENV",
    "MAX_HELPER_PROCESSES",
    "CodexHostReaders",
    "CodexSession",
    "UnindexedCodexSession",
    "carrier_in_codex_home",
    "carrier_rollout_ids",
    "codex_by_tmux_session",
    "codex_carriers",
    "default_codex_home",
    "latest_session_for_thread_name",
    "map_codex_sessions",
    "map_unindexed_codex_sessions",
    "open_rollout_id",
    "open_rollout_ids",
    "proc_cwd",
    "proc_environ_value",
    "proc_fd_targets",
    "proc_foreground_pgrp",
    "proc_pids_of_comm",
    "read_live_codex_sessions",
    "read_thread_names",
    "rollout_exists",
    "rollout_id",
]


def default_codex_home() -> Path:
    """``~/.codex`` — where Codex writes ``session_index.jsonl`` and ``sessions/``."""
    return Path.home() / ".codex"


def read_thread_names(*, codex_home: str | os.PathLike[str]) -> dict[str, str]:
    """``session_index.jsonl`` as ``{session id: thread_name}`` (last record per id wins)."""
    return codex_session_index.read_thread_names(codex_home=codex_home)


def latest_session_for_thread_name(
    *, thread_name: str, codex_home: str | os.PathLike[str] | None = None
) -> str | None:
    """The session id of the most-recently-updated indexed session named ``thread_name``.

    Reverses ``session_index.jsonl`` — which SURVIVES the session's death, unlike the live
    rollout fd a running codex holds open — so reboot recovery can learn a DEAD codex track's
    session id from its plan topic (the ``thread_name``). Among ids whose final name matches,
    the one with the greatest ``updated_at`` wins (RFC3339 UTC strings, lexicographically
    ordered, and distinct per id in real index data — verified live 2026-07-18, so the pick is
    unambiguous). Returns None when the topic names no indexed session — the caller treats such
    a track as Claude. Fail-soft: a missing/unreadable index yields None.
    """
    home = Path(codex_home) if codex_home is not None else default_codex_home()
    return codex_session_index.latest_session_for_thread_name(
        thread_name=thread_name, codex_home=home
    )


def rollout_exists(*, session_id: str, codex_home: str | os.PathLike[str] | None = None) -> bool:
    """True if a rollout file for ``session_id`` still exists under ``<codex_home>/sessions``.

    A rollout is ``rollout-<iso-ts>-<session id>.jsonl``, nested under ``sessions/YYYY/MM/DD/``
    (verified live). A dead session's rollout persists on disk, and its presence is what
    ``codex resume`` needs to reattach — so reboot recovery gates option (c) on it: rollout
    present ⇒ ``codex resume <id>`` can reattach the SAME conversation; rollout gone ⇒ recovery
    falls back to skip+surface (option b) rather than mis-recreating the track as Claude
    (which would orphan the rollout). The ``session_id`` is a UUID (no glob metacharacters), so
    it is safe to interpolate into the pattern. Fail-soft to False.
    """
    home = Path(codex_home) if codex_home is not None else default_codex_home()
    return codex_session_index.rollout_exists(session_id=session_id, codex_home=home)


def read_live_codex_sessions(
    *,
    codex_home: str | os.PathLike[str] | None = None,
    readers: CodexHostReaders | None = None,
) -> list[CodexSession]:
    """Every live, NAMED Codex TUI session, joined to its topic + repo.

    Liveness is structural: the pid came from a ``/proc`` scan this instant, and the
    session must still hold an open rollout — its own, or its helper's — and a readable
    cwd. So there is no stale-file problem to defeat (Claude's registry needs a
    ``procStart`` check precisely because its files outlive their process; an fd cannot).

    Skips, all deliberate and all fail-soft:

    - not ``comm == codex`` — including the ``bun`` launcher (holds no rollout anyway);
    - no terminal foreground group — an app-server helper is not the pane TUI even
      when it holds the rollout and shares the repository cwd;
    - **running under a DIFFERENT Codex home** (:func:`codex_carriers`) — its rollouts
      can never appear in the index this call reads, so it is not this daemon's session
      and nothing of it is read;
    - neither it nor its helpers hold an open rollout — no session id to join;
    - **its id is not in the index** — an UNNAMED session, which carries no topic
      anywhere and so cannot belong to a plan;
    - no readable cwd — the pid vanished mid-read.

    The reported ``pid`` and ``cwd`` are always the CARRIER's, never a helper's: the
    carrier is the process in the tmux pane, and its cwd is the repository the session
    is running in (see :func:`carrier_rollout_ids`).

    ``Codex Companion Task: …`` threads are deliberately NOT filtered here: they fail
    the "is this an ACTIVE plan topic?" test at adoption, so the noise filters itself
    and this stays a pure, dumb join with no policy in it.
    """
    host = readers if readers is not None else CodexHostReaders(codex_home=codex_home)
    home = (
        Path(codex_home)
        if codex_home is not None
        else (Path(host.codex_home) if host.codex_home is not None else default_codex_home())
    )
    names = read_thread_names(codex_home=home)
    carriers = codex_carriers(
        codex_home=home,
        pids_of_comm=host.pids_of_comm,
        environ_of=host.environ_of,
        foreground_pgrp_of=host.foreground_pgrp_of,
    )
    carrier_pids = frozenset(carriers.all_pids)
    out: list[CodexSession] = []
    for pid in carriers.scoped:
        session_id = next(
            (
                rollout
                for rollout in carrier_rollout_ids(
                    pid=pid,
                    carrier_pids=carrier_pids,
                    fd_targets_of=host.fd_targets_of,
                    children_of=host.children_of,
                )
                if names.get(rollout)
            ),
            None,
        )
        if session_id is None:
            continue
        name = names[session_id]
        cwd = host.cwd_of(pid=pid)
        if not cwd:
            continue
        out.append(CodexSession(pid=pid, name=name, cwd=cwd, session_id=session_id))
    return out


def map_codex_sessions(
    *,
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    readers: CodexHostReaders | None = None,
) -> list[tuple[str, str, str]]:
    """``[(tmux_session, name, cwd)]`` for every live NAMED codex session held in tmux.

    The exact twin of :func:`claude_sessions.map_named_sessions`, emitting the SAME
    triple on purpose: ``adopt`` can then consume either runtime through ONE code path
    instead of growing a parallel Codex branch that could drift from the Claude one.

    Composes :func:`read_live_codex_sessions` with
    :func:`claude_sessions.resolve_tmux_session` — which is already runtime-agnostic
    (it walks a pid up to a tmux pane pid and cares nothing for what the process is),
    so Codex needs no tmux-joining code of its own. A live session not inside any tmux
    pane is omitted: there is no pane to capture, inject, or respawn. Order follows the
    ``/proc`` pid scan, so the mapping is deterministic.
    """
    host = readers if readers is not None else CodexHostReaders()
    mapped: list[tuple[str, str, str]] = []
    for session in read_live_codex_sessions(
        readers=host,
    ):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is None:
            continue
        mapped.append((tmux_session, session.name, session.cwd))
    return mapped


def map_unindexed_codex_sessions(
    *,
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    readers: CodexHostReaders | None = None,
) -> list[UnindexedCodexSession]:
    """Delegate unindexed diagnostic discovery to its dedicated join module."""
    from _codex_unindexed_sessions import map_unindexed_codex_sessions as read_unindexed

    return read_unindexed(
        pane_pid_to_session=pane_pid_to_session,
        ppid_of=ppid_of,
        readers=readers,
    )


def codex_by_tmux_session(
    *,
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    readers: CodexHostReaders | None = None,
) -> dict[tuple[str, str], CodexSession]:
    """``{(tmux_session, name): CodexSession}`` for every live NAMED codex session in tmux.

    The twin of :func:`claude_sessions.status_by_tmux_session`, and the per-tick map the
    supervisor keys Codex behavior off — recomputed every tick like ``claude_status_by_session``,
    so it is always live and self-correcting.

    **Why a map and not a pane-command predicate.** tmux reports a codex pane's
    ``#{pane_current_command}`` as **`bun`**, NOT `codex`: the pane's foreground process
    is the `bun` launcher and the vendored codex binary is its CHILD (verified live). And
    `bun` is generic — ANY bun app would match it. So "is this pane Codex?" cannot be
    answered honestly from the pane command. Membership in THIS map answers it exactly:
    the session is in it only because a real codex process, holding a real rollout,
    resolved to that tmux session this tick. It also needs no stored ``runtime`` field on
    the mapping (nothing to migrate, nothing to drift).

    **Keyed by ``(tmux_session, name)``, not ``tmux_session`` alone.** Two codex sessions
    can share ONE tmux session — a second split, or a ``codex resume <topic>`` spawned
    from another session's Bash tool — each carrying a DIFFERENT ``name`` (= its plan
    topic). A single value per tmux session would let the second SHADOW the first, so that
    track silently loses its ctx reading, its wrap-up, and its restart — invisible in the
    table. Keying by the ``(tmux_session, name)`` pair keeps BOTH, so the supervisor's
    ``_is_codex_track`` / ``_do_codex_restart`` resolve each track to ITS OWN session by
    ``(tmux, topic)``. This is the codex analogue of the set-valued
    :func:`claude_sessions.names_by_tmux_session` (R2 review SF5). Only a genuine
    same-``(tmux, name)`` collision — two codex processes for the SAME topic in the SAME
    tmux session — keeps the FIRST by pid order (deterministic; the daemon drives one
    session per pane anyway).
    """
    host = readers if readers is not None else CodexHostReaders()
    by_key: dict[tuple[str, str], CodexSession] = {}
    for session in read_live_codex_sessions(
        readers=host,
    ):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is None:
            continue
        key = (tmux_session, session.name)
        if key in by_key:
            continue
        by_key[key] = session
    return by_key
