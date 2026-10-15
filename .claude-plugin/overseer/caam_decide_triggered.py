"""The arm every threshold, the forced pass and the refusal trigger share.

One shape serves all three because they differ only in what BOUND: the dimension
candidates are compared on, the active account's standing on it, and the line
that states the reason. The refusal trigger supplies all three through the arm's
binding, where the active account's headroom is already taken as zero, so
nothing below this point needs to know that a refusal is what fired.
"""

from __future__ import annotations

from _caam_rotation_span import switch_trigger
from caam_candidate_diagnosis import CandidatePopulation
from caam_decide_report import (
    hold_no_candidate,
    hold_reasons,
    hold_unsatisfiable_pin,
    trigger_line,
    with_note,
)
from caam_decision import eligible_profiles, rank_profiles, scoped_reserve
from caam_refusal_lines import REFUSAL_TRIGGER, refusal_trigger_line
from caam_rotation_arm import (
    RotationArm,
    RotationChoice,
    RotationRequest,
    arm_active_account,
    short_window_triggered,
)
from caam_scoped_selection import none_holds_scoped_above_reserve, scoped_alone_trigger

__all__: list[str] = [
    "triggered_choice",
]


def triggered_choice(*, request: RotationRequest, arm: RotationArm) -> RotationChoice:
    # Provenance, not just capability: the hold below is licensed only where
    # the pin is the WHOLE reason this pass is leaving. A forced pass is
    # leaving because the operator said so, which is a reason of its own, and a
    # refusing account is being left on ground truth rather than on the pin.
    scoped_alone = (
        not request.context.flags.force
        and not arm.refusal.holds_active
        and scoped_alone_trigger(
            usage=request.current,
            active_name=request.active_name,
            protection_floors=request.protection_floors,
            scoped_pin=arm.scoped_pin,
        )
    )
    decision_line = _decision_line(request=request, arm=arm)
    eligible = eligible_profiles(
        profiles=request.profiles,
        active=arm_active_account(request=request, arm=arm),
        force=request.context.flags.force,
        dimension=arm.bound.dimension,
        protection_floors=request.protection_floors,
    )
    ranked = rank_profiles(profiles=eligible.profiles, scoped_pin=arm.scoped_pin)
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
                    dimension=arm.bound.dimension,
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
        trigger=_switch_trigger_name(request=request, arm=arm),
        short_window_triggered=short_window_triggered(request=request, arm=arm),
    )


def _decision_line(*, request: RotationRequest, arm: RotationArm) -> str:
    if arm.refusal.active is not None:
        return refusal_trigger_line(remembered=arm.refusal.active)
    return trigger_line(
        flags=request.context.flags,
        label=arm.bound.label,
        remaining=arm.bound.remaining,
        current=request.current,
        dimension=arm.bound.dimension,
    )


def _switch_trigger_name(*, request: RotationRequest, arm: RotationArm) -> str:
    if arm.refusal.holds_active:
        return REFUSAL_TRIGGER
    return switch_trigger(force=request.context.flags.force, dimension=arm.bound.dimension)
