"""Whose refusal it was: the one question a refusal record cannot answer itself.

A transcript says a request was refused. It does not say which account was
spending at that moment, and getting that wrong is worse than missing the
refusal entirely -- it would move the fleet off a healthy account on the
strength of another account's exhaustion. So attribution is a conjunction of
conditions, every one of which must hold, and every one of which FAILS CLOSED:

  * the session authenticates with the HOST-WIDE LIVE credential, established
    from its agent configuration directory being the host's default one. Neither
    a separately provisioned credential nor the operation's own
    refresh-maintenance sandbox -- whose sessions deliberately exercise OTHER
    accounts' stored credentials -- can contribute;
  * where the record names an account identity, it is the active account's
    stable identifier;
  * the refusal was recorded AFTER the moment the operation last observed this
    account become active;
  * the reset it reported has not already passed; and
  * that reset does not match, within the one-minute tolerance, the same
    window's reset as last read on any DEPARTED account, because concurrent
    sessions MAY still be spending a departed account's credential for a while
    after a switch and their refusals belong to it.

TWO RESIDUALS ARE ACCEPTED AND NOT CORRECTED, as the ratified clause states. A
lagging session's RATE-LIMIT refusal derives its reset from its own retry-after
interval, so it cannot match a departed account's reset and may be attributed to
the new account -- bounded by its own short hold. And a genuine refusal of the
new account whose reset coincides within a minute with a departed account's is
NOT attributed, which fails safe because every other trigger still applies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from caam_decision import ProfileUsage, UsageRecord
from caam_profiles import ActiveIdentity
from caam_refusal_store import (
    Activation,
    DepartedEntry,
    departed_entries,
    record_activation,
    remember_refusals,
)
from caam_refusals import (
    WINDOW_FIVE_HOUR,
    Refusal,
    RefusalReader,
    TrackedSession,
    session_refusals,
)

__all__: list[str] = [
    "LIVE_CONFIG_REL",
    "RefusalObservation",
    "observe_refusals",
]

LIVE_CONFIG_REL: Final = ".claude"
_RESET_TOLERANCE_S: Final = 60.0


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
        profiles=observation.profiles,
        now=observation.now,
    )
    if activation.fresh:
        # Nothing is attributed on the pass that recorded the activation: the
        # operation has no evidence of when this account became active, and the
        # ratified clause requires recording the moment and attributing nothing
        # rather than guessing.
        return
    departed = departed_entries(state=observation.state, active_name=observation.active.profile)
    remember_refusals(
        state=observation.state,
        account=observation.active.profile,
        refusals=_attributed(observation=observation, activation=activation, departed=departed),
        reading=observation.current,
    )


def _attributed(
    *,
    observation: RefusalObservation,
    activation: Activation,
    departed: tuple[DepartedEntry, ...],
) -> tuple[Refusal, ...]:
    return tuple(
        refusal
        for session in observation.sessions
        if _on_the_live_credential(session=session, home=observation.home)
        for refusal in observation.reader(session=session)
        if _attributable(
            refusal=refusal,
            observation=observation,
            activation=activation,
            departed=departed,
        )
    )


def _on_the_live_credential(*, session: TrackedSession, home: Path) -> bool:
    return session.config_dir == home / LIVE_CONFIG_REL


def _attributable(
    *,
    refusal: Refusal,
    observation: RefusalObservation,
    activation: Activation,
    departed: tuple[DepartedEntry, ...],
) -> bool:
    if refusal.recorded_at <= activation.at:
        return False
    if refusal.resets_at is not None and refusal.resets_at <= observation.now:
        return False
    if refusal.account is not None and refusal.account != observation.active.account_uuid:
        return False
    return not _matches_a_departed_reset(refusal=refusal, departed=departed)


def _matches_a_departed_reset(*, refusal: Refusal, departed: tuple[DepartedEntry, ...]) -> bool:
    """Whether this refusal's reset is one a departed account was last read at.

    A refusal that reported no reset never matches, so it is attributed to the
    active account and bounded by the replenishment rule instead.
    """
    reported = refusal.resets_at
    if reported is None:
        return False
    return any(
        abs(reported - reset) <= _RESET_TOLERANCE_S
        for entry in departed
        for reset in (_entry_reset(entry=entry, window=refusal.window),)
        if reset is not None
    )


def _entry_reset(*, entry: DepartedEntry, window: str) -> float | None:
    if window == WINDOW_FIVE_HOUR:
        return entry.five_hour_reset_at
    return entry.seven_day_reset_at
