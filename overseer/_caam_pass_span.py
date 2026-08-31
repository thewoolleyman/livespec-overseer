"""One caam rotation PASS as one span, and the trace its pane spans hang from.

``_caam_pane_decision`` names what a pass decided about ONE pane;
``_caam_span`` puts a record on the wire. This module is the third piece: what
the pass as a whole was, and the parentage that binds the two together.

WHY A PASS SPAN, given the per-pane spans already exist (work-item
overseer-m7qrgp.2). A pane span answers "what did enforcement decide here"; it
cannot answer "under what conditions". The 2026-08-30/31
"livespec-overseer-foreman unknown->fable" incident turned on conditions the
pane spans never carry: which account was active, whether that account still had
Fable, what the foremen were therefore wanted on, and whether a `session_models`
exception was in effect. Those are properties of the PASS, identical for every
pane in it, and duplicating them onto each pane span would both bloat the record
and lose the very grouping -- one pass -- that makes them meaningful.

EXACTLY ONE RECORD PER PASS, INCLUDING A PASS THAT DID NOTHING. ``run_pass``
opens the span before it resolves anything and closes it on every return, so an
empty vault and an unresolved active profile are as visible as a full enforcing
pass. A span emitted only from the enforcing branch would be silent in precisely
the cases an operator is trying to explain.

ABSENT VALUES ARE NAMED, NEVER OMITTED -- the same rule as the pane record, and
here it is load-bearing rather than tidy. A pass that never reached enforcement
has no reading of the Fable balance at all, and reporting that as ``false``
would be a fabricated measurement indistinguishable from a genuine exhaustion.
So the balance carries its own ``unknown``, and ``caam.enforcement.reached``
states outright whether the enforcement-derived attributes mean anything.

THE CLOCK IS INJECTED AND USED TWICE: once at open for the record's ``ts``, once
at close for ``caam.wall_clock_seconds``. It is the pass's WALL clock rather
than a monotonic one because the two readings must be commensurable with the
timestamp the span is filed under, and a rotation pass is far too short for the
extra precision of a second clock source to buy anything.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

import _caam_span

__all__: list[str] = [
    "ACCOUNT_NONE",
    "EXCEPTIONS_NONE",
    "FABLE_EXHAUSTED",
    "FABLE_LEFT",
    "FABLE_UNKNOWN",
    "FOREMAN_WANT_NONE",
    "OUTCOME_NOT_REACHED",
    "ROTATION_EVENT",
    "Clock",
    "PassEventEmitter",
    "PassFacts",
    "PassFactsSink",
    "PassSpan",
    "PassTrace",
    "linked_emitter",
    "open_pass_span",
]

# Named for the rotation rather than for the "pass" this module otherwise calls it:
# ruff's S105 reads any CONSTANT whose name contains "PASS" as a hardcoded credential,
# and the wire name below is the one that has to stay stable, not the binding.
ROTATION_EVENT: Final = "caam.enforcement.pass"

ACCOUNT_NONE: Final = "none"
EXCEPTIONS_NONE: Final = "none"
FOREMAN_WANT_NONE: Final = "none"
FABLE_LEFT: Final = "left"
FABLE_EXHAUSTED: Final = "exhausted"
FABLE_UNKNOWN: Final = "unknown"
OUTCOME_NOT_REACHED: Final = "enforcement-not-reached"

_TRACE_ID_BYTES: Final = 16
_SPAN_ID_BYTES: Final = 8


class Clock(Protocol):
    def __call__(self) -> float: ...


class PassEventEmitter(Protocol):
    """Where a finished pass record goes.

    Structurally identical to ``_caam_pane_decision.PaneEventEmitter``, and named
    apart from it on purpose: the two carry different events, and one seam
    (``_caam_span_seam.emitter_from_env``) satisfies both without either having
    to claim the other's vocabulary. Like the pane emitter it answers nothing,
    so a pass can never branch on whether telemetry reached a collector.
    """

    def __call__(self, *, record: Mapping[str, object]) -> None: ...


@dataclass(frozen=True, kw_only=True)
class PassTrace:
    """The trace one pass and all of its pane decisions share."""

    trace_id: str
    span_id: str


@dataclass(frozen=True, kw_only=True)
class PassFacts:
    """What model enforcement observed, reported back to the pass that ran it.

    These four conditions are computed deep inside ``caam_enforcement`` and are
    invisible to ``run_pass``, which is why they travel back on a sink rather
    than a return value: enforcement's return type is the operator's message
    list, and widening it to carry telemetry would put a wire concern in the
    middle of the rotation table.
    """

    fable_left: bool
    foreman_want: str
    pane_count: int
    exceptions: str | None
    outcome: str


class PassFactsSink(Protocol):
    def __call__(self, *, facts: PassFacts) -> None: ...


@dataclass(kw_only=True)
class PassSpan:
    """One open pass span, accumulating what the pass learns as it learns it.

    Deliberately mutable, unlike every other record type in the caam span
    modules. The account is known only once the vault resolves it, and the
    enforcement facts only once enforcement runs -- both AFTER the span has to
    exist, because the span's whole job is to also cover the passes that never
    get that far.
    """

    trace: PassTrace
    started: float
    dry_run: bool
    clock: Clock
    emit: PassEventEmitter
    account: str | None = None
    facts: PassFacts | None = None

    def note_account(self, *, name: str) -> None:
        self.account = name

    def note_facts(self, *, facts: PassFacts) -> None:
        self.facts = facts

    def close(self, *, code: int) -> None:
        """Emit the pass's one record, whatever the pass managed to observe."""

        facts = self.facts
        self.emit(
            record={
                "ts": _caam_span.iso_timestamp(at=self.started),
                "event": ROTATION_EVENT,
                _caam_span.TRACE_ID_KEY: self.trace.trace_id,
                _caam_span.SPAN_ID_KEY: self.trace.span_id,
                "caam.account": ACCOUNT_NONE if self.account is None else self.account,
                "caam.enforcement.reached": facts is not None,
                "caam.fable.balance": _balance(facts=facts),
                "model.want.foreman": FOREMAN_WANT_NONE if facts is None else facts.foreman_want,
                "caam.pane.count": 0 if facts is None else facts.pane_count,
                "caam.session_models.exceptions": _exceptions(facts=facts),
                "caam.outcome": OUTCOME_NOT_REACHED if facts is None else facts.outcome,
                "caam.exit_code": code,
                "caam.wall_clock_seconds": self.clock() - self.started,
                "caam.dry_run": self.dry_run,
            }
        )


def open_pass_span(*, dry_run: bool, clock: Clock, emit: PassEventEmitter) -> PassSpan:
    """Mint the pass's trace and start its clock, before anything is resolved."""

    return PassSpan(
        trace=PassTrace(
            trace_id=secrets.token_hex(_TRACE_ID_BYTES),
            span_id=secrets.token_hex(_SPAN_ID_BYTES),
        ),
        started=clock(),
        dry_run=dry_run,
        clock=clock,
        emit=emit,
    )


def linked_emitter(*, emit: PassEventEmitter, trace: PassTrace) -> PassEventEmitter:
    """The same emitter, hanging everything it carries under one pass span.

    Wrapping the emitter is what keeps the linkage out of the decision modules:
    ``_caam_session_enforce`` still builds a pane record that knows nothing about
    traces, and only the pass -- the one component that HAS a trace -- says where
    that record belongs.
    """

    def linked(*, record: Mapping[str, object]) -> None:
        emit(
            record={
                **record,
                _caam_span.TRACE_ID_KEY: trace.trace_id,
                _caam_span.PARENT_SPAN_ID_KEY: trace.span_id,
            }
        )

    return linked


def _balance(*, facts: PassFacts | None) -> str:
    if facts is None:
        return FABLE_UNKNOWN
    return FABLE_LEFT if facts.fable_left else FABLE_EXHAUSTED


def _exceptions(*, facts: PassFacts | None) -> str:
    if facts is None or facts.exceptions is None:
        return EXCEPTIONS_NONE
    return facts.exceptions
