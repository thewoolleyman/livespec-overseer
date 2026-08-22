"""_supervisor_progress — row facts used by pair-stall detection.

A private collaborator of :mod:`_supervisor_evaluate`. The decision cascade owns the
operator-facing status; this module only annotates the resulting row with the
content-immune progress and human-wait facts consumed by the pair-level pass.
"""

from __future__ import annotations

import os
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


def blocked_human_stall_seconds(
    *,
    obs: Observation,
    repo: str,
    status: str,
    picker_open: bool,
    stamp_path: str | os.PathLike[str] | None,
    topic: str,
) -> int:
    """Age of an open picker while the row is waiting on a human."""
    if status != "blocked:human" or not picker_open:
        obs.istate.blocked_human_stall_since = None
        obs.istate.blocked_human_stall_capture = None
        obs.istate.picker_stall_nudged = False
        obs.istate.picker_stall_nudge_echo_capture = None
        registry.clear_picker_stall_episode(repo=repo, topic=topic, stamp_path=stamp_path)
        return 0
    gate_signature = _gate_signature(capture=obs.capture)
    durable = registry.read_picker_stall_episode(repo=repo, topic=topic, stamp_path=stamp_path)
    since = _episode_since(
        obs=obs,
        repo=repo,
        topic=topic,
        stamp_path=stamp_path,
        durable=durable,
        gate_signature=gate_signature,
    )
    obs.istate.blocked_human_stall_since = since
    obs.istate.blocked_human_stall_capture = obs.capture
    return int(max(0.0, obs.observed_at - since))


def _episode_since(
    *,
    obs: Observation,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None,
    durable: tuple[float, str] | None,
    gate_signature: str,
) -> float:
    if durable is None or durable[1] != gate_signature:
        registry.record_picker_stall_episode(
            repo=repo,
            topic=topic,
            since=obs.observed_at,
            gate_signature=gate_signature,
            stamp_path=stamp_path,
        )
        obs.istate.picker_stall_nudged = False
        obs.istate.picker_stall_nudge_echo_capture = None
        return obs.observed_at
    if obs.istate.picker_stall_nudged and obs.istate.picker_stall_nudge_echo_capture == obs.capture:
        obs.istate.picker_stall_nudge_echo_capture = None
    return durable[0]


def _gate_signature(*, capture: str) -> str:
    lines = [signals.strip_ansi(text=line).strip() for line in capture.splitlines()]
    option_start = next(
        (index for index, line in enumerate(lines) if _is_gate_option(line=line)),
        None,
    )
    if option_start is None:
        return ""
    gate_lines = [lines[option_start - 1]] if option_start > 0 else []
    for line in lines[option_start:]:
        if not _is_gate_option(line=line):
            break
        gate_lines.append(line)
    return "\n".join(gate_lines)


def _is_gate_option(*, line: str) -> bool:
    return line.startswith(("❯ ", "› ")) or line[:3].strip().isdigit()


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
