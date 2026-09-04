"""Outcome-level pins for the quota predicates the "remaining everywhere" flip will rewrite.

`plan/quota-percentages-say-remaining/research/used-versus-remaining.md` records the
maintainer ruling that these percentages must say REMAINING in labels and in keys,
and names option (b) -- store remaining -- as what that literally asks for. Option
(b) inverts every comparison in the selection path at once: `can_serve_scoped_model`,
`fable_left`, `weekly_left`, the `_FULLY_SPENT` / `_FABLE_EXHAUSTED` sentinels and the
short-window threshold tests all flip together, and a single missed inversion silently
reverses a rotation rule.

This file is the safety net that makes the flip PROVABLY outcome-preserving, covering
the predicates the blast-radius inventory found with no direct coverage:
`raw_weekly_left` (through the floor-breach report it produces), `scoped_waiver_ceiling`,
each leg of `triggered`, `scoped_alone_trigger`, and all four exhaustion-sentinel
comparisons.

TWO PROPERTIES MAKE IT SURVIVE THE FLIP UNCHANGED, and both are load-bearing:

* **Every assertion is about a DECISION OUTCOME** -- does this account rotate, is this
  candidate eligible, can this account serve the pin, is a breach reported, is the hold
  licensed -- never about the direction a field stores. Nothing here asserts a stored
  percentage, and the one figure it does assert (`floor_breach`'s reported remaining) is
  already a REMAINING quantity today and stays one after the flip.
* **Every input goes through ONE seam**, `stored_reading`, which is the only place in
  this file that knows which direction a record stores. After the flip its body becomes
  `return remaining` and not one test above it changes.

Figures are therefore written as REMAINING throughout, and deliberately stay well clear
of the configured thresholds (85 spent / 15 remaining short-window, 10 weekly reserve):
a threshold's own NUMBER may move with the representation, so a test pressed against the
boundary would be pinning the constant rather than the outcome. The exhaustion boundary
IS pinned, because "nothing left" is zero remaining under either representation.
"""

from __future__ import annotations

from math import inf

import pytest
from caam_candidate_diagnosis import CandidatePopulation, no_candidate_cause
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    binding,
    can_serve_scoped_model,
    eligible_profiles,
    five_hour_threshold,
    floor_breach,
    is_eligible,
    scoped_waiver_ceiling,
    triggered,
)
from caam_enforcement_orchestrated import fable_left
from caam_scoped_selection import scoped_alone_trigger

__all__: list[str] = []

_RESETS_AT = "2026-09-06T12:00:00Z"
_FULL_ALLOWANCE = 100.0


def stored_reading(*, remaining: float) -> float:
    """THE ONE PLACE that knows which direction a usage figure is stored in.

    Today the records hold percent SPENT, so a reading with `remaining` left is
    stored as its complement. When the "remaining everywhere" flip lands this body
    becomes `return remaining` and every test in this file keeps passing untouched --
    which is the whole point of routing every input through here.
    """
    return _FULL_ALLOWANCE - remaining


def account(
    *,
    short_window_remaining: float,
    weekly_remaining: float = 80.0,
    scoped_remaining: float | None = 100.0,
) -> UsageRecord:
    """A usage record described by what each allowance has LEFT.

    `scoped_remaining=None` is the distinct "the scoped allowance could not be read
    at all" case, which the predicates must treat as unable to serve rather than as
    fully available.
    """
    return UsageRecord(
        five_hour=stored_reading(remaining=short_window_remaining),
        seven_day=stored_reading(remaining=weekly_remaining),
        five_hour_resets_at=_RESETS_AT,
        seven_day_resets_at=_RESETS_AT,
        fable=None if scoped_remaining is None else stored_reading(remaining=scoped_remaining),
        fable_resets_at=_RESETS_AT,
    )


def live(*, name: str, record: UsageRecord) -> ProfileUsage:
    return ProfileUsage(name=name, source="live", usage=record)


def admitted(*, profiles: tuple[ProfileUsage, ...], active: ActiveAccount) -> list[str]:
    """The names selection would actually move onto -- the servability outcome."""
    return [
        profile.name
        for profile in eligible_profiles(
            profiles=profiles,
            active=active,
            force=False,
            dimension="five_hour",
        ).profiles
    ]


# ---------------------------------------------------------------------------
# The rotation trigger -- one test per leg, each judged by "does it rotate?".
# ---------------------------------------------------------------------------


def test_an_account_with_room_on_every_allowance_does_not_rotate():
    assert not triggered(usage=account(short_window_remaining=60.0, weekly_remaining=80.0))


def test_an_account_with_almost_no_short_window_allowance_left_rotates():
    assert triggered(usage=account(short_window_remaining=5.0, weekly_remaining=80.0))


def test_an_account_under_the_weekly_reserve_rotates_and_one_above_it_does_not():
    assert triggered(usage=account(short_window_remaining=60.0, weekly_remaining=5.0))
    assert not triggered(usage=account(short_window_remaining=60.0, weekly_remaining=50.0))


def test_a_protected_account_at_its_floor_rotates_where_an_unprotected_one_would_not():
    """The floor leg reads weekly remaining RAW -- before the floor is netted off.

    Eleven points left clears the ten-point weekly reserve, so nothing else in
    `triggered` fires; only the twelve-point floor forces the rotation.
    """
    at_floor = account(short_window_remaining=60.0, weekly_remaining=11.0)

    assert triggered(usage=at_floor, active_name="active", protection_floors={"active": 12.0})
    assert not triggered(usage=at_floor, active_name="active", protection_floors={})


def test_the_reported_binding_names_the_protection_floor_that_forced_the_rotation():
    at_floor = account(short_window_remaining=60.0, weekly_remaining=11.0)

    dimension, _, reason = binding(
        usage=at_floor, active_name="active", protection_floors={"active": 12.0}
    )

    assert dimension == "seven_day"
    assert reason == "protection floor for active (12%)"


def test_an_unserveable_scoped_pin_rotates_only_while_the_pin_is_in_effect():
    exhausted = account(short_window_remaining=60.0, scoped_remaining=0.0)

    assert triggered(usage=exhausted, scoped_pin=True)
    assert not triggered(usage=exhausted)


def test_a_scoped_pin_the_account_can_still_serve_does_not_rotate():
    assert not triggered(
        usage=account(short_window_remaining=60.0, scoped_remaining=0.1), scoped_pin=True
    )


# ---------------------------------------------------------------------------
# The floor-breach report -- the operator-facing outcome of `raw_weekly_left`.
# ---------------------------------------------------------------------------


def test_a_protected_account_at_its_floor_reports_a_breach_naming_what_is_left():
    breach = floor_breach(
        usage=account(short_window_remaining=60.0, weekly_remaining=8.0), protection_floor=12.0
    )

    assert breach is not None
    remaining, floor = breach
    assert remaining == pytest.approx(8.0)
    assert floor == pytest.approx(12.0)


def test_a_protected_account_still_clear_of_its_floor_reports_no_breach():
    assert (
        floor_breach(
            usage=account(short_window_remaining=60.0, weekly_remaining=20.0),
            protection_floor=12.0,
        )
        is None
    )


def test_an_unprotected_account_never_reports_a_breach_however_little_is_left():
    assert (
        floor_breach(
            usage=account(short_window_remaining=60.0, weekly_remaining=0.0),
            protection_floor=0.0,
        )
        is None
    )


# ---------------------------------------------------------------------------
# The scoped-margin waiver -- offered or not, and what it admits.
# ---------------------------------------------------------------------------


def _active(*, scoped_remaining: float | None, scoped_pin: bool) -> ActiveAccount:
    return ActiveAccount(
        name="active",
        usage=account(short_window_remaining=60.0, scoped_remaining=scoped_remaining),
        scoped_pin=scoped_pin,
    )


def test_no_waiver_is_offered_while_no_pin_names_the_scoped_model():
    assert scoped_waiver_ceiling(active=_active(scoped_remaining=0.0, scoped_pin=False)) is None


def test_no_waiver_is_offered_while_the_active_account_can_still_serve_the_pin():
    assert scoped_waiver_ceiling(active=_active(scoped_remaining=0.1, scoped_pin=True)) is None


def test_a_stranded_pin_offers_a_waiver_bounded_at_the_rotation_threshold():
    """The bound is the rotation threshold itself, so the waiver can never admit an
    account the pass would immediately have to leave again."""
    assert scoped_waiver_ceiling(
        active=_active(scoped_remaining=0.0, scoped_pin=True)
    ) == pytest.approx(five_hour_threshold())


def test_the_waiver_admits_a_scoped_capable_candidate_that_fails_the_headroom_margin():
    """The candidate is WORSE off on short-window headroom than the active account."""
    holder = live(name="holder", record=account(short_window_remaining=40.0, scoped_remaining=42.0))

    assert admitted(profiles=(holder,), active=_active(scoped_remaining=0.0, scoped_pin=True)) == [
        "holder"
    ]


def test_the_waiver_never_admits_a_scoped_capable_candidate_past_the_rotation_threshold():
    nearly_spent = live(
        name="nearly-spent", record=account(short_window_remaining=5.0, scoped_remaining=42.0)
    )

    assert (
        admitted(profiles=(nearly_spent,), active=_active(scoped_remaining=0.0, scoped_pin=True))
        == []
    )


# ---------------------------------------------------------------------------
# The scoped-alone hold -- licensed only where the pin is the WHOLE reason.
# ---------------------------------------------------------------------------


def test_scoped_unsatisfiability_alone_licenses_the_hold():
    assert scoped_alone_trigger(
        usage=account(short_window_remaining=60.0, weekly_remaining=80.0, scoped_remaining=0.0),
        scoped_pin=True,
    )


def test_a_spent_short_window_denies_the_hold_because_it_must_rotate_anyway():
    assert not scoped_alone_trigger(
        usage=account(short_window_remaining=5.0, scoped_remaining=0.0), scoped_pin=True
    )


def test_being_under_the_weekly_reserve_denies_the_hold():
    assert not scoped_alone_trigger(
        usage=account(short_window_remaining=60.0, weekly_remaining=5.0, scoped_remaining=0.0),
        scoped_pin=True,
    )


def test_being_at_a_protection_floor_denies_the_hold():
    assert not scoped_alone_trigger(
        usage=account(short_window_remaining=60.0, weekly_remaining=11.0, scoped_remaining=0.0),
        active_name="active",
        protection_floors={"active": 12.0},
        scoped_pin=True,
    )


def test_no_hold_is_licensed_without_a_pin_or_while_the_pin_is_still_serveable():
    assert not scoped_alone_trigger(
        usage=account(short_window_remaining=60.0, scoped_remaining=0.0)
    )
    assert not scoped_alone_trigger(
        usage=account(short_window_remaining=60.0, scoped_remaining=0.1), scoped_pin=True
    )


# ---------------------------------------------------------------------------
# The exhaustion sentinels -- "nothing left" is zero remaining either way.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scoped_remaining", "servable"),
    [(0.0, False), (0.1, True), (42.0, True), (100.0, True)],
)
def test_serve_capability_turns_on_whether_any_scoped_allowance_is_left(
    *, scoped_remaining: float, servable: bool
):
    record = account(short_window_remaining=60.0, scoped_remaining=scoped_remaining)

    assert can_serve_scoped_model(usage=record) is servable


def test_an_unreadable_scoped_allowance_can_never_serve_the_pin():
    assert not can_serve_scoped_model(
        usage=account(short_window_remaining=60.0, scoped_remaining=None)
    )
    assert not can_serve_scoped_model(usage=None)


@pytest.mark.parametrize(
    ("scoped_remaining", "has_capacity"),
    [(0.0, False), (0.1, True), (42.0, True), (100.0, True)],
)
def test_the_enforcement_pass_reads_scoped_capacity_at_the_same_boundary(
    *, scoped_remaining: float, has_capacity: bool
):
    assert fable_left(active_fable=stored_reading(remaining=scoped_remaining)) is has_capacity


def test_an_absent_scoped_reading_is_no_scoped_capacity_for_enforcement_either():
    assert not fable_left(active_fable=None)


@pytest.mark.parametrize("scoped_remaining", [0.0, 0.1, 42.0, 100.0])
def test_the_two_scoped_exhaustion_sentinels_agree_at_every_reading(*, scoped_remaining: float):
    """Selection and enforcement each carry their own sentinel; the flip must move both.

    Inverting one and not the other would put the rotation pass and the model-policy
    pass on opposite answers about the same account, which no single-predicate test
    can catch.
    """
    assert fable_left(
        active_fable=stored_reading(remaining=scoped_remaining)
    ) is can_serve_scoped_model(
        usage=account(short_window_remaining=60.0, scoped_remaining=scoped_remaining)
    )


def test_a_candidate_with_no_short_window_allowance_left_is_never_eligible():
    """Pinned with the margin waived entirely, so only the exhaustion sentinel can decide."""
    current = account(short_window_remaining=1.0)

    assert not is_eligible(
        usage=account(short_window_remaining=0.0),
        current=current,
        gain_needed=-inf,
        dimension="five_hour",
    )
    assert is_eligible(
        usage=account(short_window_remaining=0.1),
        current=current,
        gain_needed=-inf,
        dimension="five_hour",
    )


def test_the_empty_set_diagnosis_calls_a_spent_short_window_exhausted():
    spent = live(name="spent", record=account(short_window_remaining=0.0))
    population = CandidatePopulation(
        profiles=(spent,),
        active_name="active",
        dimension="five_hour",
        protection_floors={},
    )

    assert no_candidate_cause(population=population, gain_needed=10.0) == (
        "every live-verified candidate is exhausted (spent)"
    )


def test_the_empty_set_diagnosis_blames_the_margin_while_a_sliver_remains():
    sliver = live(name="sliver", record=account(short_window_remaining=0.1))
    population = CandidatePopulation(
        profiles=(sliver,),
        active_name="active",
        dimension="five_hour",
        protection_floors={},
    )

    assert "headroom margin over active" in no_candidate_cause(
        population=population, gain_needed=10.0
    )
