"""Fleet-wide scoped-model quota feeds caam enforcement and arms rotation (overseer-q3cvsv.6).

Per ratified SPECIFICATION v045 (the fable-quota-fleet-wide revision), "quota for
the scoped model" is FLEET-WIDE and keyed on selectability:

* Amendment A -- any tracked session currently observed running the scoped model
  arms the scoped-model rotation trigger exactly as a pin does. Enforcement
  therefore records every pane's observed model into durable state each pass,
  and ``scoped_model_pinned`` reads it, so ``decide()`` (which runs after
  enforcement in the same pass) sees an on-Fable session as an armed pin.
* Amendments B1/B2 -- a session on the scoped model is moved to the general model
  ONLY when no SELECTABLE account in the fleet can serve it. "Selectable" means an
  account rotation could actually choose: not excluded by a per-account
  protection floor, the zero-weekly disqualifier, the weekly-reserve rule, or
  the live-verification rule. The relative-headroom margin is deliberately NOT
  part of selectability (an independent ratification review ruled it out: the
  scoped waiver lifts the margin in exactly the stranding case). The ACTIVE
  account is never a candidate, so it always counts as selectable.

Before this change enforcement keyed the Fable->general move on the ACTIVE
account's ``fable_left`` alone, and the trigger was armed only by a literal pin,
so an unpinned session on default Fable was switched to the general model the
moment the active account's Fable was spent, even while another selectable
account could still serve it.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent


def _module(name: str) -> ModuleType:
    assert (ROOT / "overseer" / f"{name}.py").is_file()
    return importlib.import_module(name)


def _usage(*, five_hour: float, seven_day: float = 10.0, scoped: float | None) -> object:
    models = _module("caam_decision_models")
    return models.UsageRecord(
        five_hour_remaining=100.0 - five_hour,
        seven_day_remaining=100.0 - seven_day,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None if scoped is None else 100.0 - scoped,
        fable_resets_at=None,
    )


def _live(*, name: str, record: object) -> object:
    models = _module("caam_decision_models")
    return models.ProfileUsage(name=name, source="live", usage=record)


def _pane(session: str, model: str | None) -> object:
    sessions = _module("caam_sessions")
    return sessions.SessionModel(session=session, session_id=f"sid-{session}", model=model)


# ---------------------------------------------------------------------------
# Amendment A -- arming by an observed on-scoped-model session.
# ---------------------------------------------------------------------------


def test_scoped_model_pinned_is_armed_by_a_session_observed_on_the_scoped_model() -> None:
    override = _module("caam_foreman_override")

    state: dict[str, object] = {"observed_models": {"poweredge-raid-array": "fable"}}

    assert override.scoped_model_pinned(state=state) is True


def test_scoped_model_pinned_is_not_armed_by_sessions_observed_on_other_models() -> None:
    override = _module("caam_foreman_override")

    state: dict[str, object] = {"observed_models": {"alpha-worker": "opus", "beta": "sonnet"}}

    assert override.scoped_model_pinned(state=state) is False


def test_enforcement_records_every_known_observed_model_into_state() -> None:
    sessions = _module("caam_sessions")
    state: dict[str, object] = {}

    _ = sessions.enforce_session_models(
        panes=(_pane("alpha", "fable"), _pane("beta", "opus"), _pane("gamma", None)),
        state=state,
        want="opus",
        now=1000.0,
        set_model=lambda **_: None,
        pane_idle=lambda **_: True,
    )

    # An unknown read arms nothing and is never recorded as a model.
    assert state["observed_models"] == {"alpha": "fable", "beta": "opus"}


# ---------------------------------------------------------------------------
# Amendments B1/B2 -- fleet-wide selectable servability of the scoped model.
# ---------------------------------------------------------------------------


def test_fleet_wide_servable_when_a_selectable_candidate_can_serve() -> None:
    selection = _module("caam_scoped_selection")
    spent_active = _usage(five_hour=40.0, scoped=100.0)
    can_serve = _live(name="other", record=_usage(five_hour=20.0, seven_day=10.0, scoped=42.0))

    assert (
        selection.scoped_servable_fleet_wide(
            profiles=(can_serve,),
            active_name="active",
            current=spent_active,
            protection_floors={},
        )
        is True
    )


def test_fleet_wide_servable_when_the_active_account_itself_can_serve() -> None:
    selection = _module("caam_scoped_selection")

    assert (
        selection.scoped_servable_fleet_wide(
            profiles=(),
            active_name="active",
            current=_usage(five_hour=40.0, scoped=42.0),
            protection_floors={},
        )
        is True
    )


def test_fleet_wide_unservable_when_no_account_can_serve() -> None:
    selection = _module("caam_scoped_selection")
    spent = _live(name="other", record=_usage(five_hour=20.0, seven_day=10.0, scoped=100.0))

    assert (
        selection.scoped_servable_fleet_wide(
            profiles=(spent,),
            active_name="active",
            current=_usage(five_hour=40.0, scoped=100.0),
            protection_floors={},
        )
        is False
    )


def test_fleet_wide_unservable_when_fable_exists_only_on_a_floor_breaching_account() -> None:
    """The protection floor outranks using Fable: an at-floor holder never counts."""
    selection = _module("caam_scoped_selection")
    at_its_floor = _live(
        name="protected", record=_usage(five_hour=50.0, seven_day=90.0, scoped=0.0)
    )

    assert (
        selection.scoped_servable_fleet_wide(
            profiles=(at_its_floor,),
            active_name="active",
            current=_usage(five_hour=40.0, scoped=100.0),
            protection_floors={"protected": 10.0},
        )
        is False
    )


def test_fleet_wide_unservable_when_the_only_holder_is_not_live_verified() -> None:
    selection = _module("caam_scoped_selection")
    models = _module("caam_decision_models")
    cached = models.ProfileUsage(
        name="cached", source="cached 2.0h", usage=_usage(five_hour=20.0, scoped=0.0)
    )

    assert (
        selection.scoped_servable_fleet_wide(
            profiles=(cached,),
            active_name="active",
            current=_usage(five_hour=40.0, scoped=100.0),
            protection_floors={},
        )
        is False
    )


def test_fleet_wide_servability_ignores_the_headroom_margin_for_a_fable_capable_candidate() -> None:
    """Selectability is floor/zero-weekly/reserve/live-verification -- never the margin."""
    selection = _module("caam_scoped_selection")
    # Worse short-window headroom than the active account (more spent), which the
    # relative-headroom margin would refuse -- but it can serve Fable, so it counts.
    worse_headroom = _live(name="other", record=_usage(five_hour=90.0, seven_day=10.0, scoped=42.0))

    assert (
        selection.scoped_servable_fleet_wide(
            profiles=(worse_headroom,),
            active_name="active",
            current=_usage(five_hour=40.0, scoped=100.0),
            protection_floors={},
        )
        is True
    )


# ---------------------------------------------------------------------------
# The orchestrated path consults the fleet-wide reading, not the active account.
# ---------------------------------------------------------------------------


def _enforce(*, calls: list[tuple[str, str]], active_fable: float, **extra: object) -> object:
    enforcement = _module("caam_enforcement")
    state: dict[str, object] = {}
    return enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=Path("/tmp/does-not-matter-state.json"),
        session_names=("alpha-worker",),
        active_fable=active_fable,
        foreman_model=None,
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "fable",
        pane_idle=lambda **_: True,
        set_model=lambda **kw: calls.append((str(kw["session"]), str(kw["model"]))),
        state=state,
        **extra,
    )


def test_a_fable_session_is_left_alone_when_the_scoped_model_is_servable_fleet_wide() -> None:
    """Active account spent, but a selectable account can serve: rotation, not a model change."""
    calls: list[tuple[str, str]] = []

    _ = _enforce(calls=calls, active_fable=0.0, scoped_servable=True)

    assert calls == []


def test_a_fable_session_is_moved_when_the_scoped_model_is_unservable_fleet_wide() -> None:
    calls: list[tuple[str, str]] = []

    _ = _enforce(calls=calls, active_fable=0.0, scoped_servable=False)

    assert calls == [("alpha-worker", "opus")]


def test_without_a_fleet_wide_reading_the_active_account_reading_still_governs() -> None:
    """Every caller that passes no fleet-wide reading keeps the pre-change behaviour."""
    calls: list[tuple[str, str]] = []

    _ = _enforce(calls=calls, active_fable=0.0)

    assert calls == [("alpha-worker", "opus")]
