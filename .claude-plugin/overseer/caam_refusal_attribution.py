"""Whose refusal it was: the one question a refusal record cannot answer itself.

A transcript says a request was refused. It does not say which account was
spending at that moment, and getting that wrong is worse than missing the
refusal entirely -- it would move the fleet off a healthy account on the
strength of another account's exhaustion. So attribution is a conjunction of
conditions, every one of which must hold, and every one of which FAILS CLOSED.
The first of them is the moment the operation last observed the active account
become ACTIVE: a refusal recorded before it belongs to whatever was active then.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from caam_decision import ProfileUsage, UsageRecord
from caam_profiles import ActiveIdentity
from caam_refusal_store import Activation, record_activation, remember_refusals
from caam_refusals import Refusal, RefusalReader, TrackedSession, session_refusals

__all__: list[str] = [
    "LIVE_CONFIG_REL",
    "RefusalObservation",
    "observe_refusals",
]

LIVE_CONFIG_REL: Final = ".claude"


@dataclass(frozen=True, kw_only=True)
class RefusalObservation:
    """One pass's evidence about refusals, carried as one value.

    ``current`` is the active account's reading on THIS pass, which is the
    baseline a refusal reporting no reset is later compared against.
    """

    home: Path
    state: dict[str, object]
    active: ActiveIdentity
    current: UsageRecord
    profiles: tuple[ProfileUsage, ...]
    sessions: tuple[TrackedSession, ...]
    now: float
    reader: RefusalReader = session_refusals


def observe_refusals(*, observation: RefusalObservation) -> None:
    """Remember every refusal this pass can attribute to the active account.

    Detecting refusals sends NO request: the records were written by sessions
    that had already made theirs. The whole result is a write to the durable
    store, which is where the decision reads its refusal standing from -- so a
    pass that observes nothing leaves the store, and every decision downstream
    of it, exactly as it found them.
    """
    activation = record_activation(
        state=observation.state,
        active_name=observation.active.profile,
        now=observation.now,
    )
    if activation.fresh:
        # Nothing is attributed on the pass that recorded the activation: the
        # operation has no evidence of when this account became active, and the
        # ratified clause requires recording the moment and attributing nothing
        # rather than guessing.
        return
    remember_refusals(
        state=observation.state,
        account=observation.active.profile,
        refusals=_attributed(observation=observation, activation=activation),
        reading=observation.current,
    )


def _attributed(*, observation: RefusalObservation, activation: Activation) -> tuple[Refusal, ...]:
    return tuple(
        refusal
        for session in observation.sessions
        for refusal in observation.reader(session=session)
        if refusal.recorded_at > activation.at
    )
