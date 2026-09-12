"""Ready certification facts derived during supervisor observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_ready_fresh
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "RoundObservation",
    "live_session_identity",
    "round_observation",
    "session_identity",
]


@dataclass(frozen=True, kw_only=True)
class RoundObservation:
    record: registry.RoundRecord
    session_identity: str | None
    live_session_identity: str | None
    ready_uncertifiable_reason: str | None
    ready: bool


def live_session_identity(
    *,
    sup: Supervisor,
    session: str,
    topic: str,
    runtime: str,
) -> str | None:
    """The identity of the PROCESS this daemon can prove is in the pane, or None.

    Strictly the resolved answer: no fallback, no synthesis. That is what separates it
    from :func:`session_identity`, and the separation is load-bearing for
    `_supervisor_compaction`, which uses a CHANGE of identity as its only evidence that
    a restart completed. The Claude fallback below is constant across a real restart in
    one tmux session, so a consumer reasoning about session CHANGE must never see it —
    None ("this daemon cannot say") is the honest answer there, and it is the answer
    that makes that consumer fail closed.
    """
    if runtime == "codex":
        live = sup.live_codex.get((session, topic))
        return f"codex:{live.session_id}" if live is not None else None
    if runtime == "claude":
        return sup.claude_identity_by_session.get((session, topic))
    return None


def session_identity(
    *,
    sup: Supervisor,
    session: str,
    topic: str,
    runtime: str,
) -> str | None:
    """The certification identity token for the live session in this pane."""
    identity = live_session_identity(sup=sup, session=session, topic=topic, runtime=runtime)
    if identity is None and runtime == "claude":
        return f"claude:{session}:{topic}"
    return identity


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
    history = _supervisor_ready_fresh.observation_history(
        store_path=sup.store_path, repo=repo, topic=topic
    )
    now = sup.now()
    fresh_ready_without_round = _supervisor_ready_fresh.fresh_ready_without_round_valid(
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
        live_session_identity=live_session_identity(
            sup=sup, session=session, topic=topic, runtime=runtime
        ),
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


def _ready_uncertifiable_reason(
    *,
    declared: signals.TrackState | None,
    round_record: registry.RoundRecord,
    session_identity: str | None,
    history: _supervisor_ready_fresh.ObservationHistory,
    now: float,
) -> str | None:
    reason: str | None = None
    if (
        declared is None
        or declared.token != signals.STATE_READY
        or _supervisor_ready_fresh.fresh_ready_without_round_valid(
            declared=declared,
            round_record=round_record,
            session_identity=session_identity,
            history=history,
            now=now,
        )
    ):
        reason = None
    elif _supervisor_ready_fresh.fresh_ready_without_round_candidate(
        declared=declared,
        round_record=round_record,
        session_identity=session_identity,
        history=history,
    ) and not _supervisor_ready_fresh.ready_declaration_age_within_limit(
        declared=declared, now=now
    ):
        reason = "ready declaration exceeded 30m max age"
    elif (
        round_record.at is None
        and history.session_identity is not None
        and session_identity is not None
        and history.session_identity != session_identity
    ):
        reason = (
            "session identity differs from observed identity "
            f"(observed={history.session_identity}; live={session_identity})"
        )
    elif round_record.malformed_reason is not None:
        reason = round_record.malformed_reason
    elif round_record.at is None:
        reason = "no supervision round open"
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
        elif not _supervisor_ready_fresh.ready_declaration_age_within_limit(
            declared=declared, now=now
        ):
            reason = "ready declaration exceeded 30m max age"
    return reason
