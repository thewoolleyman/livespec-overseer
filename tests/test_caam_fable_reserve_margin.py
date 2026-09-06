"""The scoped-model RESERVE margin (work-item overseer-dyt6), end-to-end through ``decide()``.

The 2026-09-06 incident was not that the machinery is Fable-blind -- SPECIFICATION
v045 and the shipped code already rotate a Fable-dependent session off an account
that CANNOT serve Fable. The defect is that "cannot serve" is a zero-remaining
boundary with no margin: the active account drained Fable to 1% while idle accounts
held 57-69%, and because 1% > 0 the scoped trigger never armed, so the pass HELD and
the Fable session was starved. ``tests/test_caam_observed_fable_rotation_incident.py``
pins the fully-spent boundary; THIS file pins the configurable remaining-margin
(``CAAM_ROTATE_FABLE_REMAINING``, default 15) that moves BEFORE exhaustion, its
reduction to the ratified boundary at reserve 0, and the anti-oscillation rule that a
margin-triggered move only lands on an account holding Fable strictly above the reserve.

Every figure here is a percentage REMAINING, the direction the operation stores,
prints and compares.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord
from caam_foreman_override import OBSERVED_MODELS_KEY

__all__: list[str] = []


def _usage(
    *,
    fable_remaining: float | None,
    five_hour_remaining: float,
    seven_day_remaining: float,
    seven_day_resets_at: str | None = None,
) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five_hour_remaining,
        seven_day_remaining=seven_day_remaining,
        five_hour_resets_at=None,
        seven_day_resets_at=seven_day_resets_at,
        fable_remaining=fable_remaining,
        fable_resets_at=None,
    )


def _incident_active(*, fable_remaining: float) -> UsageRecord:
    """anthropic-1 at the incident: quiet on 5-hour and weekly, low on Fable.

    So being at or below the scoped-model reserve on Fable is the SOLE reason the
    pass would leave -- the incident's shape.
    """
    return _usage(
        fable_remaining=fable_remaining, five_hour_remaining=49.0, seven_day_remaining=42.0
    )


@dataclass(frozen=True, kw_only=True)
class _SwitchResult:
    lines: tuple[str, ...]
    exit_code: int
    switched: bool = True


class _Flags:
    def __init__(self) -> None:
        self.force = False
        self.dry_run = False


class _Context:
    def __init__(self, *, home: Path, observed: dict[str, str]) -> None:
        self.flags = _Flags()
        self.home = home
        self.now = 1_788_000_000.0
        self.state: dict[str, object] = {OBSERVED_MODELS_KEY: observed}
        self.state_path = home / "state.json"
        self.lines: list[str] = []

    def stdout(self, line: str) -> None:
        self.lines.append(line)


class _Outcome:
    def __init__(self) -> None:
        self.switched_to: str | None = None

    @property
    def held(self) -> bool:
        return self.switched_to is None


def _run(
    *,
    tmp_path: Path,
    active: UsageRecord,
    candidates: tuple[ProfileUsage, ...],
    observed: dict[str, str],
    protection_floors: dict[str, float] | None = None,
) -> _Outcome:
    outcome = _Outcome()
    context = _Context(home=tmp_path, observed=observed)

    def _switch(*, request: object) -> _SwitchResult:
        outcome.switched_to = request.target.name  # type: ignore[attr-defined]
        return _SwitchResult(lines=("SWITCHED",), exit_code=0)

    decide(
        context=context,
        profiles=(ProfileUsage(name="anthropic-1", source="live", usage=active), *candidates),
        active_name="anthropic-1",
        current=active,
        protection_floors=protection_floors or {},
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used"),
            save_state=lambda **_: None,
            switch_account=_switch,
        ),
    )
    return outcome


def _holder(
    *,
    name: str,
    fable_remaining: float,
    five_hour_remaining: float = 85.0,
    seven_day_resets_at: str | None = None,
) -> ProfileUsage:
    return ProfileUsage(
        name=name,
        source="live",
        usage=_usage(
            fable_remaining=fable_remaining,
            five_hour_remaining=five_hour_remaining,
            seven_day_remaining=76.0,
            seven_day_resets_at=seven_day_resets_at,
        ),
    )


# (a) THE INCIDENT, under the default reserve: active Fable 1% (>0, so v045 held),
# an observed Fable session, and an above-reserve holder -> rotate to it.
def test_active_below_the_reserve_rotates_to_an_above_reserve_holder(tmp_path: Path) -> None:
    outcome = _run(
        tmp_path=tmp_path,
        active=_incident_active(fable_remaining=1.0),
        candidates=(_holder(name="anthropic-3", fable_remaining=57.0),),
        observed={"livespec-dev-tooling-foreman": "fable"},
    )
    assert outcome.switched_to == "anthropic-3", (
        "active Fable at 1% is at or below the default reserve (15%); with a session "
        f"observed on Fable and an above-reserve holder, the pass must move. held={outcome.held}"
    )


# (b) Reserve 0 restores the exact ratified boundary: the same inputs HOLD, because
# only a fully-spent active can trigger on scoped grounds.
def test_reserve_zero_restores_the_cannot_serve_only_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAAM_ROTATE_FABLE_REMAINING", "0")
    outcome = _run(
        tmp_path=tmp_path,
        active=_incident_active(fable_remaining=1.0),
        candidates=(_holder(name="anthropic-3", fable_remaining=57.0),),
        observed={"livespec-dev-tooling-foreman": "fable"},
    )
    assert outcome.held, (
        "at reserve 0 a still-serving active (Fable 1% > 0) must not trigger on scoped "
        f"grounds; switched_to={outcome.switched_to}"
    )


# (c) No Fable-dependent session -> no scoped trigger at any Fable level, so weekly is
# never stranded for accounts that have no Fable sessions.
def test_no_observed_fable_session_never_triggers_on_the_reserve(tmp_path: Path) -> None:
    outcome = _run(
        tmp_path=tmp_path,
        active=_incident_active(fable_remaining=1.0),
        candidates=(_holder(name="anthropic-3", fable_remaining=57.0),),
        observed={},
    )
    assert outcome.held, (
        "with no session on Fable the reserve must not arm; a quiet active must stay put "
        f"rather than strand weekly. switched_to={outcome.switched_to}"
    )


# (d) Anti-oscillation via ranking: a below-reserve holder reachable by the ordinary
# 5-hour margin, with a SOONER weekly reset, must NOT out-rank a genuine above-reserve
# holder -- otherwise the move lands on an account that immediately re-triggers.
def test_an_above_reserve_holder_outranks_a_below_reserve_one_reachable_by_margin(
    tmp_path: Path,
) -> None:
    below = _holder(
        name="anthropic-below",
        fable_remaining=8.0,  # below the default reserve
        five_hour_remaining=95.0,  # clears the ordinary headroom margin over active (49%)
        seven_day_resets_at="2026-09-08T00:00:00Z",  # sooner -> would win under can-serve ties
    )
    above = _holder(
        name="anthropic-above",
        fable_remaining=57.0,  # above the reserve
        five_hour_remaining=20.0,  # admitted via the scoped waiver, not the margin
        seven_day_resets_at="2026-09-11T00:00:00Z",  # later
    )
    outcome = _run(
        tmp_path=tmp_path,
        active=_incident_active(fable_remaining=1.0),
        candidates=(below, above),
        observed={"livespec-dev-tooling-foreman": "fable"},
    )
    assert outcome.switched_to == "anthropic-above", (
        "a reserve-triggered move must prefer an above-reserve holder over a below-reserve "
        f"one, even one with a sooner weekly reset. switched_to={outcome.switched_to}"
    )


# (e) Anti-oscillation via hold: when the reserve is the sole reason to leave and the
# only Fable-capable candidate is itself at or below the reserve, HOLD rather than move
# onto an account that would immediately re-trigger.
def test_holds_when_no_candidate_holds_fable_above_the_reserve(tmp_path: Path) -> None:
    outcome = _run(
        tmp_path=tmp_path,
        active=_incident_active(fable_remaining=1.0),
        candidates=(
            _holder(name="anthropic-below", fable_remaining=8.0, five_hour_remaining=95.0),
        ),
        observed={"livespec-dev-tooling-foreman": "fable"},
    )
    assert outcome.held, (
        "no candidate holds Fable above the reserve, so a reserve-alone trigger must hold "
        f"rather than move onto a below-reserve account. switched_to={outcome.switched_to}"
    )


# (f) The protection floor is honored under a reserve-driven selection: an above-reserve
# Fable holder that is protected and at its floor is never selected to serve the pin.
def test_protected_at_floor_holder_is_not_selected_under_the_reserve(tmp_path: Path) -> None:
    protected = ProfileUsage(
        name="anthropic-0",
        source="live",
        usage=_usage(fable_remaining=57.0, five_hour_remaining=85.0, seven_day_remaining=8.0),
    )
    outcome = _run(
        tmp_path=tmp_path,
        active=_incident_active(fable_remaining=1.0),
        candidates=(protected,),
        observed={"livespec-dev-tooling-foreman": "fable"},
        protection_floors={"anthropic-0": 10.0},
    )
    assert outcome.held, (
        "a protected account at or below its floor must never be selected even to serve the "
        f"pin under the reserve. switched_to={outcome.switched_to}"
    )
