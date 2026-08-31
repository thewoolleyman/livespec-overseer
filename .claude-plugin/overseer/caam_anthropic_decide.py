"""Account decision and switch execution for caam account rotation."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from _caam_rotation_span import RotationOutcome, switch_trigger
from _caam_switch_host import acquire_switch_lock, caam_activate
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
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    binding,
    eligible_profiles,
    rank_profiles,
    triggered,
)
from caam_foreman_override import scoped_model_pinned
from caam_profile_state import caam_vault
from caam_profiles import active_profile
from caam_scoped_selection import none_can_serve_scoped_model, scoped_alone_trigger
from caam_switch import SwitchRequest

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
    dimension, spent, label = binding(
        usage=current,
        active_name=active_name,
        protection_floors=protection_floors,
    )
    if not context.flags.force and not triggered(
        usage=current,
        active_name=active_name,
        protection_floors=protection_floors,
        scoped_pin=scoped_pin,
    ):
        return hold_allowed(
            context=context,
            save_state=seams.save_state,
            label=label,
            spent=spent,
            current=current,
        )
    # Provenance, not just capability: the hold below is licensed only where the
    # pin is the WHOLE reason this pass is leaving. A forced pass is leaving
    # because the operator said so, which is a reason of its own.
    scoped_alone = not context.flags.force and scoped_alone_trigger(
        usage=current,
        active_name=active_name,
        protection_floors=protection_floors,
        scoped_pin=scoped_pin,
    )
    decision_line = trigger_line(
        flags=context.flags,
        label=label,
        spent=spent,
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
    pin_unsatisfiable = scoped_alone and none_can_serve_scoped_model(profiles=ranked)
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
    if context.flags.dry_run:
        return dry_run(
            context=context,
            save_state=seams.save_state,
            decision_line=with_note(line=decision_line, note=eligible.note),
            active_name=active_name,
            target=ranked[0],
        )
    return _switch_decision(
        context=context,
        plan=_SwitchPlan(
            active_name=active_name,
            current=current,
            target=ranked[0],
            decision_line=with_note(line=decision_line, note=eligible.note),
            # The dimension that BOUND is what made this pass leave, and it is
            # known only here -- the switch itself never sees why it was asked.
            trigger=switch_trigger(force=context.flags.force, dimension=dimension),
        ),
        seams=seams,
    )


@dataclass(frozen=True, kw_only=True)
class _SwitchPlan:
    """Everything the decision resolved, handed to the one step that executes it."""

    active_name: str
    current: UsageRecord
    target: ProfileUsage
    decision_line: str
    trigger: str


def _switch_decision(
    *,
    context: DecisionContext,
    plan: _SwitchPlan,
    seams: DecisionSeams,
) -> int:
    def save(*, state: dict[str, object]) -> None:
        seams.save_state(state=state, state_path=context.state_path)

    save(state=context.state)
    result = seams.switch_account(
        request=SwitchRequest(
            active_name=plan.active_name,
            target=plan.target,
            current=plan.current,
            state=context.state,
            home=context.home,
            now=context.now,
            active_reader=lambda: active_profile(
                live_account_path=context.home / ".claude.json",
                vault_path=caam_vault(home=context.home),
                caam_runner=_run_caam,
            ),
            fetcher=seams.fetcher,
            activator=caam_activate,
            lock_factory=acquire_switch_lock,
            save=save,
        )
    )
    for line in (plan.decision_line, *result.lines):
        context.stdout(line)
    # Emitted for a HOLD as well as a move: `switched` is the attribute that
    # separates them, and a record only on the moving path would leave the two
    # zero-exit holds invisible -- the exact shape an operator asks about.
    if seams.emit_rotation is not None:
        seams.emit_rotation(
            outcome=RotationOutcome(
                from_account=plan.active_name,
                to_account=plan.target.name,
                switched=result.switched,
                reason=result.reason,
                trigger=plan.trigger,
                exit_code=result.exit_code,
            )
        )
    # Carrier R13, and note it runs AFTER the outcome line: the operator reads
    # table, decision, outcome, corrected table. Keyed on `switched` rather than
    # on the exit code, because two holds also succeed with zero.
    if result.switched and seams.after_switch is not None:
        seams.after_switch(active_name=plan.target.name)
    return result.exit_code


def _run_caam(*, args: tuple[str, ...]):
    return caam_activate(args=args, timeout=60.0)
