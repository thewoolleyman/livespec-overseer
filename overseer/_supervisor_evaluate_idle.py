"""Post-busy idle branch group for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_evaluate_ctx_stale
import _supervisor_evaluate_restart
import _supervisor_evaluate_threshold
import _supervisor_idle
import _supervisor_launch
import _supervisor_observe
import _supervisor_round_recovery
import _supervisor_threshold
import registry
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["IdleDecision", "IdleRequest", "idle_decision"]


@dataclass(frozen=True, kw_only=True)
class IdleDecision:
    status: str
    note: str | None
    active_conditions: set[str]
    settled_streaming_progress: bool


@dataclass(frozen=True, kw_only=True)
class IdleRequest:
    sup: Supervisor
    track: registry.Track
    obs: Observation
    session: str
    target: str
    threshold: int
    ready: bool
    uncertifiable_ready: tuple[str, set[str]] | None
    ctx_stale_note: str | None
    note: str | None
    act: bool


def _idle_room_or_recovered(*, request: IdleRequest) -> tuple[str, bool]:
    if request.act and _supervisor_round_recovery.close_recovered_round(
        request=_supervisor_round_recovery.RecoveryRequest(
            sup=request.sup,
            track=request.track,
            obs=request.obs,
            session=request.session,
            target=request.target,
            threshold=request.threshold,
        )
    ):
        return "idle", True
    if request.act:
        _ = _supervisor_threshold.maybe_send_expiry_notice(
            request=_supervisor_threshold.ThresholdRequest(
                sup=request.sup,
                track=request.track,
                session=request.session,
                target=request.target,
                threshold=request.threshold,
                act=request.act,
                obs=request.obs,
            )
        )
    return _supervisor_idle.idle_room(
        request=_supervisor_idle.IdleRequest(
            sup=request.sup,
            track=request.track,
            target=request.target,
            topic=request.track.topic,
            eff_ctx=request.obs.eff_ctx,
            threshold=request.threshold,
            declared=request.obs.declared,
            claude_status=request.obs.claude_status,
            istate=request.obs.istate,
            act=request.act,
            is_codex=request.obs.is_codex,
        )
    ), False


def idle_decision(*, request: IdleRequest) -> IdleDecision:
    active_conditions: set[str] = set()
    note = request.note
    if not request.obs.idle:
        # Pane present but not a verified idle-input state and not busy —
        # a transient/settling capture. Wait; never act.
        status = "settling"
    elif request.act and not _supervisor_launch.pane_settled(
        sup=request.sup, target=request.target
    ):
        # One frame looks idle, but the pane is actively changing (streaming).
        return IdleDecision(
            status="working",
            note=note,
            active_conditions=active_conditions,
            settled_streaming_progress=True,
        )
    elif request.act and not _supervisor_observe.pane_is_managed(
        sup=request.sup,
        target=request.target,
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
    ):
        # TOCTOU re-check (Codex re-review #1): the identity gate ran at the top
        # of the tick, but capturing + the settle delay opened a window in which
        # the pane could have exited to a shell (or cd'd out of the repo). Re-
        # verify identity IMMEDIATELY before any act, so a wrap-up is never
        # pasted into — nor a respawn aimed at — a pane no longer proven ours.
        #
        # `settling` (a one-tick "wait and re-read"), NOT a status of its own: the
        # pane changed UNDER US mid-tick, which is exactly what settling means. The
        # act is suppressed either way, and the next tick re-enters at the top gate,
        # which classifies the settled truth (`session-gone` if it really has gone).
        status = "settling"
    elif request.ready:
        # The session DECLARED `ready`. This is the ONLY path to a restart — the
        # daemon never infers it (maintainer 2026-07-14). RUNTIME-DISPATCHED: for a
        # Codex track `_do_restart` routes to `codex resume <id>`, NEVER the claude
        # launch command — aiming `claude -n <topic>` at a codex pane would REPLACE
        # the codex session with a claude one and destroy it. That routing (not a
        # separate monitor-only refusal) is what preserves the one place a bug here is
        # destructive rather than merely wrong; the sabotage-verified guard test pins
        # it. A Codex track is now a full citizen (maintainer-declared 2026-07-17):
        # it is restarted on its own `ready` exactly like a Claude one.
        restart = _supervisor_evaluate_restart.ready_restart_decision(
            request=_supervisor_evaluate_restart.ReadyRestartRequest(
                sup=request.sup,
                track=request.track,
                session=request.session,
                target=request.target,
                is_codex=request.obs.is_codex,
                note=note,
                act=request.act,
            )
        )
        return IdleDecision(
            status=restart.status,
            note=restart.note,
            active_conditions=restart.active_conditions,
            settled_streaming_progress=False,
        )
    elif (
        request.obs.ctx_stale_age is not None
        and request.obs.stale_ctx is not None
        and request.obs.stale_ctx <= request.threshold
    ):
        ctx_stale = _supervisor_evaluate_ctx_stale.ctx_stale_decision(
            request=_supervisor_evaluate_ctx_stale.CtxStaleRequest(
                sup=request.sup,
                track=request.track,
                session=request.session,
                target=request.target,
                ctx_stale_age=request.obs.ctx_stale_age,
                stale_ctx=request.obs.stale_ctx,
                threshold=request.threshold,
                ctx_stale_note=request.ctx_stale_note,
                note=note,
                act=request.act,
            )
        )
        status = ctx_stale.status
        note = ctx_stale.note
        active_conditions.update(ctx_stale.active_conditions)
    elif request.obs.eff_ctx is not None and request.obs.eff_ctx <= request.threshold:
        threshold = _supervisor_evaluate_threshold.idle_threshold_decision(
            request=_supervisor_evaluate_threshold.IdleThresholdRequest(
                sup=request.sup,
                track=request.track,
                obs=request.obs,
                session=request.session,
                target=request.target,
                threshold=request.threshold,
                uncertifiable_ready=request.uncertifiable_ready,
                note=note,
                act=request.act,
            )
        )
        return IdleDecision(
            status=threshold.status,
            note=threshold.note,
            active_conditions=threshold.active_conditions,
            settled_streaming_progress=False,
        )
    elif request.uncertifiable_ready is not None:
        status = "ready-uncertifiable"
        note, ready_conditions = request.uncertifiable_ready
        active_conditions.update(ready_conditions)
    else:
        status, settled_streaming_progress = _idle_room_or_recovered(request=request)
        return IdleDecision(
            status=status,
            note=note,
            active_conditions=active_conditions,
            settled_streaming_progress=settled_streaming_progress,
        )
    return IdleDecision(
        status=status,
        note=note,
        active_conditions=active_conditions,
        settled_streaming_progress=False,
    )
