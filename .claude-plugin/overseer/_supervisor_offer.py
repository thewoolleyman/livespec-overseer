"""_supervisor_offer — the supervision offer and the no-managed-pane surfaces.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Two operator-facing surfaces that answer questions about a track the daemon
canNOT drive: whether a plan has a SUPERVISOR session it could be handed to, and
what to report when the mapped tmux pane is gone but the work may not be.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_discovery
import _supervisor_launch
import claude_sessions
import registry
import signals
from _supervisor_config import SUPERVISION_CONDITIONS, track_key
from _supervisor_prompts import supervisor_epic_path, supervisor_handoff_path
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "clear_supervision_alerts",
    "live_session_in_mapped_tmux",
    "live_session_outside_tmux",
    "no_managed_pane_row",
    "supervisor_running",
    "supervisor_session_of",
    "surface_supervision_offer",
]


def supervisor_session_of(*, sup: Supervisor, track: registry.Track) -> str:
    """The conventional attended supervisor tmux session for ``track``.

    Pair naming is derived from the worker's PLAN TOPIC, not the possibly generic
    tmux session currently hosting that worker.
    """
    worker_session = registry.tmux_id(
        repo=track.repo, topic=track.topic, colliding=sup.colliding_topics
    )
    return signals.supervisor_entity_topic(topic=worker_session)


def supervisor_running(*, sup: Supervisor, session: str, repo: str) -> bool:
    """True iff the derived supervisor session holds a live agent process in ``repo``.

    A tmux session NAME is not liveness. Surface B must still fire when a dead shell is
    left behind in ``<tracked>-supervisor``, so this checks live pane evidence: a
    Claude-like pane process in the repo, or a Codex-like pane process joined to a live
    Codex rollout in the repo.
    """
    if not sup.tmux.session_exists(session=session):
        return False
    target = sup.tmux.pane_id(session=session)
    if target is None:
        return False
    command = sup.tmux.pane_current_command(session=target)
    cwd = sup.tmux.pane_current_path(session=target)
    if signals.pane_is_claude(pane_current_command=command) and signals.path_in_repo(
        pane_current_path=cwd, repo=repo
    ):
        names = sup.claude_names_by_session.get(session)
        if names is None or session in names:
            return True
        return signals.topic_reserved_for_supervisor(topic=session)
    if not signals.pane_is_codex(pane_current_command=command):
        return False
    return any(
        tmux == session and signals.path_in_repo(pane_current_path=live.cwd, repo=repo)
        for (tmux, _name), live in sup.live_codex.items()
    )


def clear_supervision_alerts(*, sup: Supervisor, repo: str, topic: str) -> None:
    """Re-arm supervision-offer alerts once the supervision truth table is healthy."""
    prefix = track_key(repo=repo, topic=topic)
    sup.alerted = {
        key: value
        for key, value in sup.alerted.items()
        if key[:2] != prefix or key[2] not in SUPERVISION_CONDITIONS
    }


def _migrated_supervisor_handoff_exists(*, track: registry.Track) -> bool:
    """Return whether the migrated ledger-backed binder exists."""
    return supervisor_epic_path(repo=track.repo, topic=track.topic).exists()


def surface_supervision_offer(*, sup: Supervisor, track: registry.Track, act: bool) -> None:
    """Surface the supervision truth table without replacing the row's core status."""
    repo, topic = track.repo, track.topic
    session = _supervisor_launch.session_of(sup=sup, track=track)
    supervisor_session = supervisor_session_of(sup=sup, track=track)
    handoff_exists = supervisor_handoff_path(
        repo=repo, topic=topic
    ).exists() or _migrated_supervisor_handoff_exists(track=track)
    running = supervisor_running(sup=sup, session=supervisor_session, repo=repo)
    if handoff_exists and running:
        if act:
            clear_supervision_alerts(sup=sup, repo=repo, topic=topic)
        return
    if handoff_exists:
        message = (
            "supervisor handoff exists but no supervisor is running — "
            f"start tmux session '{supervisor_session}'"
        )
        condition = "supervisor-missing"
    elif running:
        message = (
            "supervision is running but has no durable prompt — capture it with "
            "/livespec-overseer:supervise-plan"
        )
        condition = "supervision-capture-offer"
    else:
        message = (
            "no supervisor handoff and no supervisor is running — run "
            "/livespec-overseer:supervise-plan for this live track"
        )
        condition = "supervision-offer"
    if act:
        sup.alert(
            repo=repo,
            topic=topic,
            session=session,
            pane=sup.tmux.pane_id(session=session),
            message=message,
            condition=condition,
        )


# Claude marks an AUTO-derived display name this way; an explicit `-n <topic>`
# launch leaves it unset. See :func:`live_session_in_mapped_tmux`.
_DERIVED_NAME_SOURCE = "derived"


def live_session_in_mapped_tmux(
    *, sup: Supervisor, repo: str, session: str
) -> claude_sessions.ClaudeSession | None:
    """A live registry session in ``repo`` that resolves to the MAPPED ``session``.

    The mirror of :func:`live_session_outside_tmux`, and the reason `overseer-j1r`
    could report a healthy track as lost. That helper — and the identity gate above
    it — both key on ``live.name == topic``, so a name MISMATCH could not reach the
    informational ``live-outside-tmux``: it degraded straight past it to
    ``session-gone``, the only red status. The softener could only soften the cases
    that had already matched by name, which are exactly the cases that did not need
    softening.

    So this deliberately does NOT look at the name. It answers a different, weaker,
    and here more useful question: *is a live agent for this repo actually sitting in
    the tmux session we mapped?* A manually-started Claude DERIVES its registry name
    from the repo directory (``livespec-overseer-01``, ``nameSource: derived``) rather
    than receiving ``-n <topic>`` as a daemon-spawned one does, so its name never
    equals the topic however healthy it is (measured 2026-07-28: pid 3057142 alive in
    ``codex-parity-and-rollout-safety`` while the row read ``session-gone``).

    **This is a REPORTING softener only and must never become an ACT gate.** The
    identity gate (:func:`_supervisor_observe.pane_is_managed`, R2/SF5) is unchanged
    and still rejects this pane, so nothing is captured, injected, pasted or
    respawned into it — that protection is what stops a reused window taking another
    topic's wrap-up and then a ``ready`` respawn-KILLING it. All that changes is what
    the operator is TOLD. Widening this into the gate would reintroduce that bug.

    **``name_source == "derived"`` is REQUIRED, and it is the whole reason this is
    safe.** A name mismatch has TWO causes that look identical by name: our own track
    started by hand and AUTO-named (``repo-01``), or a genuinely different topic's
    session sitting in a reused window (R2/SF5's ``beta``). Softening both would tell
    the operator to rename a window that another live track is using — advice that
    would hijack it. Claude marks only the first kind ``nameSource: derived``, so
    restricting to it keeps the deliberate-name case reporting the truthful
    ``session-gone`` (pinned by
    ``test_claude_name_gate_is_wired_end_to_end_through_the_registry`` and by this
    module's own explicitly-named control).
    """
    pane_pids = sup.tmux.pane_pid_sessions()
    for live in claude_sessions.read_live_sessions(
        sessions_dir=_supervisor_discovery.sessions_dir(sup=sup), starttime_of=sup.starttime_of
    ):
        if live.name_source != _DERIVED_NAME_SOURCE:
            continue
        if not signals.path_in_repo(pane_current_path=live.cwd, repo=repo):
            continue
        if (
            claude_sessions.resolve_tmux_session(
                pid=live.pid, pane_pid_to_session=pane_pids, ppid_of=sup.ppid_of
            )
            == session
        ):
            return live
    return None


def live_session_outside_tmux(
    *, sup: Supervisor, repo: str, topic: str
) -> claude_sessions.ClaudeSession | None:
    """The live Claude registry session for ``(repo, topic)`` running OUTSIDE any
    tmux pane, or None.

    Separates a genuinely gone track from one whose mapped tmux session died while a
    Claude session for the same plan kept working in a NON-tmux terminal (e.g. a bare
    SSH shell). It reads the SAME registry ``adopt_sessions`` uses
    (:func:`claude_sessions.read_live_sessions` — every live named session, tmux or
    not), matches a session whose ``name`` is the topic and whose ``cwd`` is in the
    repo, and returns it ONLY when it does not resolve to any tmux pane
    (:func:`claude_sessions.resolve_tmux_session` is None). A session that resolves to
    a DIFFERENT tmux session is deliberately NOT returned — that is a re-mapping
    concern, not an out-of-tmux one. Such an out-of-tmux session is alive and doing
    work but UNMANAGEABLE by the daemon (no pane to capture / inject / respawn), so
    ``evaluate`` reports it as the informational ``live-outside-tmux`` rather than the
    alarming ``session-gone``.
    """
    pane_pids = sup.tmux.pane_pid_sessions()
    for live in claude_sessions.read_live_sessions(
        sessions_dir=_supervisor_discovery.sessions_dir(sup=sup), starttime_of=sup.starttime_of
    ):
        if live.name != topic or not signals.path_in_repo(pane_current_path=live.cwd, repo=repo):
            continue
        if (
            claude_sessions.resolve_tmux_session(
                pid=live.pid, pane_pid_to_session=pane_pids, ppid_of=sup.ppid_of
            )
            is None
        ):
            return live
    return None


def no_managed_pane_row(*, sup: Supervisor, track: registry.Track, session: str) -> RowView:
    """The row for a track with NO live managed pane: ``live-outside-tmux`` or ``session-gone``.

    The single home for "this track has no pane we can drive". Reached THREE ways —
    the mapped tmux session is gone; or it survives but its session exited to a bare
    shell; or the pane is a genuinely FOREIGN one (fails the identity gate) — all of
    which must answer identically: they are the same fact about the track (no pane to
    drive), and only the tmux housekeeping differs. Keeping one path also keeps the
    live-outside-tmux fallback from being wired into just one of them (it was, and
    the shell case reported a live session as the now-deleted ``not-claude``).

    A Claude for the same plan may still be running in a NON-tmux terminal (a bare
    SSH shell): alive and working, but unmanageable by this tmux-only daemon (no
    pane to capture / inject / respawn). That is the informational
    ``live-outside-tmux``, NOT the alarming ``session-gone`` — the operator should
    not be told finished-looking work was lost when it is merely out of reach.

    **Both rows report ``tmux=None``, and that is the point of the helper**
    (maintainer-declared 2026-07-16: "it shouldn't display the session name; the
    session doesn't exist in that panel anymore"). The ``tmux`` cell means *the tmux
    session HOLDING this track* — an assertion about a live session, not a record of
    the mapping. Every row reaching here has no session in that tmux session: it is
    gone outright, or it survives holding only a bare shell, or the Claude is alive
    somewhere outside tmux entirely. Naming it anyway rendered a live-looking
    ``livespec1`` for a track whose session had exited — the mapping is still in the
    store, and ``session-gone`` already says "this WAS mapped and is now dead", so
    nothing is lost by leaving the cell empty. ``alert`` degrades on its own
    (``no live tmux session``, no jump command — there is nowhere to jump).

    (The former ``not-claude`` status — which named a foreign pane's session — was
    DELETED, 2026-07-17; a foreign pane now routes here like any other no-managed-pane
    case and reports ``tmux=None``. The identity gate itself is unchanged and still
    governs every act.)
    """
    repo, topic = track.repo, track.topic
    live = live_session_outside_tmux(sup=sup, repo=repo, topic=topic)
    if live is not None:
        note = (
            f"live Claude session (pid {live.pid}) running OUTSIDE tmux — "
            f"daemon cannot manage it"
        )
        if live.status:
            note += f"; self-reported status {live.status}"
        return RowView(
            topic=topic,
            repo=repo,
            tmux=None,
            ctx=None,
            status="live-outside-tmux",
            note=note,
        )
    unmanaged = live_session_in_mapped_tmux(sup=sup, repo=repo, session=session)
    if unmanaged is not None:
        note = (
            f"live agent (pid {unmanaged.pid}) in tmux session {session}, but its "
            f"registry name {unmanaged.name!r} is not the topic — daemon cannot manage "
            f"it; rename the session to {topic!r} to adopt it"
        )
        return RowView(
            topic=topic,
            repo=repo,
            tmux=None,
            ctx=None,
            status="live-name-mismatch",
            note=note,
        )
    declared = signals.read_state(repo=repo, topic=topic)
    if declared is not None and declared.token == signals.STATE_WINDING_DOWN:
        # `overseer-mkx`. The session ANNOUNCED it was wrapping up and is now gone —
        # an orderly teardown, not a loss. Reporting it as `session-gone` (the only
        # red status) made a completed track indistinguishable from one that died
        # mid-work, and it stayed in `NEEDS YOU` for as long as the plan directory
        # existed: 327 minutes, in the sighting that filed this.
        #
        # The discriminator was always on disk and simply unread. A track that dies
        # WHILE WORKING has declared nothing, so it still reports `session-gone`;
        # so does one that vanished while `blocked` (it was waiting, not finishing)
        # or holding a `ready` (an unfinished round). Only the wind-down
        # announcement is treated as an ending.
        #
        # THE TRADE, stated rather than hidden: a session that declared
        # `winding-down` and then genuinely CRASHED now reads as an orderly
        # wind-down. That distinction is deliberately given up — the declaration
        # means the session had already reached a point it called safe — to keep
        # the alarm sharp for the case that matters most, a track dying mid-work.
        #
        # This does NOT foreclose `overseer-mkx`'s other two options: a teardown
        # path that clears the file, and a terminal state token, both remain open
        # and would compose with this. It is the one that needs no change to the
        # declaration vocabulary, which is the cardinal contract.
        return RowView(
            topic=topic,
            repo=repo,
            tmux=None,
            ctx=None,
            status="wound-down",
            note="declared the wind-down and its session is gone — an orderly teardown",
        )
    return RowView(topic=topic, repo=repo, tmux=None, ctx=None, status="session-gone")
