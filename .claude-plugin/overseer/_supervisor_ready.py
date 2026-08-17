"""Ready certification facts derived during supervisor observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_config import READY_ARM_MAX_AGE

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


@dataclass(frozen=True, kw_only=True)
class ObservationHistory:
    mapped: bool
    session_identity: str | None
    added_at: str | None


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


def _observation_history(
    *,
    sup: Supervisor,
    repo: str,
    topic: str,
) -> ObservationHistory:
    repo_norm = registry.norm(repo=repo)
    for track in registry.read_mapping(store_path=sup.store_path):
        if registry.norm(repo=track.repo) == repo_norm and track.topic == topic:
            return ObservationHistory(
                mapped=True,
                session_identity=track.observed_session_identity,
                added_at=track.added_at,
            )
    return ObservationHistory(mapped=False, session_identity=None, added_at=None)


def _has_iso_added_at(*, history: ObservationHistory) -> bool:
    added_at = history.added_at
    return (
        added_at is not None
        and len(added_at) == len("2026-08-16T23:45:00Z")
        and added_at[4] == "-"
        and added_at[7] == "-"
        and added_at[10] == "T"
        and added_at[13] == ":"
        and added_at[16] == ":"
        and added_at.endswith("Z")
    )


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
    history = _observation_history(sup=sup, repo=repo, topic=topic)
    now = sup.now()
    fresh_ready_without_round = _fresh_ready_without_round_valid(
        declared=declared,
        round_record=record,
        session_identity=identity,
        history=history,
        now=now,
    )
    ready_uncertifiable_reason = _ready_uncertifiable_reason(
        declared=declared,
        round_record=record,
        session_identity=identity,
        history=history,
        now=now,
    )
    return RoundObservation(
        record=record,
        session_identity=identity,
        ready_uncertifiable_reason=ready_uncertifiable_reason,
        ready=(
            ready_uncertifiable_reason is None
            and (
                fresh_ready_without_round
                or signals.ready_valid(
                    repo=repo,
                    topic=topic,
                    certification_floor=record.certification_floor,
                    malformed_round_reason=record.malformed_reason,
                    round_session_identity=record.session_identity,
                    live_session_identity=identity,
                )
            )
        ),
    )


def _fresh_ready_without_round_valid(
    *,
    declared: signals.TrackState | None,
    round_record: registry.RoundRecord,
    session_identity: str | None,
    history: ObservationHistory,
    now: float,
) -> bool:
    return (
        _fresh_ready_without_round_candidate(
            declared=declared,
            round_record=round_record,
            session_identity=session_identity,
            history=history,
        )
        and declared is not None
        and _ready_declaration_age_within_limit(declared=declared, now=now)
    )


def _fresh_ready_without_round_candidate(
    *,
    declared: signals.TrackState | None,
    round_record: registry.RoundRecord,
    session_identity: str | None,
    history: ObservationHistory,
) -> bool:
    return (
        declared is not None
        and declared.token == signals.STATE_READY
        and round_record.at is None
        and round_record.malformed_reason is None
        and session_identity is not None
        and history.mapped
        and _has_iso_added_at(history=history)
        and history.session_identity is None
    )


def _ready_declaration_age_within_limit(*, declared: signals.TrackState, now: float) -> bool:
    return max(0.0, now - declared.mtime) <= READY_ARM_MAX_AGE


def _ready_uncertifiable_reason(
    *,
    declared: signals.TrackState | None,
    round_record: registry.RoundRecord,
    session_identity: str | None,
    history: ObservationHistory,
    now: float,
) -> str | None:
    reason: str | None = None
    if (
        declared is None
        or declared.token != signals.STATE_READY
        or _fresh_ready_without_round_valid(
            declared=declared,
            round_record=round_record,
            session_identity=session_identity,
            history=history,
            now=now,
        )
    ):
        reason = None
    elif _fresh_ready_without_round_candidate(
        declared=declared,
        round_record=round_record,
        session_identity=session_identity,
        history=history,
    ) and not _ready_declaration_age_within_limit(declared=declared, now=now):
        reason = "ready declaration exceeded 30m max age"
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
        elif not _ready_declaration_age_within_limit(declared=declared, now=now):
            reason = "ready declaration exceeded 30m max age"
    return reason
