"""Foreman self-restart for old uncertifiable ready declarations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_restart
import foreman_stop_state
import registry
from _supervisor_liveness_time import age_label

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "FOREMAN_SELF_RESTART_CONDITION",
    "FOREMAN_SELF_RESTART_FLOOR_HOURS",
    "maybe_self_restart_foreman",
]

FOREMAN_SELF_RESTART_FLOOR_HOURS = 1
FOREMAN_SELF_RESTART_FLOOR_SECONDS = FOREMAN_SELF_RESTART_FLOOR_HOURS * 3600.0
FOREMAN_SELF_RESTART_REASON = "daemon failed to act within 1h"
FOREMAN_SELF_RESTART_CONDITION = "foreman-self-restart"
FOREMAN_SELF_RESTART_HELD_CONDITION = "foreman-self-restart-held"
FOREMAN_SELF_RESTART_CAPPED_CONDITION = "foreman-self-restart-capped"
# This is intentionally a separate attention condition rather than a new generic
# blocked-age band: the ratified floor applies only to foreman seats carrying
# uncertifiable `ready`, while blocked-age bands are shared report-only liveness.


def _alert(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    message: str,
    condition: str,
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=pane,
        message=message,
        condition=condition,
    )


def _held_reason(*, repo: str) -> str | None:
    stop_state = foreman_stop_state.read_foreman_stop_state(repo=repo)
    if stop_state is None or stop_state.state != foreman_stop_state.FOREMAN_STOP_HELD:
        return None
    return stop_state.reason


def _refuse_held(
    *, sup: Supervisor, track: registry.Track, session: str, pane: str, reason: str
) -> None:
    message = f"foreman self-restart refused because foreman loop is held: {reason}"
    sup.log(message=message, repo=track.repo, topic=track.topic)
    _alert(
        sup=sup,
        track=track,
        session=session,
        pane=pane,
        message=message,
        condition=FOREMAN_SELF_RESTART_HELD_CONDITION,
    )


def maybe_self_restart_foreman(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    obs: Observation,
    age: float,
) -> str | None:
    """Respawn a stranded foreman once its own `ready` has aged past the floor.

    This is deliberately narrower than the normal restart path. It still requires
    a filesystem `ready` declaration; it only changes who acts when that declaration
    cannot certify because the daemon failed to consume it within the named hour.
    The once-per-lineage cap is durable in the stamps sidecar, not in the
    declaration-scoped in-memory band state that resets when the ready file changes.
    """
    _ = obs
    if not isinstance(track, registry.ForemanSeat):
        return None
    if age < FOREMAN_SELF_RESTART_FLOOR_SECONDS:
        return None
    persisted = registry.read_foreman_self_restart(
        repo=track.repo,
        topic=track.topic,
        stamp_path=sup.stamp_path,
    )
    if persisted.attempted:
        message = "foreman self-restart already used for this session lineage"
        sup.log(message=message, repo=track.repo, topic=track.topic)
        _alert(
            sup=sup,
            track=track,
            session=session,
            pane=pane,
            message=message,
            condition=FOREMAN_SELF_RESTART_CAPPED_CONDITION,
        )
        return FOREMAN_SELF_RESTART_CAPPED_CONDITION
    hold_reason = _held_reason(repo=track.repo)
    if hold_reason is not None:
        _refuse_held(
            sup=sup,
            track=track,
            session=session,
            pane=pane,
            reason=hold_reason,
        )
        return FOREMAN_SELF_RESTART_HELD_CONDITION
    message = (
        f"{FOREMAN_SELF_RESTART_REASON}; self-restarting foreman after " f"{age_label(seconds=age)}"
    )
    registry.record_foreman_self_restart(
        repo=track.repo,
        topic=track.topic,
        reason=FOREMAN_SELF_RESTART_REASON,
        stamp_path=sup.stamp_path,
    )
    sup.log(message=message, repo=track.repo, topic=track.topic)
    _alert(
        sup=sup,
        track=track,
        session=session,
        pane=pane,
        message=message,
        condition=FOREMAN_SELF_RESTART_CONDITION,
    )
    _supervisor_restart.do_restart(sup=sup, track=track, target=pane)
    registry.record_foreman_self_restart(
        repo=track.repo,
        topic=track.topic,
        reason=FOREMAN_SELF_RESTART_REASON,
        stamp_path=sup.stamp_path,
    )
    return FOREMAN_SELF_RESTART_CONDITION
