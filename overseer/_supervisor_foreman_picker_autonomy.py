"""Report-only attention for foreman pickers under full autonomy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_liveness
import foreman_runtime_identity
import foreman_valve_policy
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "FOREMAN_PICKER_FULL_AUTONOMY_STATUS",
    "ForemanPickerAutonomyRequest",
    "ForemanPickerAutonomyResult",
    "apply_foreman_picker_autonomy_attention",
]

FOREMAN_PICKER_FULL_AUTONOMY_STATUS = "foreman-picker-under-full-autonomy"


@dataclass(frozen=True, kw_only=True)
class ForemanPickerAutonomyResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class ForemanPickerAutonomyRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def _unchanged(*, request: ForemanPickerAutonomyRequest) -> ForemanPickerAutonomyResult:
    return ForemanPickerAutonomyResult(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )


def _is_canonical_foreman(*, track: registry.Track) -> bool:
    return isinstance(
        track, registry.ForemanSeat
    ) and track.topic == foreman_runtime_identity.canonical_session_name(repo=Path(track.repo))


def apply_foreman_picker_autonomy_attention(
    *, request: ForemanPickerAutonomyRequest
) -> ForemanPickerAutonomyResult:
    if not request.obs.gate or not _is_canonical_foreman(track=request.track):
        return _unchanged(request=request)
    resolved = foreman_valve_policy.effective_full_autonomy(repo=Path(request.track.repo))
    if resolved.get("full_autonomy") is not True:
        return _unchanged(request=request)

    note = _supervisor_liveness.append_note(
        note=request.note,
        extra=(
            "foreman picker open while full_autonomy=true; "
            "report-only, no picker answer authorized"
        ),
    )
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                "foreman picker is open while full_autonomy=true - inspect that pane; "
                "report-only, no picker answer authorized"
            ),
            condition=FOREMAN_PICKER_FULL_AUTONOMY_STATUS,
        )
    return ForemanPickerAutonomyResult(
        status=FOREMAN_PICKER_FULL_AUTONOMY_STATUS,
        note=note,
        active_conditions={
            *request.active_conditions,
            FOREMAN_PICKER_FULL_AUTONOMY_STATUS,
        },
    )
