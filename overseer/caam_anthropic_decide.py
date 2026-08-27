"""Account decision and switch execution for caam account rotation."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi

from __future__ import annotations

from collections.abc import Mapping

from _caam_switch_host import acquire_switch_lock, caam_activate
from caam_anthropic_finish import SaveState, finish
from caam_decide_context import (
    DecisionContext,
    DecisionSeams,
    Flags,
    SwitchAccount,
    UsageFetcher,
)
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    binding,
    decision_dry_run,
    decision_forced,
    decision_hold_allowance,
    decision_hold_no_candidate,
    decision_trigger,
    eligible_profiles,
    five_hour_threshold,
    floor_breach,
    floor_breach_reason,
    min_headroom_gain,
    protection_floor_for,
    rank_profiles,
    triggered,
    weekly_left,
    weekly_reserve,
)
from caam_foreman_override import scoped_model_pinned
from caam_profile_state import caam_vault
from caam_profiles import active_profile
from caam_switch import SwitchRequest
from caam_target_summary import target_summary

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
        return _hold_allowed(
            context=context,
            save_state=seams.save_state,
            label=label,
            spent=spent,
            current=current,
        )
    decision_line = _trigger_line(
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
    if not ranked:
        return _hold_no_candidate(
            context=context,
            save_state=seams.save_state,
            decision_line=decision_line,
            dimension=dimension,
            active_name=active_name,
            reasons=_hold_reasons(
                active_name=active_name,
                current=current,
                protection_floors=protection_floors,
                note=eligible.note,
            ),
        )
    if context.flags.dry_run:
        return _dry_run(
            context=context,
            save_state=seams.save_state,
            decision_line=_with_note(line=decision_line, note=eligible.note),
            active_name=active_name,
            target=ranked[0],
        )
    return _switch_decision(
        context=context,
        active_name=active_name,
        current=current,
        target=ranked[0],
        decision_line=_with_note(line=decision_line, note=eligible.note),
        seams=seams,
    )


def _hold_allowed(
    *,
    context: DecisionContext,
    save_state: SaveState,
    label: str,
    spent: float,
    current: UsageRecord,
) -> int:
    line = decision_hold_allowance(
        label=label,
        spent=spent,
        weekly_remaining=weekly_left(usage=current),
        reserve=weekly_reserve(),
    )
    return finish(
        code=0,
        state=context.state,
        state_path=context.state_path,
        save=save_state,
        stdout=context.stdout,
        lines=(line,),
    )


def _hold_no_candidate(
    *,
    context: DecisionContext,
    save_state: SaveState,
    decision_line: str,
    dimension: str,
    active_name: str,
    reasons: tuple[str, ...] = (),
) -> int:
    line = decision_hold_no_candidate(
        gain_needed=0.01 if context.flags.force else min_headroom_gain(),
        dimension=dimension,
        active_name=active_name,
        reasons=reasons,
    )
    return finish(
        code=0,
        state=context.state,
        state_path=context.state_path,
        save=save_state,
        stdout=context.stdout,
        lines=(decision_line, line),
    )


def _with_note(*, line: str, note: str | None) -> str:
    """Append an eligibility note to a decision line, if there is one."""
    return line if note is None else f"{line}; {note}"


def _hold_reasons(
    *,
    active_name: str,
    current: UsageRecord,
    protection_floors: Mapping[str, float],
    note: str | None,
) -> tuple[str, ...]:
    """Every reason this pass can give for holding, in the order they are reported."""
    breach = floor_breach_reason(
        active_name=active_name,
        breached_floor=floor_breach(
            usage=current,
            protection_floor=protection_floor_for(
                name=active_name, protection_floors=protection_floors
            ),
        ),
    )
    return tuple(reason for reason in (breach, note) if reason is not None)


def _dry_run(
    *,
    context: DecisionContext,
    save_state: SaveState,
    decision_line: str,
    active_name: str,
    target: ProfileUsage,
) -> int:
    line = decision_dry_run(
        active_name=active_name,
        target=target_summary(target=target, now=context.now),
    )
    return finish(
        code=0,
        state=context.state,
        state_path=context.state_path,
        save=save_state,
        stdout=context.stdout,
        lines=(decision_line, line),
    )


def _switch_decision(
    *,
    context: DecisionContext,
    active_name: str,
    current: UsageRecord,
    target: ProfileUsage,
    decision_line: str,
    seams: DecisionSeams,
) -> int:
    def save(*, state: dict[str, object]) -> None:
        seams.save_state(state=state, state_path=context.state_path)

    save(state=context.state)
    result = seams.switch_account(
        request=SwitchRequest(
            active_name=active_name,
            target=target,
            current=current,
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
    for line in (decision_line, *result.lines):
        context.stdout(line)
    return result.exit_code


def _trigger_line(
    *, flags: Flags, label: str, spent: float, current: UsageRecord, dimension: str
) -> str:
    if flags.force:
        return decision_forced(threshold=five_hour_threshold())
    return decision_trigger(
        label=label,
        spent=spent,
        weekly_remaining=weekly_left(usage=current),
        dimension=dimension,
    )


def _run_caam(*, args: tuple[str, ...]):
    return caam_activate(args=args, timeout=60.0)
