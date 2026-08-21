"""_supervisor_discovery — what the daemon WATCHES, and the rows one tick works from.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module answers "which tracks exist right now?": it resolves the watch set,
scans it for plan directories, joins that discovery against the durable mapping store,
refreshes the per-tick Claude and Codex session maps the identity gates read, adopts
sessions that are already running, auto-links a discovered plan to a live session, and
garbage-collects the rows of archived plans.

It holds NO judgment about any single track — :meth:`Supervisor.evaluate` owns that. The
rows this produces are the INPUT to the cascade, not a verdict.

Free functions taking the ``Supervisor`` as a parameter; ``Supervisor`` is imported under
``TYPE_CHECKING`` only, so the annotation resolves for pyright-strict while no runtime
import cycle exists. This module imports none of its siblings.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import _supervisor_codex_adoption
import claude_sessions
import registry
import signals
from _supervisor_archive_gc import archive_gc as archive_gc
from _supervisor_config import iso_now
from _supervisor_discovery_adoption import adopt_sessions as _adopt_sessions
from _supervisor_discovery_adoption import profile_for_adoption, sessions_dir
from _supervisor_unindexed_codex import unindexed_codex_rows as _unindexed_codex_rows
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "adopt_sessions",
    "archive_gc",
    "auto_link",
    "build_rows",
    "refresh_claude_status",
    "refresh_codex_sessions",
    "resolve_watch",
    "sessions_dir",
    "unindexed_codex_rows",
]


def auto_link(*, sup: Supervisor, track: registry.Track) -> registry.Track | None:
    """Link a live session to an unassigned discovered plan — safely.

    A link is created ONLY when a session named ``tmux_id(repo, topic)`` (the
    bare plan topic, or ``<repo-slug>-<topic>`` on a cross-repo collision — the
    SAME name the daemon would spawn) exists AND its ``#{pane_current_path}``
    resolves inside the row's repo. The ``path_in_repo`` guard is what actually
    prevents cross-linking two repos that share a topic (blocker #8): even if a
    colliding topic were not repo-qualified, the pane's cwd must match the row's
    repo. Returns the new mapped Track, or None if not linked.
    """
    session = registry.tmux_id(repo=track.repo, topic=track.topic, colliding=sup.colliding_topics)
    if not sup.tmux.session_exists(session=session):
        return None
    path = sup.tmux.pane_current_path(session=session)
    if not signals.path_in_repo(pane_current_path=path, repo=track.repo):
        return None
    linked = registry.PlanTrack(
        topic=track.topic,
        repo=track.repo,
        tmux=session,
        epic=track.epic or registry.unresolved_plan_epic(topic=track.topic),
    )
    registry.append_mapping(track=linked, store_path=sup.store_path, added_at=iso_now())
    sup.log(message=f"auto-linked live session {session} → {track.repo}::{track.topic}")
    return linked


_profile_for_adoption = profile_for_adoption


def adopt_sessions(*, sup: Supervisor) -> list[registry.Track]:
    """Adopt live sessions whose registry name matches an active plan topic."""
    return _adopt_sessions(sup=sup, watch=resolve_watch(sup=sup))


def refresh_codex_sessions(*, sup: Supervisor) -> None:
    """Recompute this tick's ``{(tmux_session, name): CodexSession}`` map (read-only).

    The Codex twin of :meth:`_refresh_claude_status`, and the ONLY honest way to ask
    "is this pane Codex?": tmux reports a codex pane's ``#{pane_current_command}`` as
    **`bun`** (the launcher; the vendored codex binary is its child), and `bun` is
    generic — any bun app matches it. Membership in this map is exact: a session is in
    it only because a real codex process, holding a real rollout, resolved to that
    tmux session THIS tick. Keyed by ``(tmux_session, name)`` so two codex sessions
    sharing one tmux session never shadow each other (see
    :func:`codex_sessions.codex_by_tmux_session`). Derived live, so it needs no stored
    ``runtime`` field on the mapping and cannot drift. Fail-soft to an empty map (no
    codex running is the overwhelmingly common case).
    """
    sup.live_codex = _supervisor_codex_adoption.codex_sessions_by_tmux_session(
        sup=sup, pane_pid_to_session=sup.tmux.pane_pid_sessions()
    )


def refresh_claude_status(*, sup: Supervisor) -> None:
    """Recompute this tick's ``{tmux_session: claude_status}`` map (read-only).

    Runs at the top of every ``build_rows`` — including the read-only ``list`` path —
    so ``evaluate`` can fold Claude's own ``status: "busy"`` self-report into its busy
    check. It reads only the registry + ``/proc`` (no store mutation), so it is safe on
    the read-only path. Fail-soft: any read error yields an empty map (no session
    marked busy from this signal), never a raised exception.
    """
    pane_pids = sup.tmux.pane_pid_sessions()
    # `status` feeds the busy check (last-wins is fine); `names` feeds the identity gate's
    # `topic in names` parity check (R2) and is a SET so a helper Claude in the same tmux
    # session cannot shadow the track's name (review SF5). Both from the same registry.
    sup.claude_status_by_session = claude_sessions.status_by_tmux_session(
        sessions_dir=sessions_dir(sup=sup),
        pane_pid_to_session=pane_pids,
        ppid_of=sup.ppid_of,
        starttime_of=sup.starttime_of,
    )
    sup.claude_identity_by_session = claude_sessions.identities_by_tmux_session(
        sessions_dir=sessions_dir(sup=sup),
        pane_pid_to_session=pane_pids,
        ppid_of=sup.ppid_of,
        starttime_of=sup.starttime_of,
    )
    sup.claude_names_by_session = claude_sessions.names_by_tmux_session(
        sessions_dir=sessions_dir(sup=sup),
        pane_pid_to_session=pane_pids,
        ppid_of=sup.ppid_of,
        starttime_of=sup.starttime_of,
    )
    refresh_codex_sessions(sup=sup)


def unindexed_codex_rows(*, sup: Supervisor) -> list[RowView]:
    return _unindexed_codex_rows(sup=sup, watch=resolve_watch(sup=sup))


def build_rows(*, sup: Supervisor, act: bool = True) -> list[registry.Track]:
    """Discovery ⋈ mapping (the tick's row set).

    When ``act`` (the daemon loop) this runs archive-GC + registry adoption +
    auto-link, all of which MUTATE the store. When NOT ``act`` (the ``list``
    command, advertised read-only) it does NONE — it just joins discovery
    against the current mapping, so `list` cannot silently rewrite / GC /
    adopt / re-link the store out from under a running daemon (adversarial code
    review 2026-07-13, blocker B6).
    """
    refresh_claude_status(sup=sup)
    watch = resolve_watch(sup=sup)
    discovered = registry.discover_plans(watch_repos=watch)
    # Recompute the cross-repo collision set for THIS tick before any session-name
    # derivation (adopt / auto_link / evaluate → `_session_of`) runs, so they all
    # agree on which topics must be repo-qualified. Set ABOVE the `not act` return so
    # the read-only `list` path derives display names identically.
    sup.colliding_topics = registry.colliding_topics(discovered=discovered)
    if not act:
        return registry.join(
            discovered=discovered, mapping=registry.read_valid_mapping(store_path=sup.store_path)
        )
    _ = archive_gc(sup=sup)
    # Continuous adoption (not just at bootstrap): pick up any live Claude
    # session whose registry name is now an active topic — so a session that
    # was mid-prompt, renamed, or launched after startup is tracked within one
    # tick rather than being missed forever.
    _ = _adopt_sessions(sup=sup, watch=watch)
    rows = registry.join(
        discovered=discovered, mapping=registry.read_valid_mapping(store_path=sup.store_path)
    )
    linked_any = False
    for row in rows:
        if row.is_unassigned and auto_link(sup=sup, track=row) is not None:
            linked_any = True
    if linked_any:
        rows = registry.join(
            discovered=discovered, mapping=registry.read_valid_mapping(store_path=sup.store_path)
        )
    return rows


def resolve_watch(*, sup: Supervisor) -> list[str]:
    if sup.watch_repos is not None:
        return [os.path.normpath(r) for r in sup.watch_repos]
    if sup.watch_set_path is not None:
        return registry.watch_set_from_config(
            config_path=sup.watch_set_path, extra_repos=sup.extra_repos
        )
    return [os.path.normpath(r) for r in sup.extra_repos]
