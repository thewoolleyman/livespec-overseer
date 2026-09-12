"""Observation-side helpers for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_compaction
import registry
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "COMPACTION_LATCHED_CONDITION",
    "RecordObservationRequest",
    "record_tick_observations",
]

# The edge-triggered condition a caught compaction alerts under. It names the FAILURE,
# not the warning that follows from it: an operator reading the history must be able to
# tell "this track crossed its threshold" from "this track's context generation was
# thrown away and summarized", and both produce the same `warned` row.
COMPACTION_LATCHED_CONDITION = "context-compaction-latched"


@dataclass(frozen=True, kw_only=True)
class RecordObservationRequest:
    sup: Supervisor
    track: registry.Track
    obs: Observation
    session: str
    pane: str
    act: bool


def record_tick_observations(*, request: RecordObservationRequest) -> None:
    """Persist what this tick OBSERVED about the track, and report what it caught.

    Both writes are gated on ``act`` for the same reason: the read-only ``list`` path
    must classify without mutating the store. Both are idempotent, so a steady-state
    tick — same identity, watermark already at the lowest reading — rewrites nothing.

    They sit together because they are the same kind of fact and carry the same
    durability requirement. The observed identity is what a dead-track recovery later
    reads to know which runtime it is reviving; the context-generation record is what a
    bounced daemon reads to know a restart is still owed. An in-memory version of
    either would be discarded by exactly the event it exists to survive.
    """
    if not request.act:
        return
    obs = request.obs
    if obs.session_identity is not None:
        _ = registry.record_observed_session_identity(
            repo=request.track.repo,
            topic=request.track.topic,
            session_identity=obs.session_identity,
            store_path=request.sup.store_path,
        )
    _ = registry.record_context_compaction(
        repo=request.track.repo,
        topic=request.track.topic,
        record=obs.compaction.record,
        store_path=request.sup.store_path,
    )
    _report_compaction_edges(request=request)


def _report_compaction_edges(*, request: RecordObservationRequest) -> None:
    """Say what the fold caught, once per edge.

    A caught compaction ALERTS with its session identity and its context transition,
    because the row it goes on to produce is an ordinary `warned` and nothing else on
    that row says why. A cleared latch LOGS, because "the successor was adopted and the
    obligation is discharged" is the outcome an operator who saw that alert is waiting
    for, and an obligation that vanishes silently cannot be told from one that was
    dropped.
    """
    obs = request.obs
    if obs.compaction.detected:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                "CONTEXT COMPACTION detected — "
                f"{_supervisor_compaction.compaction_evidence(record=obs.compaction.record)}; "
                "the compacted generation is exhausted, so a cooperative wind-down and a "
                "fresh-session restart stay REQUIRED at any later context percentage"
            ),
            condition=COMPACTION_LATCHED_CONDITION,
        )
    elif obs.compaction.successor:
        request.sup.log(
            message=(
                f"context-compaction latch cleared for {request.track.repo}::"
                f"{request.track.topic} after fresh session "
                f"{obs.compaction.record.session_identity} was adopted"
            )
        )
