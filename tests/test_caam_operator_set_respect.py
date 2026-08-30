"""caam enforcement respects an operator-set per-session model (overseer-q3cvsv.2/.4).

Per ratified SPECIFICATION v043: model enforcement MUST NOT re-drive a session
observed on a KNOWN non-default model that enforcement did not itself assign,
distinguished from enforcement's own durable ``models`` set-record. The single
exception is bounded to the session's OWN model and keyed on SERVABILITY: where
the active account cannot serve the model an operator set a session to,
enforcement moves it to the general model; an operator-set model the account CAN
serve is left alone even while the scoped (Fable) allowance is unavailable.
``respect_operator_set`` is therefore decided PER SESSION by the orchestrator
(v043 tightened v040, under which the whole path was gated globally on
``fable_left`` and an exhausted pass reset every operator-set session).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent


def sessions_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_sessions.py").is_file()
    return importlib.import_module("caam_sessions")


def enforcement_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_enforcement.py").is_file()
    return importlib.import_module("caam_enforcement")


def options_module() -> ModuleType:
    return importlib.import_module("caam_enforcement_options")


def session_models_module() -> ModuleType:
    return importlib.import_module("caam_session_models")


def _run(calls: list[tuple[str, str]], *, now: float):
    options = options_module()

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    def pane_idle(*, session: str) -> bool:
        _ = session
        return True

    return options.ModelRun(now=now, set_model=set_model, pane_idle=pane_idle, dry_run=False)


# ---------------------------------------------------------------------------
# enforce_session_models -- the respect_operator_set contract (cases a-d).
# ---------------------------------------------------------------------------


def test_respect_with_no_prior_enforcement_record_establishes_the_baseline() -> None:
    """With no set-record to diverge from, enforcement drives to the wanted model.

    The ratified clause keys on "the model enforcement itself last set"; a
    never-enforced session has no such record, so the base default model is not
    read as a deliberate operator choice -- enforcement establishes the baseline.
    """
    module = sessions_module()
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {}
    pane = module.SessionModel(session="alpha-foreman", session_id="sid", model="opus")

    messages = module.enforce_session_models(
        panes=(pane,),
        state=state,
        want="fable",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        respect_operator_set=True,
    )

    assert calls == [("alpha-foreman", "fable")]
    assert messages == ["alpha-foreman opus->fable"]


def test_respect_leaves_a_session_the_operator_moved_off_the_enforced_model() -> None:
    module = sessions_module()
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {"models": {"alpha-foreman": {"want": "fable", "at": 500.0}}}
    pane = module.SessionModel(session="alpha-foreman", session_id="sid", model="opus")

    messages = module.enforce_session_models(
        panes=(pane,),
        state=state,
        want="fable",
        now=1_000_000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        respect_operator_set=True,
    )

    assert calls == []
    assert messages == ["alpha-foreman operator-set(opus) kept"]


def test_respect_still_enforces_a_session_matching_the_last_enforced_model() -> None:
    module = sessions_module()
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {"models": {"alpha-foreman": {"want": "opus", "at": 500.0}}}
    pane = module.SessionModel(session="alpha-foreman", session_id="sid", model="opus")

    messages = module.enforce_session_models(
        panes=(pane,),
        state=state,
        want="fable",
        now=1_000_000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        respect_operator_set=True,
    )

    assert calls == [("alpha-foreman", "fable")]
    assert messages == ["alpha-foreman opus->fable"]


def test_respect_does_not_classify_an_unknown_read_as_operator_set() -> None:
    module = sessions_module()
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {}
    pane = module.SessionModel(session="alpha-foreman", session_id="sid", model=None)

    messages = module.enforce_session_models(
        panes=(pane,),
        state=state,
        want="fable",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        respect_operator_set=True,
    )

    assert calls == [("alpha-foreman", "fable")]
    assert messages == ["alpha-foreman unknown->fable"]


def test_without_respect_the_fable_exhausted_exception_still_moves_a_session() -> None:
    module = sessions_module()
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {}
    pane = module.SessionModel(session="alpha-foreman", session_id="sid", model="fable")

    messages = module.enforce_session_models(
        panes=(pane,),
        state=state,
        want="opus",
        now=1000.0,
        set_model=lambda *, session, model: calls.append((session, model)),
        respect_operator_set=False,
    )

    assert calls == [("alpha-foreman", "opus")]
    assert messages == ["alpha-foreman fable->opus"]


# ---------------------------------------------------------------------------
# Orchestration wiring -- respect is decided PER SESSION: the session carries no
# explicit session_models pin (an explicit pin is honored by driving to it) AND
# the active account can still serve the session's own observed model.
# ---------------------------------------------------------------------------


def test_orchestration_skips_an_operator_set_derived_session_while_fable_is_left() -> None:
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(values={}, messages=())
    calls: list[tuple[str, str]] = []
    # Enforcement last set this session to fable; the operator has since moved it
    # to opus (e.g. Opus 5 1M for a long-context task), which reads as `opus`.
    state: dict[str, object] = {"models": {"alpha-foreman": {"want": "fable", "at": 500.0}}}
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid", model="opus")

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=True,
        want_foreman="fable",
        session_exceptions=exceptions,
        run=_run(calls, now=1_000_000.0),
    )

    assert calls == []
    assert actions == ["alpha-foreman operator-set(opus) kept"]


def test_orchestration_still_drives_a_session_models_pinned_session_to_its_pin() -> None:
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(
        values={"alpha-foreman": "fable"}, messages=()
    )
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {}
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid", model="opus")

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=True,
        want_foreman="fable",
        session_exceptions=exceptions,
        run=_run(calls, now=1000.0),
    )

    assert calls == [("alpha-foreman", "fable")]
    assert actions == ["alpha-foreman opus->fable"]


def test_orchestration_moves_an_operator_set_session_when_fable_is_exhausted() -> None:
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(values={}, messages=())
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {}
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid", model="fable")

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=False,
        want_foreman="opus",
        session_exceptions=exceptions,
        run=_run(calls, now=1000.0),
    )

    assert calls == [("alpha-foreman", "opus")]
    assert actions == ["alpha-foreman fable->opus"]


# ---------------------------------------------------------------------------
# Servability bounds the exhaustion exception per session (overseer-q3cvsv.4).
# ---------------------------------------------------------------------------


def test_exhaustion_leaves_an_operator_set_session_on_a_servable_model() -> None:
    """A spent Fable allowance says nothing about a session the operator put on sonnet.

    Enforcement last set this worker to fable; the operator has since moved it
    to sonnet. The active account can serve sonnet, so the exception the spent
    scoped allowance opens does not reach this session and it is left alone.
    """
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(values={}, messages=())
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {"models": {"alpha-worker": {"want": "fable", "at": 500.0}}}
    pane = sessions.SessionModel(session="alpha-worker", session_id="sid", model="sonnet")

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=False,
        want_foreman="opus",
        session_exceptions=exceptions,
        run=_run(calls, now=1_000_000.0),
    )

    assert calls == []
    assert actions == ["alpha-worker operator-set(sonnet) kept"]


def test_exhaustion_leaves_an_operator_set_opus_session_under_a_fable_foreman_pin() -> None:
    """The servable-model case the exhausted pass used to drive onto a blocked model.

    With the foreman override pinned to fable and that allowance spent, the
    derived want is fable. An operator-set opus session is servable, so it is
    kept rather than driven onto the model the account cannot currently serve.
    """
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(values={}, messages=())
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {"models": {"alpha-foreman": {"want": "fable", "at": 500.0}}}
    pane = sessions.SessionModel(session="alpha-foreman", session_id="sid", model="opus")

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=False,
        want_foreman="fable",
        session_exceptions=exceptions,
        run=_run(calls, now=1_000_000.0),
    )

    assert calls == []
    assert actions == ["alpha-foreman operator-set(opus) kept"]


def test_exhaustion_moves_an_operator_set_session_off_the_unservable_scoped_model() -> None:
    """The bounded exception itself: the session's OWN model is what became unservable."""
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(values={}, messages=())
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {"models": {"alpha-worker": {"want": "opus", "at": 500.0}}}
    pane = sessions.SessionModel(session="alpha-worker", session_id="sid", model="fable")

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=False,
        want_foreman="opus",
        session_exceptions=exceptions,
        run=_run(calls, now=1_000_000.0),
    )

    assert calls == [("alpha-worker", "opus")]
    assert actions == ["alpha-worker fable->opus"]


def test_exhaustion_still_never_classifies_an_unknown_read_as_operator_set() -> None:
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(values={}, messages=())
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {"models": {"alpha-worker": {"want": "fable", "at": 500.0}}}
    pane = sessions.SessionModel(session="alpha-worker", session_id="sid", model=None)

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=False,
        want_foreman="opus",
        session_exceptions=exceptions,
        run=_run(calls, now=1_000_000.0),
    )

    assert calls == [("alpha-worker", "opus")]
    assert actions == ["alpha-worker unknown->opus"]


def test_a_session_models_pin_still_wins_over_a_servable_operator_set_model() -> None:
    """Servability widens nothing for an explicitly pinned session -- #2045 unchanged."""
    enforcement = enforcement_module()
    sessions = sessions_module()
    exceptions = session_models_module().SessionModelExceptions(
        values={"alpha-worker": "opus"}, messages=()
    )
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {"models": {"alpha-worker": {"want": "fable", "at": 500.0}}}
    pane = sessions.SessionModel(session="alpha-worker", session_id="sid", model="sonnet")

    actions = enforcement._actions_for_pane(
        pane=pane,
        state=state,
        fable_left=False,
        want_foreman="opus",
        session_exceptions=exceptions,
        run=_run(calls, now=1_000_000.0),
    )

    assert calls == [("alpha-worker", "opus")]
    assert actions == ["alpha-worker sonnet->opus"]
