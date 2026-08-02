"""Note preparation for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_liveness
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["EvaluationNotes", "PrepareNotesRequest", "prepare_evaluation_notes"]


@dataclass(frozen=True, kw_only=True)
class EvaluationNotes:
    blocked_age: float | None
    blocked_age_label: str | None
    note: str | None
    ctx_stale_note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class PrepareNotesRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    declared: signals.TrackState | None
    malformed: bool
    blocked: str | None
    ctx_stale_age: float | None
    act: bool


def prepare_evaluation_notes(*, request: PrepareNotesRequest) -> EvaluationNotes:
    blocked_age = _supervisor_liveness.blocked_age(sup=request.sup, declared=request.declared)
    blocked_age_label = _supervisor_liveness.age_label_or_none(seconds=blocked_age)

    # The row note defaults to the blocked reason with declaration age (if any); the
    # busy branch overrides it to "background shell" when a live background shell is
    # the SOLE reason the pane isn't idle, so the operator can see WHY.
    note: str | None = _supervisor_liveness.blocked_note(
        blocked=request.blocked, blocked_age_label=blocked_age_label
    )
    ctx_stale_note = (
        f"ctx unreadable ({_supervisor_liveness.age_label(seconds=request.ctx_stale_age)})"
        if request.ctx_stale_age is not None
        else None
    )
    active_conditions: set[str] = set()
    if request.malformed and request.declared is not None:
        active_conditions.add("malformed-state")
        note = f"BAD state file: {request.declared.token!r}"
        if request.act:
            request.sup.alert(
                repo=request.track.repo,
                topic=request.track.topic,
                session=request.session,
                pane=request.pane,
                message=(
                    f"MALFORMED state file: {request.declared.token!r} is not one of "
                    f"{', '.join(signals.STATE_TOKENS)} — treated as no declaration "
                    f"(the track will NOT be restarted)"
                ),
                condition="malformed-state",
            )
    return EvaluationNotes(
        blocked_age=blocked_age,
        blocked_age_label=blocked_age_label,
        note=note,
        ctx_stale_note=ctx_stale_note,
        active_conditions=active_conditions,
    )
