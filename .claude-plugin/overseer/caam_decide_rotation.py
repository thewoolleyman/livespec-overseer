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

TRIGGER PRECEDENCE is read off this module's shape. The refusal trigger and its
dimension govern wherever it fires, because a refusal is ground truth about an
allowance while every other trigger reads a report about one; every threshold
and the forced pass share that same arm, which the binding parameterises; and
the expiring-quota drain remains the lowest, reachable only where nothing else
fired at all.
"""

from __future__ import annotations

from caam_decide_report import hold_allowed
from caam_decide_triggered import triggered_choice
from caam_decision import triggered
from caam_expiring_quota import DRAIN_TRIGGER, drain_target, drain_trigger_line
from caam_rotation_arm import (
    RotationArm,
    RotationChoice,
    RotationRequest,
    arm_active_account,
    arm_candidates,
    resolve_arm,
    short_window_triggered,
)

__all__: list[str] = [
    "RotationChoice",
    "RotationRequest",
    "rotation_choice",
]


def rotation_choice(*, request: RotationRequest) -> RotationChoice:
    arm = resolve_arm(request=request)
    threshold_triggered = triggered(
        usage=request.current,
        active_name=request.active_name,
        protection_floors=request.protection_floors,
        scoped_pin=arm.scoped_pin,
    )
    if request.context.flags.force or threshold_triggered or arm.refusal.holds_active:
        return triggered_choice(request=request, arm=arm)
    return _drain_choice(request=request, arm=arm)


def _drain_choice(*, request: RotationRequest, arm: RotationArm) -> RotationChoice:
    """The lowest-precedence arm: drain weekly quota that expires sooner, or hold."""
    target = None
    if request.scheduled:
        target = drain_target(
            profiles=arm_candidates(request=request, arm=arm),
            active=arm_active_account(request=request, arm=arm),
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
                label=arm.bound.label,
                remaining=arm.bound.remaining,
                current=request.current,
            ),
        )
    return RotationChoice(
        target=target,
        decision_line=drain_trigger_line(target=target, now=request.context.now),
        trigger=DRAIN_TRIGGER,
        short_window_triggered=short_window_triggered(request=request, arm=arm),
    )
