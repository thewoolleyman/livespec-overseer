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
from _supervisor_prompts import supervisor_handoff_path
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "clear_supervision_alerts",
    "live_session_outside_tmux",
    "no_managed_pane_row",
    "supervisor_running",
    "supervisor_session_of",
    "surface_supervision_offer",
]


def supervisor_session_of(*, sup: Supervisor, track: registry.Track) -> str:
    """The conventional attended supervisor tmux session for ``track``."""
    return f"{_supervisor_launch.session_of(sup=sup, track=track)}-supervisor"


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
        return True
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


def surface_supervision_offer(*, sup: Supervisor, track: registry.Track, act: bool) -> None:
    """Surface the supervision truth table without replacing the row's core status."""
    repo, topic = track.repo, track.topic
    session = _supervisor_launch.session_of(sup=sup, track=track)
    supervisor_session = supervisor_session_of(sup=sup, track=track)
    handoff_exists = supervisor_handoff_path(repo=repo, topic=topic).exists()
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


def no_managed_pane_row(*, sup: Supervisor, repo: str, topic: str) -> RowView:
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
    return RowView(topic=topic, repo=repo, tmux=None, ctx=None, status="session-gone")
