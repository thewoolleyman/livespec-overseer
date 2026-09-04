"""The ORCHESTRATED model policy: what a rotation pass wants each pane on, and why.

Split out of ``caam_enforcement`` (work-item overseer-m7qrgp.3), which crossed the
201-LLOC soft band when the pass span's facts report landed in it. The cut is by
cohesion: ``caam_enforcement`` orchestrates a pass -- resolve the context, discover
the panes, save the state, and honour ``--no-models`` -- while everything here is
the POLICY that pass applies when the caller passed an ``active_fable`` reading:
what the foremen want, which sessions are exceptions to it, whose operator-set
model survives, and what the pass therefore did.

That is also the seam the pass span sits on. These four conditions -- the Fable
balance, the foreman want, the pane count, and the exceptions in effect -- are
identical for every pane in a pass and are dropped entirely by the operator
message list, so they are reported to the pass on ``ModelContext.note_facts``
here, at the one point where all four are known.
"""

from __future__ import annotations

from typing import Final

from _caam_pass_span import PassFacts
from _signals_topics import is_foreman_topic, is_grooming_topic
from caam_enforcement_options import ModelContext, ModelRun
from caam_foreman_override import SCOPED_MODEL, apply_foreman_model_override
from caam_session_models import SessionModelExceptions, apply_session_model_exceptions
from caam_sessions import SessionModel, enforce_session_models

__all__: list[str] = [
    "enforce_orchestrated_models",
    "fable_left",
]

# The scoped balance at which the allowance is gone. `active_fable` is a percent
# REMAINING reading, like every other quota figure in the caam path, so
# exhaustion is zero rather than a full hundred spent. This constant is
# deliberately local: nothing here imports the decision core, and duplicating one
# named zero is cheaper than an import edge from enforcement into selection.
_FABLE_EXHAUSTED: Final = 0.0
# The same advisory-error tuple `caam_enforcement` catches around a pass, narrowed to
# the per-pane action this module takes. Named types, not `except Exception`: the
# broad-catch gate grants a program exactly one boundary catch, in `main()`.
_ADVISORY_ERRORS: Final = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)


def fable_left(*, active_fable: float | None) -> bool:
    """Whether the active account can still serve the scoped model.

    ``active_fable`` is the account's REMAINING scoped percentage, so the reading
    is "something left", mirroring ``can_serve_scoped_model`` over a usage record.
    One reading of one policy threshold, shared with the ``--no-models`` path in
    ``caam_enforcement`` so a pass that only persists an exception judges the
    balance exactly as an enforcing pass does.
    """
    return active_fable is not None and active_fable > _FABLE_EXHAUSTED


def enforce_orchestrated_models(
    *,
    panes: tuple[SessionModel, ...],
    context: ModelContext,
) -> list[str]:
    # Per ratified v045 the reading that decides the foreman default, the derived
    # want and operator-set respect is FLEET-WIDE selectable servability of the
    # scoped model when the rotation pass supplies it; the active account's own
    # balance remains the reading for every caller that supplies nothing.
    has_fable = (
        context.scoped_servable
        if context.scoped_servable is not None
        else fable_left(active_fable=context.active_fable)
    )
    foreman = apply_foreman_model_override(
        state=context.state,
        requested_model=context.foreman_model,
        default_model="fable" if has_fable else "opus",
        fable_left=has_fable,
    )
    session_exceptions = apply_session_model_exceptions(
        state=context.state,
        requested_models=context.session_models,
        fable_left=has_fable,
    )
    actions = [
        action
        for pane in panes
        for action in _actions_for_pane(
            pane=pane,
            state=context.state,
            fable_left=has_fable,
            want_foreman=foreman.want_foreman,
            session_exceptions=session_exceptions,
            run=context.run,
        )
    ]
    balance = "left" if has_fable else "EXHAUSTED"
    suffix = ", ".join(actions) if actions else "nothing to change"
    pinned = " [pinned]" if foreman.pinned else ""
    exceptions = session_exceptions.summary()
    summary_suffix = suffix if exceptions is None else f"{suffix}; {exceptions}"
    _note_pass_facts(
        context=context,
        has_fable=has_fable,
        want_foreman=foreman.want_foreman,
        pane_count=len(panes),
        exceptions=exceptions,
        outcome=suffix,
    )
    return [
        *session_exceptions.messages,
        *foreman.messages,
        f"models: foremen want {foreman.want_foreman}{pinned} "
        f"(active account Fable {balance}); {summary_suffix}",
    ]


def _note_pass_facts(
    *,
    context: ModelContext,
    has_fable: bool,
    want_foreman: str,
    pane_count: int,
    exceptions: str | None,
    outcome: str,
) -> None:
    """Hand the pass the four conditions only this function ever sees.

    A pass with no open span notes nothing, which is the ordinary case for a
    direct ``enforce_models`` caller and for every test that does not ask for
    telemetry.
    """
    if context.note_facts is None:
        return
    context.note_facts(
        facts=PassFacts(
            fable_left=has_fable,
            foreman_want=want_foreman,
            pane_count=pane_count,
            exceptions=exceptions,
            outcome=outcome,
        )
    )


def _actions_for_pane(
    *,
    pane: SessionModel,
    state: dict[str, object],
    fable_left: bool,
    want_foreman: str,
    session_exceptions: SessionModelExceptions,
    run: ModelRun,
) -> list[str]:
    want = session_exceptions.want_for(session=pane.session) or _wanted_model(
        session=pane.session, fable_left=fable_left, want_foreman=want_foreman
    )
    if want is None:
        return []
    try:
        return enforce_session_models(
            panes=(pane,),
            state=state,
            want=want,
            now=run.now,
            set_model=run.set_model,
            pane_idle=run.pane_idle,
            dry_run=run.dry_run,
            emit_event=run.emit_event,
            respect_operator_set=_respect_operator_set(
                pane=pane,
                scoped_servable=fable_left,
                session_exceptions=session_exceptions,
            ),
        )
    except _ADVISORY_ERRORS as exc:
        return [f"{pane.session} SKIPPED({type(exc).__name__})"]


def _respect_operator_set(
    *,
    pane: SessionModel,
    scoped_servable: bool,
    session_exceptions: SessionModelExceptions,
) -> bool:
    """Whether this session's operator-set model survives THIS pass.

    Two bounds, both from the ratified clause. An explicit ``session_models``
    pin is honored by DRIVING the session to it, so a pinned session is never
    left on something else -- that path is unchanged.

    The scoped-exhaustion exception is bounded to the session's OWN model and
    keyed on SERVABILITY, not on the global scoped-allowance-exhausted
    condition: enforcement moves an operator-set session only where no
    selectable account in the fleet can serve the model that session is
    actually on. ``scoped_servable`` is the pass's FLEET-WIDE
    scoped-servability reading -- what the caller supplies when the rotation
    pass has one, with the ACTIVE account's own scoped balance ("present and
    not fully spent", the same signal ``can_serve_scoped_model`` applies to a
    usage record for the scoped-model selection clauses) read only as the
    fallback -- and it can only disqualify a session observed on the scoped
    model itself. A session on any other model is untouched by that allowance
    being spent, so no servability concern reaches it and it is left alone; the
    exhausted pass resets the derived and never-operator-set sessions, and must
    not sweep this one up with them.

    An unknown observed model needs no branch here: it is never classified as
    operator-set downstream, so respecting it decides nothing.
    """
    if session_exceptions.want_for(session=pane.session) is not None:
        return False
    return scoped_servable or pane.model != SCOPED_MODEL


def _wanted_model(*, session: str, fable_left: bool, want_foreman: str) -> str | None:
    if is_foreman_topic(topic=session) or is_grooming_topic(topic=session):
        return want_foreman
    if not fable_left:
        return "opus"
    return None
