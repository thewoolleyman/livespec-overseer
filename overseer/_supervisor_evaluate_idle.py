"""Post-busy idle branch group for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_ctx_stale
import _supervisor_idle
import _supervisor_launch
import _supervisor_liveness
import _supervisor_observe
import _supervisor_restart
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


def _missing_plan_epic_decision(*, request: IdleRequest, note: str | None) -> IdleDecision:
    next_note = _supervisor_liveness.append_note(
        note=note,
        extra=_supervisor_restart.missing_plan_epic_message(),
    )
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.target,
            message=_supervisor_restart.missing_plan_epic_message(),
            condition="restart-plan-epic-missing",
        )
    return IdleDecision(
        status="blocked:human",
        note=next_note,
        active_conditions={"blocked-human"},
        settled_streaming_progress=False,
    )


def _apply_uncertifiable_ready(
    *,
    status: str,
    note: str | None,
    active_conditions: set[str],
    uncertifiable_ready: tuple[str, set[str]] | None,
) -> tuple[str, str | None]:
    if uncertifiable_ready is None:
        return status, note
    ready_note, ready_conditions = uncertifiable_ready
    active_conditions.update(ready_conditions)
    # A surfaced certification failure is its own report-only state.  In
    # particular, do not let a low context percentage relabel a deterministic
    # identity mismatch as ordinary ``danger``: that reads as a missed ready
    # declaration and hides the UUIDs needed to resolve it safely.
    return "ready-uncertifiable", ready_note


def _idle_room_or_recovered(*, request: IdleRequest) -> str:
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
        return "idle"
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
    )


def _threshold_or_void_notice_decision(
    *, request: IdleRequest, note: str | None, active_conditions: set[str]
) -> IdleDecision:
    threshold_decision = _supervisor_threshold.threshold(
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
    status = threshold_decision.status
    active_conditions.update(threshold_decision.active_conditions)
    status, note = _apply_uncertifiable_ready(
        status=status,
        note=note,
        active_conditions=active_conditions,
        uncertifiable_ready=request.uncertifiable_ready,
    )
    return IdleDecision(
        status=status,
        note=note,
        active_conditions=active_conditions,
        settled_streaming_progress=False,
    )


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
        if _supervisor_restart.resume_prompt(track=request.track) is None:
            return _missing_plan_epic_decision(request=request, note=note)
        status = "restarting"
        if request.act:
            _supervisor_restart.do_restart(
                sup=request.sup,
                track=request.track,
                target=request.target,
                is_codex=request.obs.is_codex,
            )
    elif (
        request.obs.ctx_stale_age is not None
        and request.obs.stale_ctx is not None
        and request.obs.stale_ctx <= request.threshold
    ):
        status = "ctx-stale"
        active_conditions.add("ctx-stale")
        note = _supervisor_liveness.append_note(note=note, extra=request.ctx_stale_note)
        _supervisor_ctx_stale.ctx_stale(
            request=_supervisor_ctx_stale.CtxStaleRequest(
                sup=request.sup,
                track=request.track,
                session=request.session,
                pane=request.target,
                ctx_stale_age=request.obs.ctx_stale_age,
                stale_ctx=request.obs.stale_ctx,
                threshold=request.threshold,
                act=request.act,
            )
        )
    elif request.obs.eff_ctx is not None and request.obs.eff_ctx <= request.threshold:
        return _threshold_or_void_notice_decision(
            request=request, note=note, active_conditions=active_conditions
        )
    elif request.uncertifiable_ready is not None:
        status = "ready-uncertifiable"
        note, ready_conditions = request.uncertifiable_ready
        active_conditions.update(ready_conditions)
    else:
        status = _idle_room_or_recovered(request=request)
    return IdleDecision(
        status=status,
        note=note,
        active_conditions=active_conditions,
        settled_streaming_progress=False,
    )
