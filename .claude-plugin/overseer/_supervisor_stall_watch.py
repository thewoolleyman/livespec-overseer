"""Report-only attention for working panes whose visible bytes stop changing."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi.3

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_liveness
import _supervisor_parked_delivery
import _supervisor_picker_stall
import _supervisor_snapshot
import _supervisor_working_low_context
import registry
from _supervisor_config import PANE_STILL_AFTER
from _supervisor_view import MAX_REASON_IN_ALERT, elide

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

PANE_STILL_STATUS = "pane-still"
WATCH_TARGET_GONE_STATUS = "watch-target-gone"
_PANE_STILL_CONDITION = "pane-still"
_WATCH_TARGET_GONE_CONDITION = "watch-target-gone"
_REQUIRED_DUE_OBSERVATIONS = 2


@dataclass(frozen=True, kw_only=True)
class StallWatchResult:
    status: str
    note: str | None
    active_conditions: set[str]


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


@dataclass(frozen=True, kw_only=True)
class StallWatchRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def _status_daemon_instance_id(*, sup: Supervisor) -> str:
    if sup.status_path is None and sup.status_snapshot_path is None:
        return sup.daemon_instance_id
    path = sup.status_path if sup.status_path is not None else sup.status_snapshot_path
    read = _supervisor_snapshot.read_status_snapshot(
        path=path or _supervisor_snapshot.DEFAULT_STATUS_PATH
    )
    if read is None:
        return sup.daemon_instance_id
    return str(read.document.get("daemon_instance_id") or sup.daemon_instance_id)


def _capture_hash(*, capture: str) -> str:
    return hashlib.sha256(capture.encode("utf-8")).hexdigest()


def _reset_capture_watch(*, request: StallWatchRequest) -> None:
    state = request.obs.istate
    state.stall_watch_capture_hash = _capture_hash(capture=request.obs.capture)
    state.stall_watch_capture_since = request.obs.observed_at
    state.stall_watch_due_observations = 0


def _resolve_watch_target(*, request: StallWatchRequest) -> str | None:
    state = request.obs.istate
    daemon_instance_id = _status_daemon_instance_id(sup=request.sup)
    if state.stall_watch_daemon_instance_id is None:
        state.stall_watch_daemon_instance_id = daemon_instance_id
        state.stall_watch_pane = request.pane
        return request.pane
    if state.stall_watch_daemon_instance_id == daemon_instance_id:
        if state.stall_watch_pane is None:
            state.stall_watch_pane = request.pane
        return state.stall_watch_pane

    # overseer-7nb4sk: after a daemon bounce, re-key the report-only watch from
    # the mapped tmux SESSION identity. Live Claude pane titles can be activity
    # prefixed or task-summary drifted, so they are not a reliable identity.
    resolved = request.sup.tmux.pane_id(session=request.session)
    state.stall_watch_daemon_instance_id = daemon_instance_id
    state.stall_watch_pane = resolved
    _reset_capture_watch(request=request)
    return resolved


def _watch_target_gone(*, request: StallWatchRequest) -> StallWatchResult:
    note = (
        "stall watch target missing after daemon bounce; re-resolve by tmux session identity failed"
    )
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=f"{note} - inspect the live pane before trusting any monitor",
            condition=_WATCH_TARGET_GONE_CONDITION,
        )
    return StallWatchResult(
        status=WATCH_TARGET_GONE_STATUS,
        note=note,
        active_conditions={*request.active_conditions, _WATCH_TARGET_GONE_CONDITION},
    )


def _pane_still(*, request: StallWatchRequest, age: float) -> StallWatchResult:
    note = f"working pane unchanged for {_supervisor_liveness.age_label(seconds=age)}"
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                f"{elide(text=note, limit=MAX_REASON_IN_ALERT)} - capture and "
                "re-classify the pane; report-only, no restart authorized"
            ),
            condition=_PANE_STILL_CONDITION,
        )
    return StallWatchResult(
        status=PANE_STILL_STATUS,
        note=note,
        active_conditions={*request.active_conditions, _PANE_STILL_CONDITION},
    )


def apply_stall_watch(*, request: StallWatchRequest) -> StallWatchResult:
    state = request.obs.istate
    if _resolve_watch_target(request=request) is None:
        return _watch_target_gone(request=request)
    if (
        request.status != "working"
        or request.obs.claude_status == "shell"
        or request.obs.codex_fallback
        or request.obs.eff_ctx is None
        or request.obs.eff_ctx
        <= _supervisor_liveness.threshold_for(sup=request.sup, track=request.track)
    ):
        _reset_capture_watch(request=request)
        return StallWatchResult(
            status=request.status,
            note=request.note,
            active_conditions=set(request.active_conditions),
        )

    capture_hash = _capture_hash(capture=request.obs.capture)
    if state.stall_watch_capture_hash != capture_hash or state.stall_watch_capture_since is None:
        _reset_capture_watch(request=request)
        return StallWatchResult(
            status=request.status,
            note=request.note,
            active_conditions=set(request.active_conditions),
        )
    age = max(0.0, request.obs.observed_at - state.stall_watch_capture_since)
    if age <= PANE_STILL_AFTER:
        state.stall_watch_due_observations = 0
        return StallWatchResult(
            status=request.status,
            note=request.note,
            active_conditions=set(request.active_conditions),
        )
    state.stall_watch_due_observations += 1
    if state.stall_watch_due_observations < _REQUIRED_DUE_OBSERVATIONS:
        return StallWatchResult(
            status=request.status,
            note=request.note,
            active_conditions=set(request.active_conditions),
        )
    return _pane_still(request=request, age=age)


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
    low_context = _supervisor_working_low_context.apply_working_low_context_attention(
        request=_supervisor_working_low_context.WorkingLowContextRequest(
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
    stall_watch = apply_stall_watch(
        request=StallWatchRequest(
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
    return EvaluationMonitorResult(
        status=stall_watch.status,
        note=stall_watch.note,
        active_conditions=stall_watch.active_conditions,
        picker_stall=picker_stall,
    )
