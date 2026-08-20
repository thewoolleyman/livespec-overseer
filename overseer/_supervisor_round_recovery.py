"""Safe closure of delivered rounds that no longer belong to the live session."""

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
        return signals.valid_token(token=declared.token) and not signals.valid_session_token(
            token=declared.token
        )
    return not signals.state_path(repo=repo, topic=topic).exists()


def _round_closure_common_permits(*, request: RecoveryRequest, obs: Observation) -> bool:
    observed = obs.declared
    return (
        obs.round_record.at is not None
        and obs.round_record.malformed_reason is None
        and obs.ctx_stale_age is None
        and not registry.read_resume_pending(
            repo=request.track.repo, topic=request.track.topic, stamp_path=request.sup.stamp_path
        )
        and _state_permits_recovery(repo=request.track.repo, topic=request.track.topic)
        and (
            observed is None
            or (
                signals.valid_token(token=observed.token)
                and not signals.valid_session_token(token=observed.token)
            )
        )
    )


def _observation_permits_recovery(*, request: RecoveryRequest, obs: Observation) -> bool:
    return (
        _round_closure_common_permits(request=request, obs=obs)
        and obs.eff_ctx is not None
        and obs.eff_ctx > request.threshold
    )


def _observation_permits_identity_reset(*, request: RecoveryRequest, obs: Observation) -> bool:
    return (
        obs.round_record.session_identity is not None
        and obs.session_identity is not None
        and obs.session_identity != obs.round_record.session_identity
        and _round_closure_common_permits(request=request, obs=obs)
    )


def _closure_reason(*, request: RecoveryRequest, obs: Observation) -> str | None:
    if _observation_permits_identity_reset(request=request, obs=obs):
        return "identity-reset"
    if _observation_permits_recovery(request=request, obs=obs):
        return "recovered"
    return None


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
    if _closure_reason(request=request, obs=fresh) is None:
        return None
    return fresh


def _log_closure(*, request: RecoveryRequest, final: Observation) -> None:
    if _observation_permits_identity_reset(request=request, obs=final):
        message = (
            f"closed round for {request.track.repo}::{request.track.topic} "
            "after live session identity changed "
            f"(round={final.round_record.session_identity}; live={final.session_identity})"
        )
        _ = request.sup.out.write(f"{message}\n")
        request.sup.log(message=message)
        return
    request.sup.log(
        message=(
            f"closed recovered round for {request.track.repo}::{request.track.topic} "
            f"(ctx {final.eff_ctx}% > threshold {request.threshold}%)"
        )
    )


def close_recovered_round(*, request: RecoveryRequest) -> bool:
    """Close a delivered round when fresh observations prove it is no longer current."""
    if _closure_reason(request=request, obs=request.obs) is None:
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
    _log_closure(request=request, final=final)
    return True
