"""Account decision and switch execution for caam account rotation."""
# livespec-lloc-soft-band-owner: overseer-4z97.2

from __future__ import annotations

from collections.abc import Mapping

from _caam_rotation_span import switch_trigger
from caam_candidate_diagnosis import CandidatePopulation
from caam_decide_context import (
    DecisionContext,
    DecisionSeams,
    Flags,
    SwitchAccount,
    UsageFetcher,
)
from caam_decide_report import (
    dry_run,
    hold_allowed,
    hold_no_candidate,
    hold_reasons,
    hold_unsatisfiable_pin,
    trigger_line,
    with_note,
)
from caam_decide_switch import SwitchPlan, switch_decision
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
    "DecisionContext",
    "DecisionSeams",
    "Flags",
    "SwitchAccount",
    "UsageFetcher",
    "decide",
]


def decide(
    *,
    context: DecisionContext,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    current: UsageRecord,
    protection_floors: Mapping[str, float],
    seams: DecisionSeams,
) -> int:
    scoped_pin = scoped_model_pinned(state=context.state)
    dimension, remaining, label = binding(
        usage=current,
        active_name=active_name,
        protection_floors=protection_floors,
    )
    threshold_triggered = triggered(
        usage=current,
        active_name=active_name,
        protection_floors=protection_floors,
        scoped_pin=scoped_pin,
    )
    normal_rotation = context.flags.force or threshold_triggered
    if not normal_rotation:
        target = None
        if seams.scheduled:
            target = drain_target(
                profiles=profiles,
                active=ActiveAccount(name=active_name, usage=current, scoped_pin=scoped_pin),
                protection_floors=protection_floors,
                state=context.state,
                now=context.now,
            )
        if target is None:
            return hold_allowed(
                context=context,
                save_state=seams.save_state,
                label=label,
                remaining=remaining,
                current=current,
            )
        decision_line = drain_trigger_line(target=target, now=context.now)
        switch_trigger_name = DRAIN_TRIGGER
    else:
        # Provenance, not just capability: the hold below is licensed only where
        # the pin is the WHOLE reason this pass is leaving. A forced pass is
        # leaving because the operator said so, which is a reason of its own.
        scoped_alone = not context.flags.force and scoped_alone_trigger(
            usage=current,
            active_name=active_name,
            protection_floors=protection_floors,
            scoped_pin=scoped_pin,
        )
        decision_line = trigger_line(
            flags=context.flags,
            label=label,
            remaining=remaining,
            current=current,
            dimension=dimension,
        )
        eligible = eligible_profiles(
            profiles=profiles,
            active=ActiveAccount(name=active_name, usage=current, scoped_pin=scoped_pin),
            force=context.flags.force,
            dimension=dimension,
            protection_floors=protection_floors,
        )
        ranked = rank_profiles(profiles=eligible.profiles, scoped_pin=scoped_pin)
        pin_unsatisfiable = scoped_alone and none_holds_scoped_above_reserve(
            profiles=ranked, reserve=scoped_reserve()
        )
        reasons = hold_reasons(
            active_name=active_name,
            current=current,
            protection_floors=protection_floors,
            note=eligible.note,
            pin_unsatisfiable=pin_unsatisfiable,
        )
        if not ranked:
            return hold_no_candidate(
                context=context,
                save_state=seams.save_state,
                decision_line=decision_line,
                population=CandidatePopulation(
                    profiles=profiles,
                    active_name=active_name,
                    dimension=dimension,
                    protection_floors=protection_floors,
                ),
                reasons=reasons,
            )
        if pin_unsatisfiable:
            return hold_unsatisfiable_pin(
                context=context,
                save_state=seams.save_state,
                decision_line=decision_line,
                active_name=active_name,
                reasons=reasons,
            )
        target = ranked[0]
        decision_line = with_note(line=decision_line, note=eligible.note)
        switch_trigger_name = switch_trigger(force=context.flags.force, dimension=dimension)
    if context.flags.dry_run:
        return dry_run(
            context=context,
            save_state=seams.save_state,
            decision_line=decision_line,
            active_name=active_name,
            target=target,
        )
    return switch_decision(
        context=context,
        plan=SwitchPlan(
            active_name=active_name,
            current=current,
            target=target,
            decision_line=decision_line,
            # The dimension that BOUND is what made this pass leave, and it is
            # known only here -- the switch itself never sees why it was asked.
            trigger=switch_trigger_name,
            short_window_triggered=current.five_hour_remaining <= five_hour_remaining_floor(),
        ),
        seams=seams,
    )
