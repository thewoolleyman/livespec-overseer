"""Ready-declared restart branch for the idle evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_liveness
import _supervisor_restart
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["ReadyRestartDecision", "ReadyRestartRequest", "ready_restart_decision"]


@dataclass(frozen=True, kw_only=True)
class ReadyRestartDecision:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class ReadyRestartRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    target: str
    is_codex: bool
    note: str | None
    act: bool


def _missing_plan_epic_decision(
    *, request: ReadyRestartRequest, note: str | None
) -> ReadyRestartDecision:
    message = _supervisor_restart.missing_restart_epic_message(track=request.track)
    next_note = _supervisor_liveness.append_note(
        note=note,
        extra=message,
    )
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.target,
            message=message,
            condition="restart-plan-epic-missing",
        )
    return ReadyRestartDecision(
        status="blocked:human",
        note=next_note,
        active_conditions={"blocked-human"},
    )


def _track_ready_to_restart(*, request: ReadyRestartRequest) -> registry.Track | None:
    """The track to restart with, or None if it still has no usable epic.

    Tries the one-shot re-derive (overseer-vbmq) only after the track's CURRENT
    epic proves unusable — never speculatively — so the common case (epic
    already populated) costs nothing extra.
    """
    track = request.track
    if _supervisor_restart.resume_prompt(track=track) is not None:
        return track
    if not isinstance(track, registry.PlanTrack):
        return None
    track = _supervisor_restart.rederive_epic_if_stale(
        sup=request.sup, track=track, act=request.act
    )
    if _supervisor_restart.resume_prompt(track=track) is not None:
        return track
    return None


def ready_restart_decision(*, request: ReadyRestartRequest) -> ReadyRestartDecision:
    # The session DECLARED `ready`. This is the ONLY path to a restart — the
    # daemon never infers it (maintainer 2026-07-14). RUNTIME-DISPATCHED: for a
    # Codex track `_do_restart` routes to `codex resume <id>`, NEVER the claude
    # launch command — aiming `claude -n <topic>` at a codex pane would REPLACE
    # the codex session with a claude one and destroy it. That routing (not a
    # separate monitor-only refusal) is what preserves the one place a bug here is
    # destructive rather than merely wrong; the sabotage-verified guard test pins
    # it. A Codex track is now a full citizen (maintainer-declared 2026-07-17):
    # it is restarted on its own `ready` exactly like a Claude one.
    track = _track_ready_to_restart(request=request)
    if track is None:
        return _missing_plan_epic_decision(request=request, note=request.note)
    if request.act:
        _supervisor_restart.do_restart(
            sup=request.sup,
            track=track,
            target=request.target,
            is_codex=request.is_codex,
        )
    return ReadyRestartDecision(
        status="restarting",
        note=request.note,
        active_conditions=set(),
    )
