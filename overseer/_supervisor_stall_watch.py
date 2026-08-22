"""Report-only attention for working panes whose visible bytes stop changing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_final_ruling_attention
import _supervisor_foreman_picker_autonomy
import _supervisor_pane_still
import _supervisor_parked_delivery
import _supervisor_picker_stall
import _supervisor_settling_stuck
import _supervisor_working_low_context
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "EvaluationMonitorRequest",
    "EvaluationMonitorResult",
    "StallWatchRequest",
    "StallWatchResult",
    "apply_evaluation_monitors",
    "apply_stall_watch",
]

PANE_STILL_STATUS = _supervisor_pane_still.PANE_STILL_STATUS
WATCH_TARGET_GONE_STATUS = _supervisor_pane_still.WATCH_TARGET_GONE_STATUS
StallWatchRequest = _supervisor_pane_still.StallWatchRequest
StallWatchResult = _supervisor_pane_still.StallWatchResult
apply_stall_watch = _supervisor_pane_still.apply_stall_watch


@dataclass(frozen=True, kw_only=True)
class EvaluationMonitorResult:
    status: str
    note: str | None
    active_conditions: set[str]
    picker_stall: _supervisor_picker_stall.PickerStallDecision


@dataclass(frozen=True, kw_only=True)
class EvaluationMonitorRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def apply_evaluation_monitors(*, request: EvaluationMonitorRequest) -> EvaluationMonitorResult:
    picker_stall = _supervisor_picker_stall.apply_picker_stall(
        request=_supervisor_picker_stall.PickerStallRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            status=request.status,
            note=request.note,
            obs=request.obs,
            active_conditions=request.active_conditions,
            act=request.act,
        )
    )
    parked_delivery = _supervisor_parked_delivery.apply_parked_delivery_attention(
        request=_supervisor_parked_delivery.ParkedDeliveryRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            status=picker_stall.status,
            note=picker_stall.note,
            obs=request.obs,
            active_conditions=picker_stall.active_conditions,
            act=request.act,
        )
    )
    foreman_picker = _supervisor_foreman_picker_autonomy.apply_foreman_picker_autonomy_attention(
        request=_supervisor_foreman_picker_autonomy.ForemanPickerAutonomyRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            status=parked_delivery.status,
            note=parked_delivery.note,
            obs=request.obs,
            active_conditions=parked_delivery.active_conditions,
            act=request.act,
        )
    )
    final_ruling = _supervisor_final_ruling_attention.apply_final_ruling_attention(
        request=_supervisor_final_ruling_attention.FinalRulingRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            status=foreman_picker.status,
            note=foreman_picker.note,
            obs=request.obs,
            active_conditions=foreman_picker.active_conditions,
            act=request.act,
        )
    )
    low_context = _supervisor_working_low_context.apply_working_low_context_attention(
        request=_supervisor_working_low_context.WorkingLowContextRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            status=final_ruling.status,
            note=final_ruling.note,
            obs=request.obs,
            active_conditions=final_ruling.active_conditions,
            act=request.act,
        )
    )
    settling_stuck = _supervisor_settling_stuck.apply_settling_stuck_attention(
        request=_supervisor_settling_stuck.SettlingStuckRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            status=low_context.status,
            note=low_context.note,
            obs=request.obs,
            active_conditions=low_context.active_conditions,
            act=request.act,
        )
    )
    stall_watch = apply_stall_watch(
        request=StallWatchRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            status=settling_stuck.status,
            note=settling_stuck.note,
            obs=request.obs,
            active_conditions=settling_stuck.active_conditions,
            act=request.act,
        )
    )
    return EvaluationMonitorResult(
        status=stall_watch.status,
        note=stall_watch.note,
        active_conditions=stall_watch.active_conditions,
        picker_stall=picker_stall,
    )
