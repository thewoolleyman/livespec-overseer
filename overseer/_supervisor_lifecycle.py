"""_supervisor_lifecycle — the daemon's run loop, its singleton lock, and its start gates.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns the OUTERMOST layer: the two refusals that must hold before a
first tick (an unsupported host, and a watched repo whose ``tmp/overseer/`` is not
gitignored), the per-store singleton lock that stops two daemons fighting over one
mapping store, and the loop itself.

The loop body is :meth:`Supervisor.tick`, which stays on the class — it is three calls
to public methods and reads better beside them than behind another indirection.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_discovery
import _supervisor_state_watch
import registry
from _supervisor_config import LOOP_INTERVAL_SECONDS

if TYPE_CHECKING:
    from typing import IO

    from _supervisor_core import Supervisor

__all__: list[str] = [
    "acquire_singleton_lock",
    "release_singleton_lock",
    "run_loop",
    "singleton_lock_path",
    "unignored_tmp_repos",
    "unsupported_host_reasons",
]


def singleton_lock_path(*, sup: Supervisor) -> Path:
    store = Path(sup.store_path) if sup.store_path is not None else registry.DEFAULT_STORE_PATH
    return Path(str(store) + ".daemon.lock")


def acquire_singleton_lock(*, sup: Supervisor) -> IO[str] | None:
    """Non-blocking flock on a per-store lockfile; None if another daemon holds it.

    Two overseer daemons on the same store double-inject and double-restart —
    B's ``respawn-pane -k`` can kill the fresh session A just resumed
    (adversarial code review 2026-07-13, blocker B6 = Codex #3). Keyed to the
    store path so a scratch-store live-exercise run never contends with the
    real daemon. Fail-soft: on any OSError, return None (treat as contended).
    """
    path = singleton_lock_path(sup=sup)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("w", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return handle


def release_singleton_lock(*, handle: IO[str] | None) -> None:
    if handle is not None:
        with contextlib.suppress(OSError):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def unignored_tmp_repos(*, sup: Supervisor) -> list[str]:
    """Watched repos whose ``tmp/overseer/`` is NOT gitignored (present roots only).

    The overseer writes its markers under each track's ``<repo>/tmp/overseer/``;
    if that path is not gitignored, a marker would dirty the tracked tree — the
    exact thing the overseer must never do. A transiently-absent repo root is
    skipped (not a violation), mirroring the GC's ``repo_root_present`` guard.
    """
    return [
        repo
        for repo in _supervisor_discovery.resolve_watch(sup=sup)
        if registry.repo_root_present(repo=repo) and not sup.gitignore_check(repo=repo)
    ]


def unsupported_host_reasons(*, sup: Supervisor) -> list[str]:
    """Declared host preconditions that are ABSENT here (empty list == supported).

    Linux + tmux is a DECLARED REQUIREMENT rather than an abstraction boundary,
    so the honest failure is an immediate refusal naming what is missing — not a
    `FileNotFoundError` surfacing several ticks deep, from whichever reader
    happened to touch the host first. Two things are checked because two things
    are genuinely required: `/proc` (the Claude and Codex session readers both
    parse `/proc/<pid>/…`, and macOS has no `/proc` at all — absent, not merely
    different), and a real `tmux` on PATH (every acting mechanic shells out to
    it).
    """
    reasons: list[str] = []
    if not Path(sup.proc_root).is_dir():
        reasons.append(
            f"{os.fspath(sup.proc_root)} is not a directory — the session readers "
            "parse /proc/<pid>/ and macOS has no /proc at all (Linux is required)"
        )
    if sup.which("tmux") is None:
        reasons.append("tmux is not on PATH — every acting mechanic drives a real tmux")
    return reasons


def run_loop(
    *,
    sup: Supervisor,
    interval: float = LOOP_INTERVAL_SECONDS,
    once: bool = False,
    recover: bool = False,
) -> None:
    """Run the poll loop. ``once`` runs a single tick (live-exercise/testing).

    Holds a per-store singleton lock for its whole lifetime (B6).

    A tick that raises is NOT caught: the exception propagates, the daemon exits
    with a full traceback, and the process supervisor restarts it. B7's two
    original cases — an unreadable ``plan/`` dir and a malformed store — are now
    boundaried where they arise, by the narrow catches in
    :func:`registry.discover_plans` and ``read_row_records``, so B7 is
    discharged there rather than by a blanket guard here. What remains able to
    reach this loop is a BUG, and a bug must not be swallowed into a loop that
    keeps re-entering it.

    ``KeyboardInterrupt`` is caught to exit cleanly; ``SystemExit`` propagates
    (it is a BaseException).
    """
    unsupported = unsupported_host_reasons(sup=sup)
    if unsupported:
        sup.surface(
            message="refusing to start: unsupported host — "
            + "; ".join(unsupported)
            + " (the overseer declares Linux + tmux as a REQUIREMENT and "
            "deliberately does not abstract the host boundary)"
        )
        return
    offenders = unignored_tmp_repos(sup=sup)
    if offenders:
        sup.surface(
            message="refusing to start: tmp/overseer/ is NOT gitignored in "
            + ", ".join(offenders)
            + " — add `tmp/` to each repo's .gitignore (the overseer writes markers "
            "there and must never dirty a tracked tree)"
        )
        return
    lock = acquire_singleton_lock(sup=sup)
    if lock is None:
        sup.surface(
            message=f"another overseer daemon holds {singleton_lock_path(sup=sup)}; "
            "refusing to start"
        )
        return
    try:
        if recover:
            _ = sup.recover_missing_sessions()
        while True:
            try:
                _ = sup.tick(act=True)
            except KeyboardInterrupt:
                sup.log(message="interrupted; exiting")
                return
            # NO per-iteration broad catch. A bug in one track's tick PROPAGATES:
            # this loop lets it out, the daemon dies with a full traceback on
            # stderr, and the process supervisor restarts it. Deliberately not a
            # `try`/`except` that logs and continues — a loop that swallows a bug
            # and re-enters keeps re-reading the same bad state, so it presents as
            # supervising while enforcing nothing.
            #
            # This is safe because it is NOT where environmental failures land:
            # an unreadable `plan/` dir and a malformed store — the two cases the
            # withdrawn catch was justified by — are boundaried narrowly in
            # `registry.py` (`discover_plans`, `read_row_records`), and the
            # `UnicodeDecodeError` that used to escape those handlers is caught
            # there too. Anything reaching here is a defect, not a bad input.
            #
            # Do NOT reintroduce a catch here. The permission was withdrawn by
            # maintainer ruling and the narrowing is ratified in livespec's
            # non-functional-requirements (the supervisor-discipline rules), which
            # no longer recognizes a loop-iteration marker at all.
            if once:
                return
            _ = _supervisor_state_watch.wait_for_state_declaration(sup=sup, interval=interval)
    finally:
        release_singleton_lock(handle=lock)
