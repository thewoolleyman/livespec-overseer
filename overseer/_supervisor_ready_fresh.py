"""Fresh ready-without-round certification helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass

import registry
import signals
from _supervisor_config import READY_ARM_MAX_AGE

__all__: list[str] = [
    "ObservationHistory",
    "fresh_ready_without_round_candidate",
    "fresh_ready_without_round_valid",
    "has_iso_added_at",
    "observation_history",
    "ready_declaration_age_within_limit",
]


@dataclass(frozen=True, kw_only=True)
class ObservationHistory:
    mapped: bool
    session_identity: str | None
    added_at: str | None


def observation_history(
    *,
    store_path: str | os.PathLike[str] | None,
    repo: str,
    topic: str,
) -> ObservationHistory:
    repo_norm = registry.norm(repo=repo)
    for track in registry.read_valid_mapping(store_path=store_path):
        if registry.norm(repo=track.repo) == repo_norm and track.topic == topic:
            return ObservationHistory(
                mapped=True,
                session_identity=track.observed_session_identity,
                added_at=track.added_at,
            )
    return ObservationHistory(mapped=False, session_identity=None, added_at=None)


def has_iso_added_at(*, history: ObservationHistory) -> bool:
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


def fresh_ready_without_round_valid(
    *,
    declared: signals.TrackState | None,
    round_record: registry.RoundRecord,
    session_identity: str | None,
    history: ObservationHistory,
    now: float,
) -> bool:
    return (
        fresh_ready_without_round_candidate(
            declared=declared,
            round_record=round_record,
            session_identity=session_identity,
            history=history,
        )
        and declared is not None
        and ready_declaration_age_within_limit(declared=declared, now=now)
    )


def fresh_ready_without_round_candidate(
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
        and has_iso_added_at(history=history)
        and (history.session_identity is None or history.session_identity == session_identity)
    )


def ready_declaration_age_within_limit(*, declared: signals.TrackState, now: float) -> bool:
    return max(0.0, now - declared.mtime) <= READY_ARM_MAX_AGE
