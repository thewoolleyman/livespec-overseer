"""The arm every threshold, the forced pass and the refusal trigger share.

One shape serves all three because they differ only in what BOUND: the dimension
candidates are compared on, the active account's standing on it, and the line
that states the reason. The refusal trigger supplies all three through the arm's
binding, where the active account's headroom is already taken as zero, so
nothing below this point needs to know that a refusal is what fired.

The fast-drain trigger shares it too, and shares MORE of it than the others:
it compares candidates on the same short-window dimension the binding already
names, and it relaxes no rule, so only the three facts it states in its own
words differ -- the line that says why the pass is leaving, the trigger name
the switch record carries, and the projection its switch line states. A
`projection` here is therefore both those words and the fact that the
fast-drain trigger is what GOVERNED, which the caller has already decided by
precedence before it calls.

What does differ is how a HOLD reads. A refusing account with no replacement is
a different situation from an ordinary empty candidate set -- the fleet is
sitting on an account that serves nothing -- so it gets its own line.
"""

from __future__ import annotations

from _caam_rotation_span import switch_trigger
from caam_candidate_diagnosis import CandidatePopulation
from caam_capacity_select import capacity_selection
from caam_decide_report import (
    hold_no_candidate,
    hold_no_capacity,
    hold_reasons,
    hold_refusing,
    hold_unsatisfiable_pin,
    trigger_line,
    with_note,
)
from caam_decision import (
    eligible_profiles,
    five_hour_remaining_floor,
    rank_profiles,
    scoped_reserve,
)
from caam_fast_drain import FAST_DRAIN_TRIGGER, ShortWindowProjection, fast_drain_trigger_line
from caam_refusal_lines import REFUSAL_TRIGGER, refusal_exclusion_reason, refusal_trigger_line
from caam_rotation_arm import (
    RotationArm,
    RotationChoice,
    RotationRequest,
    arm_active_account,
    arm_candidates,
    short_window_triggered,
)
from caam_scoped_selection import none_holds_scoped_above_reserve, scoped_alone_trigger
from caam_weekly_reserve import weekly_reserve_decision

__all__: list[str] = [
    "triggered_choice",
]


def triggered_choice(
    *,
    request: RotationRequest,
    arm: RotationArm,
    projection: ShortWindowProjection | None = None,
) -> RotationChoice:
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
    decision_line = _decision_line(request=request, arm=arm, projection=projection)
    active = arm_active_account(request=request, arm=arm)
    candidates = arm_candidates(request=request, arm=arm)
    reserve = weekly_reserve_decision(
        profiles=request.profiles,
        candidates=candidates,
        active=active,
        force=request.context.flags.force,
        dimension=arm.bound.dimension,
        protection_floors=request.protection_floors,
        load=arm.load,
        active_fast_draining=projection is not None,
    )
    # A released reserve never turns a candidate at the short-window floor into
    # a destination.  Such a row was relevant to deciding that the reserve
    # protects nothing, but it cannot carry a request through the next pass.
    if not reserve.enforce:
        candidates = tuple(
            profile
            for profile in candidates
            if profile.usage is not None
            and profile.usage.five_hour_remaining > five_hour_remaining_floor()
        )
    eligible = eligible_profiles(
        profiles=candidates,
        active=active,
        force=request.context.flags.force,
        dimension=arm.bound.dimension,
        protection_floors=request.protection_floors,
        enforce_reserve=reserve.enforce,
        reserve_note=reserve.note,
    )
    # Preserve the established empty-set diagnosis until the reporting slice can
    # distinguish a release-only hold from the legacy all-under-reserve case.
    # A populated released set always carries the serveability decision's note.
    if not eligible.profiles:
        eligible = eligible_profiles(
            profiles=candidates,
            active=active,
            force=request.context.flags.force,
            dimension=arm.bound.dimension,
            protection_floors=request.protection_floors,
        )
    # The capacity test runs AFTER the ranking rather than inside it: ranking is
    # a perishability order with no capacity term in it, and the test is an
    # eligibility rule that happens to read a capacity weight. Filtering a
    # ranked tuple preserves the order the ranking chose.
    selection = capacity_selection(
        profiles=rank_profiles(profiles=eligible.profiles, scoped_pin=arm.scoped_pin),
        load=arm.load,
        refusal_held=arm.refusal.holds_active,
    )
    ranked = selection.profiles
    pin_unsatisfiable = scoped_alone and none_holds_scoped_above_reserve(
        profiles=ranked, reserve=scoped_reserve()
    )
    reasons = hold_reasons(
        active_name=request.active_name,
        current=request.current,
        protection_floors=request.protection_floors,
        note=eligible.note,
        pin_unsatisfiable=pin_unsatisfiable,
        refusal_excluded=refusal_exclusion_reason(
            holding=arm.refusal.holding, active_name=request.active_name
        ),
    )
    # Ahead of the empty-set hold, which this case would otherwise fall into
    # wearing the wrong diagnosis: the set was NOT empty, and every account in
    # it cleared every gate that hold's cause reports on.
    if selection.excluded_every:
        return RotationChoice(
            target=None,
            exit_code=hold_no_capacity(
                context=request.context,
                save_state=request.save_state,
                decision_line=decision_line,
                reasons=reasons,
            ),
        )
    if not ranked:
        return RotationChoice(
            target=None,
            exit_code=_hold_empty_set(
                request=request, arm=arm, decision_line=decision_line, reasons=reasons
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
        trigger=_switch_trigger_name(request=request, arm=arm, projection=projection),
        short_window_triggered=short_window_triggered(
            request=request, arm=arm, projection=projection
        ),
        refusal=arm.refusal.active,
        projection=projection,
    )


def _decision_line(
    *,
    request: RotationRequest,
    arm: RotationArm,
    projection: ShortWindowProjection | None,
) -> str:
    if arm.refusal.active is not None:
        return refusal_trigger_line(remembered=arm.refusal.active)
    if projection is not None:
        return fast_drain_trigger_line(
            active_name=request.active_name, current=request.current, projection=projection
        )
    return trigger_line(
        flags=request.context.flags,
        label=arm.bound.label,
        remaining=arm.bound.remaining,
        current=request.current,
        dimension=arm.bound.dimension,
    )


def _switch_trigger_name(
    *,
    request: RotationRequest,
    arm: RotationArm,
    projection: ShortWindowProjection | None,
) -> str:
    if arm.refusal.holds_active:
        return REFUSAL_TRIGGER
    if projection is not None:
        return FAST_DRAIN_TRIGGER
    return switch_trigger(force=request.context.flags.force, dimension=arm.bound.dimension)


def _hold_empty_set(
    *,
    request: RotationRequest,
    arm: RotationArm,
    decision_line: str,
    reasons: tuple[str, ...],
) -> int:
    # The WHOLE vault, not the set the refusal hold left: the diagnosis names
    # the gate that emptied the candidate set, and the hold is one of them. Fed
    # only what survived it, it reads a held account as one that was never there
    # and says so beside a table that still lists its figures.
    population = CandidatePopulation(
        profiles=request.profiles,
        active_name=request.active_name,
        dimension=arm.bound.dimension,
        protection_floors=request.protection_floors,
        refusal_held=arm.refusal.held,
    )
    if arm.refusal.holds_active:
        return hold_refusing(
            context=request.context,
            save_state=request.save_state,
            decision_line=decision_line,
            active_name=request.active_name,
            population=population,
            reasons=reasons,
        )
    return hold_no_candidate(
        context=request.context,
        save_state=request.save_state,
        decision_line=decision_line,
        population=population,
        reasons=reasons,
    )
