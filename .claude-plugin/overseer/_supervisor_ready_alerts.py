"""Report-only surfaces for ready declarations that cannot certify."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _supervisor_launch
import _supervisor_wrapup_select
import registry
import signals
from _supervisor_config import CONDITION_CONTINUITY_GAP
from _supervisor_liveness_time import (
    age_label,
    blocked_band_seconds,
    clear_alert_conditions,
)
from _supervisor_records import InjectState, Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "STRANDED_READY_NOTICE_AFTER",
    "uncertifiable_ready_surface",
]

STRANDED_READY_NOTICE_AFTER = 60 * 60


def reset_uncertifiable_ready_state(*, istate: InjectState) -> None:
    istate.uncertifiable_ready_mtime = None
    istate.uncertifiable_ready_entry_age_label = None
    istate.uncertifiable_ready_alerted_bands = set()
    istate.uncertifiable_ready_notice_mtime = None


def _must_surface_immediately(*, reason: str) -> bool:
    """Whether this certification failure identifies a changed live session.

    A generic missing or stale declaration gets a continuity grace: a session may
    finish its own tail shortly after declaring.  A changed session identity is
    different.  It is deterministic proof that the standing declaration cannot
    authorize this live pane, so hiding it behind that grace turns a safe hold
    into an indistinguishable ``danger`` row.
    """
    return reason.startswith(
        (
            "no supervision round open",
            "session identity differs from round-open identity",
            "session identity differs from observed identity",
            "ready declaration exceeded",
        )
    )


def uncertifiable_ready_surface(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    obs: Observation,
    act: bool,
) -> tuple[str, set[str]] | None:
    """Return the report-only surface for a `ready` that cannot certify, if due."""
    declared = obs.declared
    if declared is None or declared.token != signals.STATE_READY:
        reset_uncertifiable_ready_state(istate=obs.istate)
        return None
    if obs.ready_uncertifiable_reason is None:
        reset_uncertifiable_ready_state(istate=obs.istate)
        return None
    reason = obs.ready_uncertifiable_reason

    istate = obs.istate
    age = max(0.0, sup.now() - declared.mtime)
    if age < CONDITION_CONTINUITY_GAP and not _must_surface_immediately(reason=reason):
        return None

    active_conditions = {"ready-uncertifiable"}
    note = f"{age_label(seconds=age)}: ready cannot certify: {reason}"
    if not act:
        return note, active_conditions

    if istate.uncertifiable_ready_mtime != declared.mtime:
        clear_alert_conditions(sup=sup, repo=track.repo, topic=track.topic, conditions=frozenset())
        istate.uncertifiable_ready_mtime = declared.mtime
        istate.uncertifiable_ready_entry_age_label = age_label(seconds=age)
        istate.uncertifiable_ready_alerted_bands = set(blocked_band_seconds(age=age))
        istate.uncertifiable_ready_notice_mtime = None
    for band in blocked_band_seconds(age=age):
        active_conditions.add(f"ready-uncertifiable-age-{band}")

    alert_age = istate.uncertifiable_ready_entry_age_label or age_label(seconds=age)
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=pane,
        message=(
            f"ready cannot certify ({alert_age}): {reason} — "
            "restart held; clear the declaration and complete a newly delivered "
            "current-session round before declaring ready"
        ),
        condition="ready-uncertifiable",
    )
    new_bands = [
        band
        for band in blocked_band_seconds(age=age)
        if band not in istate.uncertifiable_ready_alerted_bands
    ]
    istate.uncertifiable_ready_alerted_bands.update(new_bands)
    for band in new_bands:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=pane,
            message=(
                f"ready cannot certify ({age_label(seconds=band)}): {reason} — "
                "restart held; clear the declaration and complete a newly delivered "
                "current-session round before declaring ready"
            ),
            condition=f"ready-uncertifiable-age-{band}",
        )
    _maybe_deliver_stranded_ready_notice(
        sup=sup,
        track=track,
        pane=pane,
        obs=obs,
        age=age,
        reason=reason,
    )
    return note, active_conditions


def _maybe_deliver_stranded_ready_notice(
    *,
    sup: Supervisor,
    track: registry.Track,
    pane: str,
    obs: Observation,
    age: float,
    reason: str,
) -> None:
    declared = cast("signals.TrackState", obs.declared)
    if age < STRANDED_READY_NOTICE_AFTER:
        return
    istate = obs.istate
    if istate.uncertifiable_ready_notice_mtime == declared.mtime:
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
        expect_codex=obs.is_codex,
    )
    if not sent:
        return
    istate.uncertifiable_ready_notice_mtime = declared.mtime
    sup.log(message=f"injected stranded-ready notice into {track.repo}::{track.topic}")
