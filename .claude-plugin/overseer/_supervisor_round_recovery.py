"""Recovered-round closure for compacted sessions back above threshold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_observe
import registry
import signals
from _supervisor_config import track_key
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["RecoveryRequest", "close_recovered_round"]


@dataclass(frozen=True, kw_only=True)
class RecoveryRequest:
    sup: Supervisor
    track: registry.Track
    obs: Observation
    session: str
    target: str
    threshold: int


def _state_permits_recovery(*, repo: str, topic: str) -> bool:
    declared = signals.read_state(repo=repo, topic=topic)
    if declared is not None:
        return declared.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT
    return not signals.state_path(repo=repo, topic=topic).exists()


def _observation_permits_recovery(*, request: RecoveryRequest, obs: Observation) -> bool:
    return (
        not signals.topic_reserved_for_supervisor(topic=request.track.topic)
        and obs.round_record.at is not None
        and obs.round_record.malformed_reason is None
        and obs.eff_ctx is not None
        and obs.ctx_stale_age is None
        and obs.eff_ctx > request.threshold
        and not registry.read_resume_pending(
            repo=request.track.repo, topic=request.track.topic, stamp_path=request.sup.stamp_path
        )
        and _state_permits_recovery(repo=request.track.repo, topic=request.track.topic)
    )


def _fresh_recovery_observation(*, request: RecoveryRequest) -> Observation | None:
    if not _supervisor_observe.pane_is_managed(
        sup=request.sup,
        target=request.target,
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
    ):
        return None
    fresh = _supervisor_observe.observe(
        sup=request.sup,
        track=request.track,
        session=request.session,
        target=request.target,
        key=track_key(repo=request.track.repo, topic=request.track.topic),
    )
    if not _observation_permits_recovery(request=request, obs=fresh):
        return None
    return fresh


def close_recovered_round(*, request: RecoveryRequest) -> bool:
    """Close a delivered round whose context is known recovered above threshold."""
    if not _observation_permits_recovery(request=request, obs=request.obs):
        return False
    fresh = _fresh_recovery_observation(request=request)
    if fresh is None:
        return False
    final = _fresh_recovery_observation(request=request)
    if final is None:
        return False
    registry.clear_injection_stamp(
        repo=request.track.repo, topic=request.track.topic, stamp_path=request.sup.stamp_path
    )
    _ = request.sup.inject.pop(track_key(repo=request.track.repo, topic=request.track.topic), None)
    request.sup.log(
        message=(
            f"closed recovered round for {request.track.repo}::{request.track.topic} "
            f"(ctx {final.eff_ctx}% > threshold {request.threshold}%)"
        )
    )
    return True
