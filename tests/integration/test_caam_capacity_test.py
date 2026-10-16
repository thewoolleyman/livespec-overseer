"""Integration-tier scenarios for the capacity test (SPECIFICATION v056).

The capacity-test scenarios of `SPECIFICATION/scenarios.md` are driven through
the SHIPPED rotation pass on the harness `test_caam_fast_drain` builds, because
the two halves of this ratified clause are measured the same way: a capacity
test needs a FLEET LOAD, a fleet load needs a burn rate, and a burn rate is a
measurement across two readings taken at known, different instants.

WHY TWO CANDIDATES AND NOT ONE in most of these. "Not selected" is only
observable against something that WAS, so each scenario that excludes a
candidate also supplies one the test admits -- and the excluded one is the one
RANKING puts first, so a build that ignored the capacity test entirely selects
it. A scenario asserting only that the pass held would pass against a build
that emptied the candidate set for some unrelated reason.

Capacity classes come from the live plan read, which the harness injects per
account, exactly as `test_caam_capacity_reporting` does: a plan the provider
does not answer for reads as an UNKNOWN class, which is one of the scenarios.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from caam_capacity_load import FLEET_LOAD
from caam_capacity_weights import ANTHROPIC, capacity_weights
from caam_decision import ProfileUsage, rank_profiles
from test_caam_fast_drain import (
    LARGE_PLAN,
    NOW,
    PASS_INTERVAL,
    SMALL_PLAN,
    RotationHarness,
    usage,
)

__all__: list[str] = []

pytestmark = pytest.mark.integration

DAY = 86_400.0
# The fall, in short-window points across one projection horizon, that the
# ratified scenarios state as "a short-window burn rate of 10 points per
# projection horizon". Against the Anthropic defaults (large 7, small 1) it is
# a fleet load that drains 70 points off a small account in one horizon.
HEAVY_FALL = 10.0
# "a short-window burn rate of 1 point per projection horizon", which drains 7.
LIGHT_FALL = 1.0


def fleet_load_record(*, harness: RotationHarness) -> dict[str, object]:
    """The fleet load the operation's own durable store now holds."""
    stored = harness.read_state()[FLEET_LOAD]
    assert isinstance(stored, dict)
    return stored


def ranks_first(*, first: str, second: str, harness: RotationHarness) -> bool:
    """Whether RANKING puts `first` ahead of `second`, on this pass's readings.

    Asserted as a PREMISE by the scenarios that exclude a candidate: if the
    excluded candidate did not rank first, the switch landing elsewhere would
    say nothing about the capacity test.
    """
    ranked = rank_profiles(
        profiles=tuple(
            ProfileUsage(name=name, source="live", usage=harness.usages[name])
            for name in (second, first)
        )
    )
    return tuple(profile.name for profile in ranked) == (first, second)


def test_scenario_a_small_candidate_that_the_current_load_would_drain_is_not_selected(
    *, tmp_path: Path
) -> None:
    """Given the active account is in the large capacity class with a short-window
    burn rate of 10 points per projection horizon, and a candidate in the small
    capacity class holds 50% short-window remaining, and the short-window floor is
    15% remaining, and the capacity weights are large 7 and small 1, when the
    operation selects a destination, then the small candidate is not selected.

    Seventy points of the fleet's load land on a small account in one horizon,
    so 50% becomes -20% before the next pass -- an account that would be
    refusing requests within minutes of being moved onto.

    The large candidate holds the SAME 50% and is selected instead, which is
    what makes this a measurement of capacity rather than of percentages: the
    two candidates are indistinguishable on every figure the ranking reads, and
    the small one ranks FIRST.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="big",
        usages={
            "big": usage(five_hour_remaining=30.0, seven_day_reset_s=DAY),
            "small-plan": usage(five_hour_remaining=50.0, seven_day_reset_s=2 * DAY),
            "big-plan": usage(five_hour_remaining=50.0, seven_day_reset_s=3 * DAY),
        },
        live_plans={"big": LARGE_PLAN, "small-plan": SMALL_PLAN, "big-plan": LARGE_PLAN},
    )
    assert ranks_first(first="small-plan", second="big-plan", harness=harness)

    _first_code, _first_lines = harness.run(at=NOW)
    harness.read(
        name="big",
        record=usage(five_hour_remaining=30.0 - HEAVY_FALL, seven_day_reset_s=DAY),
    )
    code, lines = harness.run(at=NOW + PASS_INTERVAL)

    assert code == 0
    assert harness.switches == ["big-plan"]
    assert any("projected short-window drain" in line for line in lines)
    recorded = fleet_load_record(harness=harness)
    assert recorded["at"] == NOW + PASS_INTERVAL
    assert recorded["load"] == pytest.approx(HEAVY_FALL * 7.0 / PASS_INTERVAL)


def test_scenario_a_small_candidate_is_selectable_under_light_load(*, tmp_path: Path) -> None:
    """Given the active account is in the large capacity class with a short-window
    burn rate of 1 point per projection horizon, and a candidate in the small
    capacity class holds 50% short-window remaining, and the short-window floor is
    15% remaining, and the capacity weights are large 7 and small 1, when the
    operation selects a destination, then the capacity test does not exclude the
    small candidate.

    Seven points land on the small account in one horizon, leaving 43% -- so the
    test the scenario above fails is passed here on the SAME 50% reading and the
    same weights. Only the load differs, which is the point: the clause bounds
    what an account can CARRY, not how large its plan is.

    The active account crosses its own short-window floor here, so it is the
    ordinary threshold that fires rather than the fast-drain trigger, which is
    deliberate: the capacity test applies to every selection the operation makes.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="big",
        usages={
            "big": usage(five_hour_remaining=16.0, seven_day_reset_s=DAY),
            "small-plan": usage(five_hour_remaining=50.0, seven_day_reset_s=2 * DAY),
        },
        live_plans={"big": LARGE_PLAN, "small-plan": SMALL_PLAN},
    )

    _first_code, _first_lines = harness.run(at=NOW)
    harness.read(
        name="big",
        record=usage(five_hour_remaining=16.0 - LIGHT_FALL, seven_day_reset_s=DAY),
    )
    code, _lines = harness.run(at=NOW + PASS_INTERVAL)

    assert code == 0
    assert harness.switches == ["small-plan"]
    assert fleet_load_record(harness=harness)["load"] == pytest.approx(
        LIGHT_FALL * 7.0 / PASS_INTERVAL
    )


def test_no_fleet_load_at_all_excludes_no_candidate(*, tmp_path: Path) -> None:
    """Where no fleet load is available the capacity test excludes nobody.

    A single pass has no baseline to measure from and nothing remembered, so
    there is no load -- and the small candidate here is one that a load of the
    size the scenarios above state WOULD exclude. Failing closed instead would
    strand the fleet on an exhausted account on the one pass that knows least.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="big",
        usages={
            "big": usage(five_hour_remaining=15.0, seven_day_reset_s=DAY),
            "small-plan": usage(five_hour_remaining=30.0, seven_day_reset_s=2 * DAY),
        },
        live_plans={"big": LARGE_PLAN, "small-plan": SMALL_PLAN},
    )

    code, _lines = harness.run(at=NOW)

    assert code == 0
    assert harness.switches == ["small-plan"]
    assert FLEET_LOAD not in harness.read_state()


def test_capacity_weights_are_configurable_per_provider_and_class(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capacity weights are configurable per provider and capacity class, with the
    Anthropic defaults small 1, medium 2 and large 7.

    The nominal plan multiplier is NOT the weight: measured on host hp
    2026-10-13 the observed short-window ratio between Anthropic's large and
    small plans was about seven to one, against a nominal twenty, which is
    exactly why these are knobs and not constants.

    The knob is then measured rather than merely read: flattening the large
    weight to 1 turns the scenario that excludes a small candidate into one that
    selects it, on the same readings.
    """
    assert capacity_weights(provider=ANTHROPIC) == {"small": 1.0, "medium": 2.0, "large": 7.0}
    monkeypatch.setenv("CAAM_ROTATE_CAPACITY_WEIGHT_ANTHROPIC_LARGE", "1")
    assert capacity_weights(provider=ANTHROPIC)["large"] == 1.0
    harness = RotationHarness(
        home=tmp_path,
        active="big",
        usages={
            "big": usage(five_hour_remaining=30.0, seven_day_reset_s=DAY),
            "small-plan": usage(five_hour_remaining=50.0, seven_day_reset_s=2 * DAY),
            "big-plan": usage(five_hour_remaining=50.0, seven_day_reset_s=3 * DAY),
        },
        live_plans={"big": LARGE_PLAN, "small-plan": SMALL_PLAN, "big-plan": LARGE_PLAN},
    )

    _first_code, _first_lines = harness.run(at=NOW)
    harness.read(
        name="big",
        record=usage(five_hour_remaining=30.0 - HEAVY_FALL, seven_day_reset_s=DAY),
    )
    code, _lines = harness.run(at=NOW + PASS_INTERVAL)

    assert code == 0
    assert harness.switches == ["small-plan"]
