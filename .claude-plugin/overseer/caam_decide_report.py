"""Every terminal outcome of a rotation pass that reports rather than switches.

A pass ends in one of two ways: it switches accounts, or it stops and says why.
This module owns the second kind end to end -- composing the operator-facing
lines and writing them out with the state save that ends the pass -- so that the
decision entry point beside it is left with the choice itself and the switch.

The hold reasons COMPOSE. Each condition that can hold a pass contributes one
reason to a tuple, and the tuple is appended to whichever hold line states the
cause; no condition brings a mechanism of its own. With an empty tuple every
line is byte-identical to the form that predates reasons.
"""

from __future__ import annotations

from collections.abc import Mapping

from caam_anthropic_finish import SaveState, finish
from caam_decide_context import DecisionContext, Flags
from caam_decision import (
    ProfileUsage,
    UsageRecord,
    decision_dry_run,
    decision_forced,
    decision_hold_allowance,
    decision_hold_no_candidate,
    decision_hold_unsatisfiable_pin,
    decision_trigger,
    five_hour_threshold,
    floor_breach,
    floor_breach_reason,
    min_headroom_gain,
    protection_floor_for,
    unsatisfiable_pin_reason,
    weekly_left,
    weekly_reserve,
)
from caam_target_summary import target_summary

__all__: list[str] = [
    "dry_run",
    "hold_allowed",
    "hold_no_candidate",
    "hold_reasons",
    "hold_unsatisfiable_pin",
    "trigger_line",
    "with_note",
]


def hold_allowed(
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
    return _report(context=context, save_state=save_state, lines=(line,))


def hold_no_candidate(
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
    return _report(context=context, save_state=save_state, lines=(decision_line, line))


def hold_unsatisfiable_pin(
    *,
    context: DecisionContext,
    save_state: SaveState,
    decision_line: str,
    active_name: str,
    reasons: tuple[str, ...] = (),
) -> int:
    """Hold where candidates exist but none of them can serve the pin.

    Distinct from the no-candidate hold because its cause is distinct: there
    ARE candidates clearing the headroom margin, and switching onto one would
    simply move the unsatisfiable pin somewhere else. Saying so on the
    no-candidate line would state something false about the candidate set.
    """
    line = decision_hold_unsatisfiable_pin(active_name=active_name, reasons=reasons)
    return _report(context=context, save_state=save_state, lines=(decision_line, line))


def dry_run(
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
    return _report(context=context, save_state=save_state, lines=(decision_line, line))


def with_note(*, line: str, note: str | None) -> str:
    """Append an eligibility note to a decision line, if there is one."""
    return line if note is None else f"{line}; {note}"


def hold_reasons(
    *,
    active_name: str,
    current: UsageRecord,
    protection_floors: Mapping[str, float],
    note: str | None,
    pin_unsatisfiable: bool = False,
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
    pin = unsatisfiable_pin_reason() if pin_unsatisfiable else None
    return tuple(reason for reason in (breach, pin, note) if reason is not None)


def trigger_line(
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


def _report(*, context: DecisionContext, save_state: SaveState, lines: tuple[str, ...]) -> int:
    return finish(
        code=0,
        state=context.state,
        state_path=context.state_path,
        save=save_state,
        stdout=context.stdout,
        lines=lines,
    )
