"""Delivery of the report-only stranded-ready notice into the seat's own pane."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _supervisor_launch
import _supervisor_observe
import _supervisor_wrapup_select
import registry
import signals
from _supervisor_config import track_key
from _supervisor_liveness_time import age_label
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "STRANDED_READY_NOTICE_AFTER",
    "maybe_deliver_stranded_ready_notice",
]

STRANDED_READY_NOTICE_AFTER = 60 * 60


def _declaration_signature(*, obs: Observation) -> tuple[str | None, str | None, float | None]:
    return (
        getattr(obs.declared, "token", None),
        getattr(obs.declared, "detail", None),
        getattr(obs.declared, "mtime", None),
    )


def _ready_notice_inputs_changed(*, settled: Observation, fresh: Observation) -> bool:
    return (
        fresh.capture != settled.capture
        or fresh.is_codex != settled.is_codex
        or fresh.busy != settled.busy
        or fresh.gate != settled.gate
        or fresh.idle != settled.idle
        or fresh.codex_fallback != settled.codex_fallback
        or fresh.claude_status != settled.claude_status
        or fresh.ready != settled.ready
        or fresh.malformed != settled.malformed
        or fresh.blocked != settled.blocked
        or fresh.acked != settled.acked
        or fresh.ready_uncertifiable_reason != settled.ready_uncertifiable_reason
        or _declaration_signature(obs=fresh) != _declaration_signature(obs=settled)
    )


def _fresh_stranded_ready_notice_observation(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    obs: Observation,
) -> Observation | None:
    """Re-read every pane-write authorization input immediately before acting."""
    if not (
        obs.idle
        and not obs.gate
        and not obs.busy
        and obs.declared is not None
        and obs.declared.token == signals.STATE_READY
    ):
        return None
    if not _supervisor_observe.pane_is_managed(
        sup=sup,
        target=pane,
        repo=track.repo,
        topic=track.topic,
        session=session,
    ):
        return None
    if not _supervisor_launch.pane_settled(sup=sup, target=pane):
        return None
    fresh = _supervisor_observe.observe(
        sup=sup,
        track=track,
        session=session,
        target=pane,
        key=track_key(repo=track.repo, topic=track.topic),
    )
    if _ready_notice_inputs_changed(settled=obs, fresh=fresh):
        return None
    return fresh


def maybe_deliver_stranded_ready_notice(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: tuple[str, str],
    obs: Observation,
    age: float,
    reason: str,
) -> None:
    session, pane = target
    declared = cast("signals.TrackState", obs.declared)
    if age < STRANDED_READY_NOTICE_AFTER:
        return
    istate = obs.istate
    if istate.uncertifiable_ready_notice_mtime == declared.mtime:
        return
    fresh = _fresh_stranded_ready_notice_observation(
        sup=sup, track=track, session=session, pane=pane, obs=obs
    )
    if fresh is None:
        return
    text = _supervisor_wrapup_select.select_stranded_ready_notice(
        track=track,
        age=age_label(seconds=age),
        reason=reason,
    )
    sent = _supervisor_launch.submit_prompt(
        sup=sup,
        target=pane,
        text=text,
        expect_codex=fresh.is_codex,
    )
    if not sent:
        return
    istate.uncertifiable_ready_notice_mtime = declared.mtime
    sup.log(message=f"injected stranded-ready notice into {track.repo}::{track.topic}")
