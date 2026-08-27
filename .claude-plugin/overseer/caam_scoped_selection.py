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

from caam_decision import triggered
from caam_decision_models import ProfileUsage, UsageRecord
from caam_decision_protection import NO_PROTECTION_FLOORS, can_serve_scoped_model

__all__: list[str] = [
    "none_can_serve_scoped_model",
    "scoped_alone_trigger",
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
