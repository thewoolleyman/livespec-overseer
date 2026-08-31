"""The ROTATION half of caam observability: keeping accounts warm, and moving between them.

``_caam_pane_decision`` and ``_caam_pass_span`` cover the ENFORCEMENT half -- what a
pass decided about each foreman pane, and under what conditions. Neither says
anything about the other half of the same pass: whether the idle accounts rotation
depends on are still switchable, when the next keep-warm wake is due, and what
happened when the pass actually tried to move. Those are the questions an
exhausted-account incident starts from, and until now they existed only as operator
lines in a tmux scrollback.

TWO EVENTS, one per concern of that half (work-item overseer-m7qrgp.4):

  - ``caam.warm.schedule`` -- one per pass that reached its warm stage, covering
    BOTH ``keep_warm`` and ``emit_next_warm_wake``: what was attempted and what was
    refreshed, plus WHICH idle account expires soonest and WHEN its refresh is due.
    A pass whose warming was switched off emits one too, reporting
    ``caam.warm.maintained`` false, so a disabled warm stage is distinguishable
    from a healthy one that had nothing to do.

  - ``caam.rotation.switch`` -- one per attempted switch, whether or not it moved.
    ``caam.rotation.switched`` is the only attribute that says a credential actually
    changed: an exit code of zero does not, because a lock held by another pass and
    an active account that changed mid-decision both hold successfully.

THE VOCABULARY IS OWNED WHERE IT IS DECIDED, not derived from the operator message
-- the rule the pane record already keeps, and the reason this module accepts
``reason`` as a string rather than inferring one. ``caam_switch`` names its outcome
at the branch that reaches it (``REASON_*``), and this module ships that name. The
TRIGGER is the one exception it does compute, because "why was this pass leaving"
is a decision-layer fact rather than a switch-layer one: the operator's ``--force``,
or the usage dimension that bound.

BOTH RECORDS HANG FROM THE PASS SPAN, through the same ``linked_emitter`` the pane
records use, so a pass's enforcement decisions, its warm schedule and its switch are
one trace rather than three unrelated records.

ABSENT VALUES ARE NAMED, NEVER OMITTED. A pass with no idle account to wake for
reports ``none`` for both the profile and the wake rather than dropping the keys: a
span whose key set varies by branch cannot be grouped, and a missing attribute and
an attribute reading "none" are different queries.

THE WAKE IS AN ISO INSTANT, not the float ``next_warm_wake`` returns, and it is
built by ``_caam_span.iso_timestamp`` -- the same convention as every ``ts`` in this
family -- rather than by copying the coarser second-resolution stamp the operator
line prints. One timestamp format describes the wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

import _caam_span
from _caam_pass_span import PassSpan, linked_emitter
from caam_warm_records import WarmOutcome, WarmSchedule

__all__: list[str] = [
    "PROFILE_NONE",
    "ROTATION_SWITCH_EVENT",
    "TRIGGER_FORCE",
    "WAKE_NONE",
    "WARM_SCHEDULE_EVENT",
    "RotationOutcome",
    "RotationSink",
    "emit_warm_schedule",
    "rotation_record",
    "rotation_sink",
    "switch_trigger",
    "warm_record",
]

WARM_SCHEDULE_EVENT: Final = "caam.warm.schedule"
ROTATION_SWITCH_EVENT: Final = "caam.rotation.switch"

PROFILE_NONE: Final = "none"
WAKE_NONE: Final = "none"
TRIGGER_FORCE: Final = "force"


@dataclass(frozen=True, kw_only=True)
class RotationOutcome:
    """WHAT one attempted switch did, as the layers that know each part named it."""

    from_account: str
    to_account: str
    switched: bool
    reason: str
    trigger: str
    exit_code: int


class RotationSink(Protocol):
    """Where a finished switch record goes.

    Answers nothing, like every emitter in this family: the decision path must not
    be able to branch on whether telemetry reached a collector.
    """

    def __call__(self, *, outcome: RotationOutcome) -> None: ...


def warm_record(
    *, account: str, warm: WarmOutcome, schedule: WarmSchedule, at: float
) -> dict[str, object]:
    """The one record a pass emits about its warm stage."""

    return {
        "ts": _caam_span.iso_timestamp(at=at),
        "event": WARM_SCHEDULE_EVENT,
        "caam.account": account,
        "caam.warm.profile": PROFILE_NONE if schedule.profile is None else schedule.profile,
        "caam.warm.next_wake": _wake(wake=schedule.wake),
        "caam.warm.maintained": warm.maintained,
        "caam.warm.attempted": warm.attempted,
        "caam.warm.refreshed": warm.refreshed,
    }


def rotation_record(*, outcome: RotationOutcome, at: float) -> dict[str, object]:
    """The one record a pass emits about a switch it attempted.

    ``caam.account`` repeats the account being LEFT so a reader filtering the whole
    caam scope by account finds this record beside that pass's other spans; the
    from/to pair is what says where the rotation went.
    """

    return {
        "ts": _caam_span.iso_timestamp(at=at),
        "event": ROTATION_SWITCH_EVENT,
        "caam.account": outcome.from_account,
        "caam.rotation.from": outcome.from_account,
        "caam.rotation.to": outcome.to_account,
        "caam.rotation.switched": outcome.switched,
        "caam.rotation.reason": outcome.reason,
        "caam.rotation.trigger": outcome.trigger,
        "caam.exit_code": outcome.exit_code,
    }


def emit_warm_schedule(
    *, span: PassSpan, account: str, warm: WarmOutcome, schedule: WarmSchedule, at: float
) -> None:
    """Put this pass's warm record on the wire, under the pass's own trace."""

    emit = linked_emitter(emit=span.emit, trace=span.trace)
    emit(record=warm_record(account=account, warm=warm, schedule=schedule, at=at))


def rotation_sink(*, span: PassSpan, at: float) -> RotationSink:
    """A sink the decision path can hold without holding a trace or a transport.

    Bound once per pass, so the decision modules stay unaware of parentage exactly
    as the enforcement modules do: only the pass -- the one component that HAS a
    trace -- says where the record belongs.
    """

    emit = linked_emitter(emit=span.emit, trace=span.trace)

    def sink(*, outcome: RotationOutcome) -> None:
        emit(record=rotation_record(outcome=outcome, at=at))

    return sink


def switch_trigger(*, force: bool, dimension: str) -> str:
    """Why the pass was leaving: the operator said so, or a usage dimension bound.

    A forced pass has a binding dimension too -- ``binding`` always names one -- but
    reporting it would claim a threshold explained a move the operator ordered.
    """

    return TRIGGER_FORCE if force else dimension


def _wake(*, wake: float | None) -> str:
    return WAKE_NONE if wake is None else _caam_span.iso_timestamp(at=wake)
