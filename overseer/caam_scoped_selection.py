"""Whether the scoped-model clause licenses holding this pass, and why.

The clause's hold is conditioned on two facts a single pass must establish
together, and they are about different things: the trigger's PROVENANCE -- was
scoped unsatisfiability the whole reason for leaving -- and the CANDIDATE SET's
capability -- can anything within reach serve the pin. Neither is a property of
one account, so neither belongs beside the per-account predicates; keeping them
here keeps the pure decision helpers below the size at which they stop being
readable, and gives the clause's two halves one place to be read together.

These sit ABOVE `caam_decision` rather than inside it, and deliberately are not
re-exported from there: the dependency runs one way, so the pure helpers stay
unaware of the pass-level question they are asked in service of.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import inf

from caam_decision import (
    every_live_account_under_reserve,
    min_headroom_gain,
    triggered,
    weekly_reserve,
)
from caam_decision_models import ProfileUsage, UsageRecord
from caam_decision_protection import (
    NO_PROTECTION_FLOORS,
    CandidatePolicy,
    can_serve_scoped_model,
    protection_floor_for,
    select_candidate_set,
)

__all__: list[str] = [
    "none_can_serve_scoped_model",
    "scoped_alone_trigger",
    "scoped_servable_fleet_wide",
]


def scoped_alone_trigger(
    *,
    usage: UsageRecord,
    active_name: str | None = None,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
    scoped_pin: bool = False,
) -> bool:
    """Whether scoped unsatisfiability is the SOLE reason this pass is rotating.

    The ratified clause licenses holding for an unserveable pin only where the
    pin is the whole reason for leaving. An account over its short-window
    threshold, under the weekly reserve, or past its protection floor must still
    rotate for THOSE reasons even while a pin happens to be unsatisfiable
    everywhere -- holding there would strand it for a reason no clause allows.
    So this asks the other legs directly, with no pin, and requires their silence.
    """
    return (
        scoped_pin
        and not can_serve_scoped_model(usage=usage)
        and not triggered(
            usage=usage,
            active_name=active_name,
            protection_floors=protection_floors,
        )
    )


def none_can_serve_scoped_model(*, profiles: tuple[ProfileUsage, ...]) -> bool:
    """Whether no profile in this set can serve the pinned model.

    Vacuously true of an empty set, which is the correct reading: a pass with no
    candidate at all has none that can serve the pin either.
    """
    return not any(can_serve_scoped_model(usage=profile.usage) for profile in profiles)


def scoped_servable_fleet_wide(
    *,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    current: UsageRecord,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
) -> bool:
    """Whether some SELECTABLE account in the fleet can serve the scoped model.

    Per ratified SPECIFICATION v045 "quota for the scoped model" is fleet-wide and
    keyed on selectability: an account counts only if this section's rotation
    rules could actually choose it -- not excluded by a per-account protection
    floor, the zero-weekly disqualifier, the weekly-reserve rule or the
    live-verification rule. The relative-headroom margin is deliberately NOT a
    selectability test: the candidate policy below sets the scoped waiver floor
    unbounded BELOW, so every Fable-capable candidate is judged on those
    exclusions alone, exactly as the scoped clause waives the margin in the
    stranding case. The bound is negative infinity rather than positive because
    the waiver now asks how much a candidate has LEFT -- "more left than nothing
    conceivable" is the same admit-everything test the spent direction wrote as
    "less spent than anything conceivable".
    The ACTIVE account is never a candidate, so it counts whenever its own scoped
    allowance can serve. The reserve is released only when every live account
    sits under it, mirroring `eligible_profiles`, so a fleet entirely under the
    reserve still finds its Fable holder rather than resetting every session.
    """
    if can_serve_scoped_model(usage=current):
        return True

    def _selectable(*, enforce_reserve: bool) -> tuple[ProfileUsage, ...]:
        return select_candidate_set(
            profiles=profiles,
            active_name=active_name,
            policy=CandidatePolicy(
                current=current,
                gain_needed=min_headroom_gain(),
                dimension="five_hour",
                enforce_reserve=enforce_reserve,
                weekly_reserve=weekly_reserve(),
                scoped_waiver_floor=-inf,
                current_protection_floor=protection_floor_for(
                    name=active_name, protection_floors=protection_floors
                ),
            ),
            protection_floors=protection_floors,
        )

    candidates = _selectable(enforce_reserve=True)
    if not candidates and every_live_account_under_reserve(profiles=profiles):
        candidates = _selectable(enforce_reserve=False)
    return not none_can_serve_scoped_model(profiles=candidates)
