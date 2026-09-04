"""What a caam pass DOES with the panes discovery found: decide, act, and report.

``caam_sessions`` owns finding a pane and reading its model; this module owns the
decision taken from that read, the durable memos the decision consults, and the
``caam.enforcement.pane`` record it emits. The split is by concern, and the import
runs one way only -- discovery knows nothing about enforcement, and the type
reference back to ``SessionModel`` is a `TYPE_CHECKING` import so nothing is
circular at runtime (the same shape ``_supervisor_otel_async`` uses for
``Supervisor``).

One rule keeps enforcement from re-driving a pane that is already on the wanted
model (work-item overseer-o3t75c.1): an unknown (``None``) read is NOT evidence of
a mismatch. It authorises ONE verifying drive per session and wanted model --
remembered under the ``models_unknown`` state key, independently of the time-boxed
``models`` memo -- and never re-authorises one while the read stays unknown.
Settling the pane is left to the actuator, which dismisses the picker without
switching when the model is already correct (``caam_picker.PICKER_ALREADY_SET``).
A later KNOWN mismatch acts as usual and re-arms the verify.

Every pane a pass considers also produces ONE ``caam.enforcement.pane`` record on
the injected emission seam, naming the decision reached and the read it was
reached from (work-item overseer-m7qrgp.2). The record is emitted AT each branch
rather than derived from the returned messages, because three of the seven
decisions return no message at all, and because the two reasons a pass holds -- a
read that already agrees with the want, and a time-boxed suppression memo masking
a pane that never moved -- were one ``continue`` in the code and indistinguishable
from outside it.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol, cast

import jsonio
from _caam_pane_decision import (
    DECISION_BUSY,
    DECISION_DRIVE,
    DECISION_OPERATOR_SET_KEPT,
    DECISION_SKIP_ALREADY_SET,
    DECISION_SKIP_RECENTLY_SET,
    DECISION_SKIP_UNKNOWN_VERIFIED,
    DECISION_WOULD,
    PICKER_OUTCOME_ERROR,
    PaneEventEmitter,
    PaneOutcome,
    PaneSubject,
    pane_decision_record,
)

if TYPE_CHECKING:
    from caam_sessions import SessionModel

__all__: list[str] = [
    "ModelSetter",
    "PaneIdle",
    "enforce_session_models",
    "recently_set",
    "set_suppress_s",
]

_SET_SUPPRESS_DEFAULT_S: Final = "3600"
# The same advisory-error tuple `caam_enforcement` catches around a per-pane action.
# A drive that fails is REPORTED on the span and then allowed to continue to that
# handler, which is what turns it into the operator's `SKIPPED(<type>)` line; this
# module swallows nothing. Named types, not `except Exception`: the broad-catch gate
# grants a program exactly one boundary catch, in `main()`.
_DRIVE_ERRORS: Final = (OSError, RuntimeError, ValueError, TypeError, KeyError, IndexError)


class PaneIdle(Protocol):
    def __call__(self, *, session: str) -> bool: ...


class ModelSetter(Protocol):
    """Drives one pane to one model, answering with the actuator's own outcome.

    The answer is optional because a caller that only needs the pane moved (every
    test seam, and any future non-picker actuator) has nothing meaningful to say;
    the production setter returns the picker's verdict verbatim.
    """

    def __call__(self, *, session: str, model: str) -> str | None: ...


def set_suppress_s() -> float:
    return float(os.environ.get("CAAM_ROTATE_SET_SUPPRESS_S", _SET_SUPPRESS_DEFAULT_S))


def recently_set(*, state: dict[str, object], session: str, want: str, now: float) -> bool:
    models = jsonio.as_object(value=state.get("models")) or {}
    record = jsonio.as_object(value=models.get(session))
    if record is None or record.get("want") != want:
        return False
    at = jsonio.as_float(value=record.get("at"))
    return at is not None and now - at <= set_suppress_s()


# Mirrors caam_foreman_override.OBSERVED_MODELS_KEY, duplicated here rather than
# imported for the same reason that module duplicates the session-model keys: the
# dependency between them runs one way only.
_OBSERVED_MODELS_KEY = "observed_models"


def enforce_session_models(
    *,
    panes: tuple[SessionModel, ...],
    state: dict[str, object],
    want: str,
    now: float | None = None,
    set_model: ModelSetter,
    respect_operator_set: bool = False,
    **model_options: object,
) -> list[str]:
    checked_at = time.time() if now is None else now
    pane_idle = _pane_idle_option(options=model_options)
    dry_run = _bool_option(options=model_options, key="dry_run")
    reporter = _PaneReporter(emit=_emitter_option(options=model_options), want=want, at=checked_at)
    messages: list[str] = []
    # Per ratified v045 a session observed on the scoped model arms the rotation
    # trigger, and the decision runs after this pass; record every KNOWN observed
    # model, rebuilt from this pass alone so a session that went unreadable or
    # away stops arming rather than lingering on a stale reading.
    state[_OBSERVED_MODELS_KEY] = {
        pane.session: pane.model for pane in panes if pane.model is not None
    }
    for pane in panes:
        held = _held_decision(pane=pane, state=state, want=want, at=checked_at)
        if held is not None:
            reporter.report(pane=pane, decision=held)
            continue
        if respect_operator_set and _is_operator_set(
            state=state, session=pane.session, observed=pane.model
        ):
            messages.append(f"{pane.session} operator-set({pane.model}) kept")
            reporter.report(pane=pane, decision=DECISION_OPERATOR_SET_KEPT)
            continue
        model = pane.model or "unknown"
        if pane_idle is not None and not pane_idle(session=pane.session):
            messages.append(f"{pane.session} busy({model}->{want})")
            reporter.report(pane=pane, decision=DECISION_BUSY)
            continue
        if dry_run:
            messages.append(f"{pane.session} would {model}->{want}")
            reporter.report(pane=pane, decision=DECISION_WOULD)
            continue
        messages.append(
            _drive_pane(
                pane=pane,
                state=state,
                want=want,
                at=checked_at,
                set_model=set_model,
                reporter=reporter,
            )
        )
    return messages


def _held_decision(
    *, pane: SessionModel, state: dict[str, object], want: str, at: float
) -> str | None:
    """The reason this pass holds the pane, or None when it may still act on it.

    Three distinct reasons, evaluated in the order enforcement has always evaluated
    them. They used to be two ``continue``s carrying no distinction at all, which is
    the whole reason the decision is now named: a pane held because its read already
    agrees with the want and a pane held because a memo suppresses it look identical
    from outside, and only one of them is evidence the pane is actually on the model.
    """

    if pane.model == want:
        return DECISION_SKIP_ALREADY_SET
    if recently_set(state=state, session=pane.session, want=want, now=at):
        return DECISION_SKIP_RECENTLY_SET
    if pane.model is None and _unknown_verified(state=state, session=pane.session, want=want):
        return DECISION_SKIP_UNKNOWN_VERIFIED
    return None


def _drive_pane(
    *,
    pane: SessionModel,
    state: dict[str, object],
    want: str,
    at: float,
    set_model: ModelSetter,
    reporter: _PaneReporter,
) -> str:
    """Drive one pane to the wanted model, and report whatever the actuator answered.

    A drive that RAISES is reported first and then re-raised unchanged, so the span
    records the attempt while `caam_enforcement`'s per-pane handler still turns it into
    the operator's ``SKIPPED(<type>)`` line. Nothing is swallowed here.
    """

    try:
        outcome = set_model(session=pane.session, model=want)
    except _DRIVE_ERRORS:
        reporter.report(pane=pane, decision=DECISION_DRIVE, outcome=PICKER_OUTCOME_ERROR)
        raise
    _record_model_set(state=state, session=pane.session, want=want, now=at)
    _record_unknown_read(state=state, session=pane.session, want=want, unknown=pane.model is None)
    reporter.report(pane=pane, decision=DECISION_DRIVE, driven=True, outcome=outcome)
    return f"{pane.session} {pane.model or 'unknown'}->{want}"


@dataclass(frozen=True, kw_only=True)
class _PaneReporter:
    """The pass-wide half of a pane report, bound once so each branch states its own half.

    A closure over the loop variable would be the obvious alternative and is exactly
    what makes a per-branch report easy to get wrong: the branch that reports would no
    longer name the pane it is reporting on.
    """

    emit: PaneEventEmitter | None
    want: str
    at: float

    def report(
        self,
        *,
        pane: SessionModel,
        decision: str,
        driven: bool = False,
        outcome: str | None = None,
    ) -> None:
        if self.emit is None:
            return
        self.emit(
            record=pane_decision_record(
                subject=PaneSubject(
                    session=pane.session,
                    session_id=pane.session_id,
                    transcript=pane.transcript,
                    model_read=pane.model,
                    read_source=pane.source,
                ),
                outcome=PaneOutcome(
                    want=self.want,
                    decision=decision,
                    driven=driven,
                    picker_outcome=outcome,
                ),
                at=self.at,
            )
        )


def _record_model_set(*, state: dict[str, object], session: str, want: str, now: float) -> None:
    models = jsonio.as_object(value=state.get("models")) or {}
    state["models"] = models
    models[session] = {"want": want, "at": now}


def _is_operator_set(*, state: dict[str, object], session: str, observed: str | None) -> bool:
    """Whether a KNOWN observed model was set by the operator, not by enforcement.

    Called only after the observed model is known to differ from the wanted
    model. A session is operator-set when its observed model is known and
    differs from the model enforcement itself last set for it (its durable
    ``models`` record's ``want``). Two boundaries follow the ratified clause,
    which keys on "the model enforcement itself LAST SET": an unknown (None)
    observed model is never evidence of an operator choice; and a session with
    NO enforcement set-record has nothing for the observation to diverge from,
    so enforcement establishes its baseline (drives it) rather than reading the
    base default as a deliberate choice. Once enforcement has set a model, an
    observation that no longer matches it is the operator's own pick.
    """
    if observed is None:
        return False
    models = jsonio.as_object(value=state.get("models")) or {}
    record = jsonio.as_object(value=models.get(session))
    if record is None:
        return False
    return observed != record.get("want")


def _unknown_verified(*, state: dict[str, object], session: str, want: str) -> bool:
    verified = jsonio.as_object(value=state.get("models_unknown")) or {}
    return verified.get(session) == want


def _record_unknown_read(
    *, state: dict[str, object], session: str, want: str, unknown: bool
) -> None:
    verified = jsonio.as_object(value=state.get("models_unknown")) or {}
    state["models_unknown"] = verified
    if unknown:
        verified[session] = want
        return
    _ = verified.pop(session, None)


def _pane_idle_option(*, options: dict[str, object]) -> PaneIdle | None:
    value = options.get("pane_idle")
    return cast(PaneIdle, value) if callable(value) else None


def _emitter_option(*, options: dict[str, object]) -> PaneEventEmitter | None:
    value = options.get("emit_event")
    return cast(PaneEventEmitter, value) if callable(value) else None


def _bool_option(*, options: dict[str, object], key: str) -> bool:
    value = options.get(key)
    return value if isinstance(value, bool) else False
