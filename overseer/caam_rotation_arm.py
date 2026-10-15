"""The values and the shared terms every rotation arm reads.

One arm per trigger, and each one needs the same three things before it can
choose anything: whether an operator pin names the scoped model, which accounts
a refusal holds, and what the pass is leaving ON. Resolving them once and
handing them to whichever arm runs is what keeps the arms from disagreeing about
their own inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from caam_anthropic_finish import SaveState
from caam_decide_context import DecisionContext
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    five_hour_remaining_floor,
)
from caam_refusal_hold import RefusalState, TriggerBinding, refusal_state, trigger_binding
from caam_refusal_store import RememberedRefusal
from caam_refusals import WINDOW_FIVE_HOUR
from caam_scoped_model import scoped_model_pinned

__all__: list[str] = [
    "RotationArm",
    "RotationChoice",
    "RotationRequest",
    "arm_active_account",
    "resolve_arm",
    "short_window_triggered",
]


@dataclass(frozen=True, kw_only=True)
class RotationRequest:
    """Everything a trigger arm reads, carried as one value.

    The pass's own seams are deliberately absent except the state save the hold
    paths owe: an arm selects and reports, and nothing here can switch.
    """

    context: DecisionContext
    profiles: tuple[ProfileUsage, ...]
    active_name: str
    current: UsageRecord
    protection_floors: Mapping[str, float]
    scheduled: bool
    save_state: SaveState


@dataclass(frozen=True, kw_only=True)
class RotationChoice:
    """The destination a fired trigger selected, or the exit code of its own hold.

    `target` is None exactly when this pass has already reported a hold and
    `exit_code` is the whole answer; the caller owes nothing further. The other
    fields describe the move: the operator line that states why it is being made,
    which trigger is making it, the refusal that governed it where one did, and
    whether the short-window threshold was among those that fired, which the
    expiring-quota drain remembers.
    """

    target: ProfileUsage | None
    decision_line: str = ""
    trigger: str = ""
    exit_code: int = 0
    short_window_triggered: bool = False
    refusal: RememberedRefusal | None = None


@dataclass(frozen=True, kw_only=True)
class RotationArm:
    """The terms every arm shares, resolved once for the pass."""

    scoped_pin: bool
    refusal: RefusalState
    bound: TriggerBinding


def resolve_arm(*, request: RotationRequest) -> RotationArm:
    """Resolve the shared terms, once, for whichever arm the pass then runs."""
    refusal = refusal_state(state=request.context.state, active_name=request.active_name)
    return RotationArm(
        scoped_pin=scoped_model_pinned(state=request.context.state),
        refusal=refusal,
        bound=trigger_binding(
            refusal=refusal,
            current=request.current,
            active_name=request.active_name,
            protection_floors=request.protection_floors,
        ),
    )


def arm_active_account(*, request: RotationRequest, arm: RotationArm) -> ActiveAccount:
    return ActiveAccount(name=request.active_name, usage=arm.bound.usage, scoped_pin=arm.scoped_pin)


def short_window_triggered(*, request: RotationRequest, arm: RotationArm) -> bool:
    """Whether the short-window threshold was among the triggers that fired.

    Read on EVERY arm, the drain included, because the expiring-quota drain's
    condition (f) remembers the account a short-window move departed from
    whatever else was true of that pass. A move made under the refusal trigger
    on a short-window refusal counts as a short-window move for that condition,
    which is why this is a disjunction rather than a choice between the two: a
    weekly refusal does not stop the short-window threshold from having fired.
    """
    refused = arm.refusal.active
    if refused is not None and refused.refusal.window == WINDOW_FIVE_HOUR:
        return True
    return request.current.five_hour_remaining <= five_hour_remaining_floor()
