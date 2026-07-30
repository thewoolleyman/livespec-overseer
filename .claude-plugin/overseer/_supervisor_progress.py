"""_supervisor_progress — row facts used by pair-stall detection.

A private collaborator of :mod:`_supervisor_evaluate`. The decision cascade owns the
operator-facing status; this module only annotates the resulting row with the
content-immune progress and human-wait facts consumed by the pair-level pass.
"""

from __future__ import annotations

import registry
import signals
from _supervisor_records import Observation
from _supervisor_view import RowView

__all__: list[str] = ["row_view"]


def row_view(
    *,
    track: registry.Track,
    session: str,
    status: str,
    note: str | None,
    obs: Observation,
    settled_streaming_progress: bool,
) -> RowView:
    """Build the operator row and pair-stall detector annotations."""

    return RowView(
        topic=track.topic,
        repo=track.repo,
        tmux=session,
        ctx=obs.eff_ctx,
        status=status,
        note=note,
        runtime=obs.runtime,
        progress_now=_progress_now(obs=obs, settled_streaming_progress=settled_streaming_progress),
        human_wait=obs.gate or obs.claude_status == "waiting" or obs.blocked is not None,
        round_open=obs.injection_stamp is not None,
        acked=obs.acked,
    )


def _progress_now(*, obs: Observation, settled_streaming_progress: bool) -> bool:
    """Return track-level progress, with capture heuristics admitted only for Codex."""

    return (
        obs.claude_status == "busy"
        or obs.ctx_changed
        or (obs.is_codex and signals.is_busy(capture_text=obs.capture))
        or settled_streaming_progress
    )
