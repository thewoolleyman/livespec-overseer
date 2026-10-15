"""Which destination a fired trigger selects, or the hold it reports instead.

Moved out of `caam_anthropic_decide`, which is left with the two steps it is
named for: deciding, and executing the switch that decision asks for. Choosing
WHERE to go is a separate concern with its own rules -- one arm per trigger,
each with its own comparison dimension, its own operator line and its own
reasons for holding -- and it is the arm set that grows as triggers are
ratified, which is exactly why it must not grow inside the entry point.

A choice is either a destination or a hold that has ALREADY been reported: the
hold paths write their own lines and persist the state that ends the pass,
because the reason a candidate set came out empty is known only here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from _caam_rotation_span import switch_trigger
from caam_anthropic_finish import SaveState
from caam_candidate_diagnosis import CandidatePopulation
from caam_decide_context import DecisionContext
from caam_decide_report import (
    hold_allowed,
    hold_no_candidate,
    hold_reasons,
    hold_unsatisfiable_pin,
    trigger_line,
    with_note,
)
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    binding,
    eligible_profiles,
    five_hour_remaining_floor,
    rank_profiles,
    scoped_reserve,
    triggered,
)
from caam_expiring_quota import DRAIN_TRIGGER, drain_target, drain_trigger_line
from caam_scoped_model import scoped_model_pinned
from caam_scoped_selection import none_holds_scoped_above_reserve, scoped_alone_trigger

__all__: list[str] = [
    "RotationChoice",
    "RotationRequest",
    "rotation_choice",
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
    which trigger is making it, and whether the short-window threshold was among
    those that fired, which the expiring-quota drain remembers.
    """

    target: ProfileUsage | None
    decision_line: str = ""
    trigger: str = ""
    exit_code: int = 0
    short_window_triggered: bool = False


def rotation_choice(*, request: RotationRequest) -> RotationChoice:
    scoped_pin = scoped_model_pinned(state=request.context.state)
    threshold_triggered = triggered(
        usage=request.current,
        active_name=request.active_name,
        protection_floors=request.protection_floors,
        scoped_pin=scoped_pin,
    )
    if request.context.flags.force or threshold_triggered:
        return _triggered_choice(request=request, scoped_pin=scoped_pin)
    return _drain_choice(request=request, scoped_pin=scoped_pin)


def _drain_choice(*, request: RotationRequest, scoped_pin: bool) -> RotationChoice:
    """The lowest-precedence arm: drain weekly quota that expires sooner, or hold."""
    _dimension, remaining, label = binding(
        usage=request.current,
        active_name=request.active_name,
        protection_floors=request.protection_floors,
    )
    target = None
    if request.scheduled:
        target = drain_target(
            profiles=request.profiles,
            active=_active_account(request=request, scoped_pin=scoped_pin),
            protection_floors=request.protection_floors,
            state=request.context.state,
            now=request.context.now,
        )
    if target is None:
        return RotationChoice(
            target=None,
            exit_code=hold_allowed(
                context=request.context,
                save_state=request.save_state,
                label=label,
                remaining=remaining,
                current=request.current,
            ),
        )
    return RotationChoice(
        target=target,
        decision_line=drain_trigger_line(target=target, now=request.context.now),
        trigger=DRAIN_TRIGGER,
        short_window_triggered=_short_window_triggered(request=request),
    )


def _triggered_choice(*, request: RotationRequest, scoped_pin: bool) -> RotationChoice:
    """The arm every threshold and the forced pass share: rank, then take the best."""
    dimension, remaining, label = binding(
        usage=request.current,
        active_name=request.active_name,
        protection_floors=request.protection_floors,
    )
    # Provenance, not just capability: the hold below is licensed only where
    # the pin is the WHOLE reason this pass is leaving. A forced pass is
    # leaving because the operator said so, which is a reason of its own.
    scoped_alone = not request.context.flags.force and scoped_alone_trigger(
        usage=request.current,
        active_name=request.active_name,
        protection_floors=request.protection_floors,
        scoped_pin=scoped_pin,
    )
    decision_line = trigger_line(
        flags=request.context.flags,
        label=label,
        remaining=remaining,
        current=request.current,
        dimension=dimension,
    )
    eligible = eligible_profiles(
        profiles=request.profiles,
        active=_active_account(request=request, scoped_pin=scoped_pin),
        force=request.context.flags.force,
        dimension=dimension,
        protection_floors=request.protection_floors,
    )
    ranked = rank_profiles(profiles=eligible.profiles, scoped_pin=scoped_pin)
    pin_unsatisfiable = scoped_alone and none_holds_scoped_above_reserve(
        profiles=ranked, reserve=scoped_reserve()
    )
    reasons = hold_reasons(
        active_name=request.active_name,
        current=request.current,
        protection_floors=request.protection_floors,
        note=eligible.note,
        pin_unsatisfiable=pin_unsatisfiable,
    )
    if not ranked:
        return RotationChoice(
            target=None,
            exit_code=hold_no_candidate(
                context=request.context,
                save_state=request.save_state,
                decision_line=decision_line,
                population=CandidatePopulation(
                    profiles=request.profiles,
                    active_name=request.active_name,
                    dimension=dimension,
                    protection_floors=request.protection_floors,
                ),
                reasons=reasons,
            ),
        )
    if pin_unsatisfiable:
        return RotationChoice(
            target=None,
            exit_code=hold_unsatisfiable_pin(
                context=request.context,
                save_state=request.save_state,
                decision_line=decision_line,
                active_name=request.active_name,
                reasons=reasons,
            ),
        )
    return RotationChoice(
        target=ranked[0],
        decision_line=with_note(line=decision_line, note=eligible.note),
        # The dimension that BOUND is what made this pass leave, and it is
        # known only here -- the switch itself never sees why it was asked.
        trigger=switch_trigger(force=request.context.flags.force, dimension=dimension),
        short_window_triggered=_short_window_triggered(request=request),
    )


def _active_account(*, request: RotationRequest, scoped_pin: bool) -> ActiveAccount:
    return ActiveAccount(name=request.active_name, usage=request.current, scoped_pin=scoped_pin)


def _short_window_triggered(*, request: RotationRequest) -> bool:
    """Whether the short-window threshold was among the triggers that fired.

    Read on EVERY arm, the drain included, because the expiring-quota drain's
    condition (f) remembers the account a short-window move departed from
    whatever else was true of that pass.
    """
    return request.current.five_hour_remaining <= five_hour_remaining_floor()
