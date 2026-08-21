"""Live-session adoption for discovered supervisor tracks."""

from __future__ import annotations

import collections
import os
from typing import TYPE_CHECKING

import claude_sessions
import codex_sessions
import registry
import signals
from _supervisor_config import iso_now
from _supervisor_launch_profile import LaunchProfileProblem, read_launch_profile
from _supervisor_launch_profile_sources import (
    CodexProfileReaders,
    LaunchProfileSource,
    live_profile_sources,
)
from _supervisor_statusline_model import rendered_statusline_model as statusline_model

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "adopt_sessions",
    "profile_for_adoption",
    "sessions_dir",
]


def _codex_profile_readers(*, sup: Supervisor) -> CodexProfileReaders:
    return CodexProfileReaders(
        codex_home=sup.codex_home,
        pids_of_comm=sup.codex_pids_of_comm,
        cwd_of=sup.codex_cwd_of,
        fd_targets_of=sup.codex_fd_targets_of,
    )


def profile_for_adoption(
    *,
    sup: Supervisor,
    source: LaunchProfileSource | None,
    session: str,
    repo: str | None = None,
    topic: str | None = None,
) -> dict[str, str | None] | None:
    if source is None:
        return None
    profile = read_launch_profile(
        pid=source.pid,
        harness=source.harness,
        pane_pid=source.pane_pid,
        cmdline_of=sup.cmdline_of,
        environ_of=sup.environ_of,
        ppid_of=sup.ppid_of,
    )
    if isinstance(profile, LaunchProfileProblem):
        sup.log(message=profile.message)
        return None
    baseline = (
        None
        if repo is None or topic is None
        else registry.read_launch_statusline_baseline(
            repo=repo,
            topic=topic,
            stamp_path=sup.stamp_path,
        )
    )
    profile["statusline_model"] = baseline or statusline_model(
        capture=sup.tmux.capture_pane(session=session)
    )
    return profile


def _adoptable_live_sessions(
    *,
    sup: Supervisor,
    pane_pids: dict[int, str],
) -> list[tuple[str, str, str]]:
    return claude_sessions.map_named_sessions(
        sessions_dir=sessions_dir(sup=sup),
        pane_pid_to_session=pane_pids,
        ppid_of=sup.ppid_of,
        starttime_of=sup.starttime_of,
    ) + codex_sessions.map_codex_sessions(
        pane_pid_to_session=pane_pids,
        codex_home=sup.codex_home,
        ppid_of=sup.ppid_of,
        pids_of_comm=sup.codex_pids_of_comm,
        cwd_of=sup.codex_cwd_of,
        fd_targets_of=sup.codex_fd_targets_of,
    )


def _live_profile_sources(
    *,
    sup: Supervisor,
    pane_pids: dict[int, str],
) -> dict[tuple[str, str], LaunchProfileSource]:
    return live_profile_sources(
        sessions_dir=sessions_dir(sup=sup),
        pane_pid_to_session=pane_pids,
        ppid_of=sup.ppid_of,
        starttime_of=sup.starttime_of,
        codex_readers=_codex_profile_readers(sup=sup),
    )


def _active_topics_by_repo(*, watch: list[str]) -> dict[str, set[str]]:
    active: dict[str, set[str]] = {}
    for repo, topic in registry.discover_plans(watch_repos=watch):
        active.setdefault(repo, set()).add(topic)
    return active


def _mapped_tmux_by_track(*, sup: Supervisor) -> dict[tuple[str, str], str | None]:
    mapping = registry.read_valid_mapping(store_path=sup.store_path)
    for track in mapping:
        epic = track.epic
        if registry.epic_is_resolved(epic=epic) and epic is not None:
            sup.mapping_epics[(registry.norm(repo=track.repo), track.topic)] = epic
    return {(registry.norm(repo=track.repo), track.topic): track.tmux for track in mapping}


def adopt_sessions(*, sup: Supervisor, watch: list[str]) -> list[registry.Track]:
    """Adopt live Claude sessions whose registry name matches an active plan topic.

    Run at `/overseer` startup AND every daemon tick (so a session that is
    renamed, un-blocks a prompt, or is launched later is picked up within one
    interval — not only at bootstrap). It reads Claude Code's own session
    registry (:mod:`claude_sessions`, ``~/.claude/sessions/<pid>.json``) rather
    than scraping the pane: each live session reports its display ``name`` and
    ``cwd`` in a file keyed by the claude PID, which :mod:`claude_sessions`
    joins to the owning tmux session by walking that PID up to a tmux pane PID.
    This is screen-independent, so it works while a session is showing a prompt
    (the exact case the old input-box-border scrape missed), and it reflects a
    runtime ``/rename`` — the maintainer's sessions run
    ``claude --dangerously-skip-permissions`` with NO ``-n`` in argv, so the
    name lives only in that registry.

    A session is adopted ONLY when (a) its registry ``cwd`` resolves inside a
    FLEET repo (the watch-set) AND (b) its ``name`` is an ACTIVE plan topic in
    that repo (a discovered ``plan/<topic>/`` DIRECTORY). Registry
    membership already proves it is a live Claude process, so no worker-command
    guard is needed. The mapping's ``tmux`` field is the ACTUAL session name
    holding the work (any name — a generic `livespec`, an operator-renamed one) —
    NOT necessarily the ``tmux_id`` the daemon would derive+spawn. A
    ``(repo, topic)`` already mapped is left untouched (no double-add).
    Returns the newly-adopted Tracks.

    Codex sessions are NOT in Claude's registry, but they ARE adopted through the
    SAME path: this method sums ``claude_sessions.map_named_sessions`` +
    ``codex_sessions.map_codex_sessions`` (below), both emitting the same
    ``(tmux, name, cwd)`` triple, so a live NAMED codex session is adopted exactly
    like a Claude one. Distinct from :meth:`auto_link`, which links only the
    derived ``tmux_id`` session (the bare topic, or ``<repo-slug>-<topic>`` on a
    cross-repo collision) the daemon itself launches.
    """
    active = _active_topics_by_repo(watch=watch)
    existing = _mapped_tmux_by_track(sup=sup)
    pane_pids = sup.tmux.pane_pid_sessions()
    # BOTH runtimes, through ONE path. `codex_sessions.map_codex_sessions` emits the
    # same `(tmux_session, name, cwd)` triple as its Claude twin precisely so adoption
    # never grows a parallel Codex branch that could drift. Codex sessions are absent
    # from Claude's registry, so without this they are invisible: the plan is
    # discovered and shows `unassigned` while a real session runs in its tmux
    # (maintainer-reported live 2026-07-17: rop-sweep-library-checks in
    # `livespec-dev-tooling`, rop-sweep-consumer-cleanup in `livespec3`).
    #
    # `Codex Companion Task: …` threads filter themselves out below: their names are
    # not active plan topics, so they fail the same test any non-topic name fails.
    mapped = _adoptable_live_sessions(sup=sup, pane_pids=pane_pids)
    profile_sources = _live_profile_sources(sup=sup, pane_pids=pane_pids)
    # Detect (repo, topic) claimed by MORE THAN ONE live session this tick. Re-pointing
    # such a track would FLIP-FLOP between the sessions' tmux ids every tick — two store
    # rewrites + two "re-pointed" log lines forever (review SF1) — since which one "wins"
    # is just `mapped` order. When ambiguous we skip the re-point entirely and leave the
    # mapping as-is (the identity gate + set-valued `claude_names_by_session` still classify
    # each pane correctly). Resolve repo the same way the loop does, so the counts match.
    live_keys: list[tuple[str, str]] = []
    for _session, name, cwd in mapped:
        r = next((r for r in watch if signals.path_in_repo(pane_current_path=cwd, repo=r)), None)
        if r is not None and name in active.get(r, set()):
            live_keys.append((r, name))
    ambiguous = {k for k, count in collections.Counter(live_keys).items() if count > 1}
    adopted: list[registry.Track] = []
    for session, name, cwd in mapped:
        repo = next((r for r in watch if signals.path_in_repo(pane_current_path=cwd, repo=r)), None)
        if repo is None:
            continue
        topic = name
        if signals.topic_reserved_for_supervisor(topic=topic) or topic not in active.get(
            repo, set()
        ):
            continue
        key = (registry.norm(repo=repo), topic)
        if key in existing:
            # Already mapped. RE-POINT if the live named session has MOVED to a
            # different tmux session than the store records (R2, 2026-07-18): generic
            # reused windows (`livespec1`…) get cycled across topics, so a frozen
            # binding would let an act target the wrong pane. The data is already in
            # `mapped`; rewrite the row's `tmux` and log it like an adoption. Guarded
            # so a steady-state tick (tmux unchanged) never touches the store, and
            # idempotent (`repoint_tmux` no-ops + returns False when unchanged). SKIP
            # when ambiguous (>1 live session for this track) so it cannot flip-flop.
            if (
                (repo, topic) not in ambiguous
                and existing[key] != session
                and registry.repoint_tmux(
                    repo=repo, topic=topic, new_tmux=session, store_path=sup.store_path
                )
            ):
                sup.log(message=f"re-pointed {repo}::{topic} tmux {existing[key]} → {session}")
                existing[key] = session
            continue
        track = registry.PlanTrack(
            topic=topic,
            repo=repo,
            tmux=session,
            epic=sup.mapping_epics.get(key) or registry.unresolved_plan_epic(topic=topic),
            model_profile=profile_for_adoption(
                sup=sup,
                source=profile_sources.get((session, topic)),
                repo=repo,
                session=session,
                topic=topic,
            ),
        )
        registry.append_mapping(track=track, store_path=sup.store_path, added_at=iso_now())
        existing[key] = session
        adopted.append(track)
        sup.log(message=f"adopted session {session} → {repo}::{topic}")
    return adopted


def sessions_dir(*, sup: Supervisor) -> str | os.PathLike[str]:
    """The Claude session-registry dir (injected override, else the real ``~/.claude``)."""
    return (
        sup.sessions_dir if sup.sessions_dir is not None else claude_sessions.default_sessions_dir()
    )
