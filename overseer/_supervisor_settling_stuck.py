"""Report-only attention for below-threshold panes stuck in settling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_config
import _supervisor_liveness
import _supervisor_observe
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "SETTLING_STUCK_CONDITION",
    "SETTLING_STUCK_STATUS",
    "SettlingStuckRequest",
    "SettlingStuckResult",
    "apply_settling_stuck_attention",
]

SETTLING_STUCK_CONDITION = "settling-stuck"
SETTLING_STUCK_STATUS = "settling-stuck"


@dataclass(frozen=True, kw_only=True)
class SettlingStuckResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class SettlingStuckRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def _unchanged(*, request: SettlingStuckRequest) -> SettlingStuckResult:
    return SettlingStuckResult(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )


def _condition_now(*, request: SettlingStuckRequest) -> bool:
    return (
        request.status == "settling"
        and not request.obs.idle
        and not request.obs.busy
        and not request.obs.gate
        and request.obs.eff_ctx is not None
        and request.obs.eff_ctx
        <= _supervisor_liveness.threshold_for(sup=request.sup, track=request.track)
    )


def _note(*, request: SettlingStuckRequest, age: float) -> str:
    threshold = _supervisor_liveness.threshold_for(sup=request.sup, track=request.track)
    return (
        f"settling {_supervisor_liveness.age_label(seconds=age)}: ctx "
        f"{request.obs.eff_ctx}% <= threshold {threshold}%; "
        "pane is not idle, busy, or gated"
    )


def _surface(*, request: SettlingStuckRequest) -> None:
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            "settling stuck "
            f"({_supervisor_liveness.age_label(seconds=_supervisor_config.SETTLING_STUCK_AFTER)}): "
            "below threshold and pane is not idle, busy, or gated - inspect that pane; "
            "report-only, no restart authorized; current streak age is in the row note"
        ),
        condition=SETTLING_STUCK_CONDITION,
    )


def apply_settling_stuck_attention(*, request: SettlingStuckRequest) -> SettlingStuckResult:
    condition_now = _condition_now(request=request)
    _supervisor_observe.advance_condition(
        episode=request.obs.istate.settling_episode,
        condition_now=condition_now,
        now=request.obs.observed_at,
    )
    if not condition_now or request.obs.istate.settling_episode.since is None:
        return _unchanged(request=request)

    age = max(0.0, request.obs.observed_at - request.obs.istate.settling_episode.since)
    if age <= _supervisor_config.SETTLING_STUCK_AFTER:
        return _unchanged(request=request)

    note = _supervisor_liveness.append_note(
        note=request.note, extra=_note(request=request, age=age)
    )
    if request.act:  # pragma: no branch
        _surface(request=request)
    return SettlingStuckResult(
        status=SETTLING_STUCK_STATUS,
        note=note,
        active_conditions={*request.active_conditions, SETTLING_STUCK_CONDITION},
    )
