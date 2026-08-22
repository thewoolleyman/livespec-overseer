"""_supervisor_progress — row facts used by pair-stall detection.

A private collaborator of :mod:`_supervisor_evaluate`. The decision cascade owns the
operator-facing status; this module only annotates the resulting row with the
content-immune progress and human-wait facts consumed by the pair-level pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_records import Observation
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_picker_stall import PickerStallView

__all__: list[str] = ["RowViewRequest", "blocked_human_stall_seconds", "row_view"]


@dataclass(frozen=True, kw_only=True)
class RowViewRequest:
    track: registry.Track
    session: str
    status: str
    note: str | None
    obs: Observation
    settled_streaming_progress: bool
    picker_stall: PickerStallView
    supervisor_state_stale: bool


def blocked_human_stall_seconds(*, obs: Observation, status: str, picker_open: bool) -> int:
    """Age of an open picker while the row is waiting on a human."""
    if status != "blocked:human" or not picker_open:
        obs.istate.blocked_human_stall_since = None
        obs.istate.blocked_human_stall_capture = None
        obs.istate.picker_stall_nudged = False
        obs.istate.picker_stall_nudge_echo_capture = None
        return 0
    since = obs.istate.blocked_human_stall_since
    if since is None:
        obs.istate.blocked_human_stall_since = obs.observed_at
        obs.istate.blocked_human_stall_capture = obs.capture
        return 0
    if obs.istate.blocked_human_stall_capture != obs.capture:
        if (
            obs.istate.picker_stall_nudged
            and obs.istate.picker_stall_nudge_echo_capture == obs.capture
        ):
            obs.istate.picker_stall_nudge_echo_capture = None
        obs.istate.blocked_human_stall_capture = obs.capture
    return int(max(0.0, obs.observed_at - since))


def row_view(*, request: RowViewRequest) -> RowView:
    """Build the operator row and pair-stall detector annotations."""

    return RowView(
        topic=request.track.topic,
        repo=request.track.repo,
        tmux=request.session,
        ctx=request.obs.eff_ctx,
        status=request.status,
        note=request.note,
        runtime=request.obs.runtime,
        progress_now=_progress_now(
            obs=request.obs,
            settled_streaming_progress=request.settled_streaming_progress,
        ),
        human_wait=(
            request.obs.gate
            or request.obs.claude_status == "waiting"
            or request.obs.blocked is not None
        ),
        round_open=request.obs.injection_stamp is not None,
        acked=request.obs.acked,
        picker_open=request.picker_stall.picker_open,
        stall_seconds=request.picker_stall.stall_seconds,
        supervisor_state_stale=request.supervisor_state_stale,
    )


def _progress_now(*, obs: Observation, settled_streaming_progress: bool) -> bool:
    """Return track-level progress, with capture heuristics admitted only for Codex."""

    return (
        obs.claude_status == "busy"
        or obs.ctx_changed
        or (obs.is_codex and signals.is_busy(capture_text=obs.capture))
        or settled_streaming_progress
    )
