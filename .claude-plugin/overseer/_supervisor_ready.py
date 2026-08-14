"""Ready certification facts derived during supervisor observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "RoundObservation",
    "round_observation",
    "session_identity",
]


@dataclass(frozen=True, kw_only=True)
class RoundObservation:
    record: registry.RoundRecord
    session_identity: str | None
    ready_uncertifiable_reason: str | None
    ready: bool


def session_identity(
    *,
    sup: Supervisor,
    session: str,
    topic: str,
    runtime: str,
) -> str | None:
    """The certification identity token for the live session in this pane."""
    if runtime == "codex":
        live = sup.live_codex.get((session, topic))
        return f"codex:{live.session_id}" if live is not None else None
    if runtime == "claude":
        identity = sup.claude_identity_by_session.get((session, topic))
        return identity if identity is not None else f"claude:{session}:{topic}"
    return None


def round_observation(
    *,
    sup: Supervisor,
    repo: str,
    topic: str,
    session: str,
    runtime: str,
    declared: signals.TrackState | None,
) -> RoundObservation:
    record = registry.read_round_record(repo=repo, topic=topic, stamp_path=sup.stamp_path)
    identity = session_identity(sup=sup, session=session, topic=topic, runtime=runtime)
    return RoundObservation(
        record=record,
        session_identity=identity,
        ready_uncertifiable_reason=_ready_uncertifiable_reason(
            declared=declared, round_record=record, session_identity=identity
        ),
        ready=signals.ready_valid(
            repo=repo,
            topic=topic,
            certification_floor=record.certification_floor,
            malformed_round_reason=record.malformed_reason,
            round_session_identity=record.session_identity,
            live_session_identity=identity,
        ),
    )


def _ready_uncertifiable_reason(
    *,
    declared: signals.TrackState | None,
    round_record: registry.RoundRecord,
    session_identity: str | None,
) -> str | None:
    reason: str | None = None
    if declared is None or declared.token != signals.STATE_READY:
        reason = None
    elif round_record.at is None:
        reason = "no supervision round open"
    elif round_record.malformed_reason is not None:
        reason = round_record.malformed_reason
    elif session_identity is None:
        reason = "session identity cannot be determined"
    elif session_identity != round_record.session_identity:
        reason = (
            "session identity differs from round-open identity "
            f"(round={round_record.session_identity}; live={session_identity})"
        )
    else:
        floor = round_record.certification_floor
        if floor is not None and declared.mtime <= floor:
            reason = "ready predates certification floor"
    return reason
