"""Where a pass observes refusals, and where it gets the sessions to observe.

A thin stage, deliberately: the pass hands over the readings it has just taken
and the sessions it was given, and everything that follows -- parsing the
provider's records, attributing them, remembering what survived -- belongs to
`caam_refusal_attribution`. Keeping the composition here is what lets the pass
call one function with the values it already holds rather than assembling an
observation out of seven of them.
"""

from __future__ import annotations

from typing import cast

from caam_decide_context import DecisionContext
from caam_decision import ProfileUsage, UsageRecord
from caam_profiles import ActiveIdentity
from caam_refusal_attribution import RefusalObservation, observe_refusals
from caam_refusal_sessions import discover_tracked_sessions
from caam_refusals import TrackedSessionSource

__all__: list[str] = [
    "TrackedSessionSource",
    "observe_pass_refusals",
    "tracked_session_source",
]


def tracked_session_source(*, overrides: dict[str, object]) -> TrackedSessionSource:
    """Discovery in production; whatever a scenario states instead."""
    return cast(TrackedSessionSource, overrides.get("tracked_sessions", discover_tracked_sessions))


def observe_pass_refusals(
    *,
    context: DecisionContext,
    active: ActiveIdentity,
    current: UsageRecord,
    profiles: tuple[ProfileUsage, ...],
    source: TrackedSessionSource,
) -> None:
    """Observe this pass's refusals into the durable store the decision reads.

    Sends NO request: the records were written by the sessions that had already
    made theirs. The sessions are resolved HERE rather than by the caller so the
    pass does not hold a value it has no other use for.
    """
    observe_refusals(
        observation=RefusalObservation(
            home=context.home,
            state=context.state,
            active=active,
            current=current,
            profiles=profiles,
            sessions=source(home=context.home),
            now=context.now,
        )
    )
