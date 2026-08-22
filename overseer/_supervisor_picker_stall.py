"""Interactive picker stall projection and attention promotion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_config
import _supervisor_liveness
import _supervisor_nudge
import _supervisor_progress
import registry
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "PickerStallDecision",
    "PickerStallRequest",
    "PickerStallView",
    "apply_picker_stall",
]


@dataclass(frozen=True, kw_only=True)
class PickerStallView:
    picker_open: bool
    stall_seconds: int


@dataclass(frozen=True, kw_only=True)
class PickerStallDecision:
    status: str
    note: str | None
    active_conditions: set[str]
    view: PickerStallView


@dataclass(frozen=True, kw_only=True)
class PickerStallRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def apply_picker_stall(*, request: PickerStallRequest) -> PickerStallDecision:
    picker_open = request.obs.gate
    stall_seconds = _supervisor_progress.blocked_human_stall_seconds(
        obs=request.obs, status=request.status, picker_open=picker_open
    )
    view = PickerStallView(picker_open=picker_open, stall_seconds=stall_seconds)
    if (
        request.status != "blocked:human"
        or not picker_open
        or stall_seconds < _supervisor_config.PICKER_STALL_AFTER
    ):
        return PickerStallDecision(
            status=request.status,
            note=request.note,
            active_conditions=request.active_conditions,
            view=view,
        )

    promoted_conditions = set(request.active_conditions)
    promoted_conditions.add("picker-stalled")
    promoted_note = _supervisor_liveness.append_note(
        note=request.note,
        extra=f"picker stalled {_supervisor_liveness.age_label(seconds=stall_seconds)}",
    )
    if request.act:
        promoted_conditions.update(
            _supervisor_liveness.surface_picker_stall_alert(
                sup=request.sup,
                track=request.track,
                session=request.session,
                pane=request.pane,
                stall_seconds=stall_seconds,
            )
        )
        if isinstance(request.track, registry.SupervisorSeat | registry.ForemanSeat):
            _supervisor_nudge.nudge_charter_authorized_picker_stall(
                sup=request.sup,
                track=request.track,
                target=request.pane,
                stall_seconds=stall_seconds,
                istate=request.obs.istate,
            )
    return PickerStallDecision(
        status="picker-stalled",
        note=promoted_note,
        active_conditions=promoted_conditions,
        view=view,
    )
