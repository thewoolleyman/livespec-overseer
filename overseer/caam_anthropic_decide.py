"""Account decision and switch execution for caam account rotation."""
# livespec-lloc-soft-band-owner: overseer-4z97.2

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from _caam_rotation_span import RotationOutcome
from _caam_switch_host import acquire_switch_lock, caam_activate
from caam_decide_context import (
    DecisionContext,
    DecisionSeams,
    Flags,
    SwitchAccount,
    UsageFetcher,
)
from caam_decide_report import dry_run
from caam_decide_rotation import RotationRequest, rotation_choice
from caam_decision import ProfileUsage, UsageRecord
from caam_expiring_quota import (
    DRAIN_TRIGGER,
    drain_switch_line,
    remember_short_window_departure,
)
from caam_profile_state import caam_vault
from caam_profiles import active_profile
from caam_switch import REASON_HOLD_LOCK_HELD, SwitchRequest

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
    choice = rotation_choice(
        request=RotationRequest(
            context=context,
            profiles=profiles,
            active_name=active_name,
            current=current,
            protection_floors=protection_floors,
            scheduled=seams.scheduled,
            save_state=seams.save_state,
        )
    )
    # The arm has already written its own hold lines and persisted the state that
    # ends the pass, because the reason a candidate set came out empty is known
    # only where the set was built.
    if choice.target is None:
        return choice.exit_code
    if context.flags.dry_run:
        return dry_run(
            context=context,
            save_state=seams.save_state,
            decision_line=choice.decision_line,
            active_name=active_name,
            target=choice.target,
        )
    return _switch_decision(
        context=context,
        plan=_SwitchPlan(
            active_name=active_name,
            current=current,
            target=choice.target,
            decision_line=choice.decision_line,
            trigger=choice.trigger,
            short_window_triggered=choice.short_window_triggered,
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
    short_window_triggered: bool


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
            active_reader=lambda: _active_name(home=context.home),
            fetcher=seams.fetcher,
            activator=caam_activate,
            lock_factory=acquire_switch_lock,
            save=save,
        )
    )
    # The ONE outcome in which this pass never held the lock, and therefore never
    # owned the decision it was about to record. Reported from the reason rather
    # than from the exit code, which a lock contention shares with an ordinary
    # successful hold.
    if seams.lock_contended is not None and result.reason == REASON_HOLD_LOCK_HELD:
        seams.lock_contended()
    if result.switched and plan.short_window_triggered:
        remember_short_window_departure(
            state=context.state,
            account=plan.active_name,
            resets_at_value=plan.current.five_hour_resets_at,
        )
        save(state=context.state)
    result_lines = (
        (drain_switch_line(active_name=plan.active_name, target=plan.target, now=context.now),)
        if result.switched and plan.trigger == DRAIN_TRIGGER
        else result.lines
    )
    for line in (plan.decision_line, *result_lines):
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


def _active_name(*, home: Path) -> str | None:
    """The active profile's NAME, for the re-read taken while holding the lock.

    That read exists to catch the decision's premise changing beneath it, which
    the name alone settles: the identity of the account this pass determined was
    resolved once, where it was determined, and re-resolving it here would answer
    a question nobody asked at this point in the sequence.
    """

    active = active_profile(
        live_account_path=home / ".claude.json",
        vault_path=caam_vault(home=home),
        caam_runner=_run_caam,
    )
    return None if active is None else active.profile


def _run_caam(*, args: tuple[str, ...]):
    return caam_activate(args=args, timeout=60.0)
