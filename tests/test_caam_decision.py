"""Tests for the pure caam account-rotation decision core."""

from __future__ import annotations

import ast
import time
from datetime import datetime
from math import isinf
from pathlib import Path

import caam_decision as caam_rendering
import pytest
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    binding,
    eligible_profiles,
    is_eligible,
    rank_profiles,
    resets_at,
    triggered,
    weekly_left,
)

__all__: list[str] = []


SHARED_HELPER_NAMES = {
    "five_hour_threshold",
    "min_headroom_gain",
    "resets_at",
    "weekly_reserve",
}


def usage(
    *,
    five_hour: float,
    seven_day: float,
    five_hour_resets_at: str | None = "2026-08-21T12:00:00Z",
    seven_day_resets_at: str | None = "2026-08-23T12:00:00Z",
    fable: float | None = 0.0,
    fable_resets_at: str | None = "2026-08-23T12:00:00Z",
) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at=five_hour_resets_at,
        seven_day_resets_at=seven_day_resets_at,
        fable=fable,
        fable_resets_at=fable_resets_at,
    )


def test_shared_caam_helpers_have_one_decision_owned_definition():
    package = Path(__file__).resolve().parents[1] / "overseer"
    definitions: dict[str, list[str]] = {name: [] for name in SHARED_HELPER_NAMES}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in definitions:
                definitions[node.name].append(path.name)

    assert definitions == {
        "five_hour_threshold": ["caam_decision.py"],
        "min_headroom_gain": ["caam_decision.py"],
        "resets_at": ["caam_decision.py"],
        "weekly_reserve": ["caam_decision.py"],
    }


def test_rendering_imports_shared_caam_helpers_from_decision_module():
    rendering_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_rendering.py"
    tree = ast.parse(rendering_path.read_text(encoding="utf-8"))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "caam_decision"
        for alias in node.names
    }

    assert imported_names >= SHARED_HELPER_NAMES


@pytest.mark.parametrize(
    ("record", "threshold", "reserve", "expected"),
    [
        (usage(five_hour=85.0, seven_day=20.0), "85", "10", ("five_hour", 85.0, "5-hour window")),
        (usage(five_hour=84.9, seven_day=91.0), "85", "10", ("seven_day", 91.0, "weekly reserve")),
        (usage(five_hour=84.9, seven_day=90.0), "85", "10", ("five_hour", 84.9, "5-hour window")),
    ],
)
def test_binding_selects_the_triggering_allowance_at_call_time(
    *, monkeypatch, record, threshold, reserve, expected
):
    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", threshold)
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", reserve)

    assert binding(usage=record) == expected


def test_trigger_configuration_is_resolved_at_call_time(*, monkeypatch):
    record = usage(five_hour=70.0, seven_day=20.0)

    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "80")
    assert not triggered(usage=record)

    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "70")
    assert triggered(usage=record)


def test_weekly_left_derives_remaining_percent_from_weekly_usage():
    assert weekly_left(usage=usage(five_hour=12.0, seven_day=64.5)) == 35.5


def test_eligibility_is_relative_instead_of_an_absolute_threshold(*, monkeypatch):
    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "50")
    current = usage(five_hour=55.0, seven_day=25.0)
    candidate = usage(five_hour=51.0, seven_day=25.0)

    assert is_eligible(
        usage=candidate,
        current=current,
        gain_needed=0.01,
        dimension="five_hour",
    )


def test_min_gain_margin_makes_reverse_switch_impossible():
    current = usage(five_hour=86.0, seven_day=25.0)
    target = usage(five_hour=70.0, seven_day=25.0)

    assert is_eligible(
        usage=target,
        current=current,
        gain_needed=10.0,
        dimension="five_hour",
    )
    assert not is_eligible(
        usage=current,
        current=target,
        gain_needed=10.0,
        dimension="five_hour",
    )


@pytest.mark.parametrize(
    ("record", "floor", "expected"),
    [
        (usage(five_hour=10.0, seven_day=88.0), 10.0, 2.0),
        (usage(five_hour=10.0, seven_day=90.0), 10.0, 0.0),
        (usage(five_hour=10.0, seven_day=95.0), 10.0, 0.0),
        (usage(five_hour=10.0, seven_day=88.0), 0.0, 12.0),
    ],
)
def test_protection_floor_reduces_usable_weekly_headroom(*, record, floor, expected):
    assert weekly_left(usage=record, protection_floor=floor) == expected


def test_protected_candidate_uses_usable_weekly_headroom_for_eligibility():
    current = usage(five_hour=10.0, seven_day=100.0)
    candidate = usage(five_hour=10.0, seven_day=88.0)

    assert is_eligible(
        usage=candidate,
        current=current,
        gain_needed=10.0,
        dimension="seven_day",
    )
    assert not is_eligible(
        usage=candidate,
        current=current,
        gain_needed=10.0,
        dimension="seven_day",
        protection_floor=10.0,
    )
    assert not is_eligible(
        usage=usage(five_hour=10.0, seven_day=90.0),
        current=current,
        gain_needed=0.01,
        dimension="seven_day",
        protection_floor=10.0,
    )


def test_protected_candidates_are_last_resort_and_keep_existing_ranking():
    current = usage(five_hour=95.0, seven_day=95.0)
    unprotected = ProfileUsage(
        name="unprotected",
        source="live",
        usage=usage(
            five_hour=40.0,
            seven_day=40.0,
            seven_day_resets_at="2026-08-27T00:00:00Z",
        ),
    )
    protected_soon = ProfileUsage(
        name="protected-soon",
        source="live",
        usage=usage(
            five_hour=30.0,
            seven_day=80.0,
            seven_day_resets_at="2026-08-22T00:00:00Z",
        ),
    )
    protected_later = ProfileUsage(
        name="protected-later",
        source="live",
        usage=usage(
            five_hour=20.0,
            seven_day=70.0,
            seven_day_resets_at="2026-08-24T00:00:00Z",
        ),
    )
    floors = {"protected-soon": 10.0, "protected-later": 20.0}

    with_unprotected = eligible_profiles(
        profiles=(unprotected, protected_soon),
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
        protection_floors=floors,
    )
    assert [profile.name for profile in with_unprotected.profiles] == ["unprotected"]

    only_protected = eligible_profiles(
        profiles=(protected_later, protected_soon),
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="seven_day",
        protection_floors=floors,
    )
    assert [profile.name for profile in rank_profiles(profiles=only_protected.profiles)] == [
        "protected-soon",
        "protected-later",
    ]


def test_active_protected_account_triggers_at_its_floor_and_reports_protection_binding(
    *, monkeypatch
):
    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "85")
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", "10")
    active = usage(five_hour=40.0, seven_day=88.0)

    assert triggered(usage=active, active_name="active", protection_floors={"active": 12.0})
    assert not triggered(usage=active, active_name="active", protection_floors={})
    assert binding(usage=active, active_name="active", protection_floors={"active": 12.0}) == (
        "seven_day",
        88.0,
        "protection floor for active (12%)",
    )


def test_reserve_release_does_not_release_protection_floors(*, monkeypatch):
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", "15")
    current = usage(five_hour=95.0, seven_day=95.0)
    unprotected = ProfileUsage(
        name="unprotected",
        source="live",
        usage=usage(five_hour=40.0, seven_day=90.0),
    )
    protected = ProfileUsage(
        name="protected",
        source="live",
        usage=usage(five_hour=35.0, seven_day=92.0),
    )

    released = eligible_profiles(
        profiles=(unprotected, protected),
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
        protection_floors={"protected": 10.0},
    )
    assert [profile.name for profile in released.profiles] == ["unprotected"]
    assert released.reserve_released
    assert released.note == "note: every account is under the 15% weekly reserve -- releasing it"

    held = eligible_profiles(
        profiles=(protected,),
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
        protection_floors={"protected": 10.0},
    )
    assert held.profiles == ()
    assert not held.reserve_released
    assert held.note == "hold: protected account floors reached: protected at 8% left (floor 10%)"


def test_protection_inputs_are_explicit_and_ignore_environment(*, monkeypatch):
    current = usage(five_hour=10.0, seven_day=100.0)
    candidate = usage(five_hour=10.0, seven_day=88.0)

    monkeypatch.setenv("CAAM_PROTECTED_ACCOUNTS", "candidate=10")
    without_explicit_floor = is_eligible(
        usage=candidate,
        current=current,
        gain_needed=10.0,
        dimension="seven_day",
    )
    with_explicit_floor = is_eligible(
        usage=candidate,
        current=current,
        gain_needed=10.0,
        dimension="seven_day",
        protection_floor=10.0,
    )

    assert without_explicit_floor
    assert not with_explicit_floor


@pytest.mark.parametrize(
    ("current", "candidate", "gain_needed", "dimension"),
    [
        (
            usage(five_hour=95.0, seven_day=95.0),
            usage(five_hour=40.0, seven_day=95.0),
            0.01,
            "five_hour",
        ),
        (
            usage(five_hour=10.0, seven_day=100.0),
            usage(five_hour=10.0, seven_day=88.0),
            10.0,
            "seven_day",
        ),
        (
            usage(five_hour=86.0, seven_day=25.0),
            usage(five_hour=70.0, seven_day=25.0),
            10.0,
            "five_hour",
        ),
    ],
)
def test_absent_protection_preserves_current_eligibility(
    *, current, candidate, gain_needed, dimension
):
    assert is_eligible(
        usage=candidate,
        current=current,
        gain_needed=gain_needed,
        dimension=dimension,
    ) == is_eligible(
        usage=candidate,
        current=current,
        gain_needed=gain_needed,
        dimension=dimension,
        protection_floor=0.0,
        current_protection_floor=0.0,
    )


def test_absent_protection_preserves_current_candidate_decisions(*, monkeypatch):
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", "10")
    current = usage(five_hour=95.0, seven_day=95.0)
    profiles = (
        ProfileUsage(
            name="below",
            source="live",
            usage=usage(five_hour=50.0, seven_day=95.0),
        ),
        ProfileUsage(
            name="above",
            source="live",
            usage=usage(five_hour=50.0, seven_day=89.0),
        ),
    )

    before = eligible_profiles(
        profiles=profiles,
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
    )
    after = eligible_profiles(
        profiles=profiles,
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
        protection_floors={},
    )

    assert after == before


def test_absent_protection_preserves_current_trigger_and_binding(*, monkeypatch):
    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "85")
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", "10")
    cases = (
        usage(five_hour=85.0, seven_day=20.0),
        usage(five_hour=84.9, seven_day=91.0),
        usage(five_hour=40.0, seven_day=88.0),
    )

    for record in cases:
        assert triggered(usage=record, protection_floors={}) == triggered(usage=record)
        assert binding(usage=record, protection_floors={}) == binding(usage=record)


def test_eligibility_and_ranking_do_not_consult_fable():
    """The two-tier Fable design was built and deliberately reverted."""

    current = usage(five_hour=90.0, seven_day=40.0, fable=100.0, fable_resets_at="bad")
    exhausted_fable_soonest = ProfileUsage(
        name="soonest",
        source="live",
        usage=usage(
            five_hour=70.0,
            seven_day=20.0,
            seven_day_resets_at="2026-08-22T00:00:00Z",
            fable=100.0,
            fable_resets_at="unreadable-fable",
        ),
    )
    has_fable_later = ProfileUsage(
        name="later",
        source="live",
        usage=usage(
            five_hour=69.0,
            seven_day=20.0,
            seven_day_resets_at="2026-08-25T00:00:00Z",
            fable=0.0,
            fable_resets_at="2026-08-21T00:00:00Z",
        ),
    )

    candidates = eligible_profiles(
        profiles=(exhausted_fable_soonest, has_fable_later),
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
    ).profiles

    assert [profile.name for profile in rank_profiles(profiles=candidates)] == ["soonest", "later"]


@pytest.mark.parametrize(
    "record",
    [
        usage(five_hour=80.0, seven_day=100.0),
        usage(five_hour=100.0, seven_day=80.0),
    ],
)
def test_zero_allowance_disqualifies_candidate(*, record):
    assert not is_eligible(
        usage=record,
        current=usage(five_hour=95.0, seven_day=95.0),
        gain_needed=0.01,
        dimension="five_hour",
    )


def test_reserve_release_retry_only_when_every_account_is_below_the_reserve(*, monkeypatch):
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", "10")
    current = usage(five_hour=95.0, seven_day=95.0)
    below_reserve = ProfileUsage(
        name="below",
        source="live",
        usage=usage(five_hour=50.0, seven_day=95.0),
    )
    above_reserve = ProfileUsage(
        name="above",
        source="live",
        usage=usage(five_hour=50.0, seven_day=89.0),
    )

    protected = eligible_profiles(
        profiles=(below_reserve, above_reserve),
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
    )
    assert [profile.name for profile in protected.profiles] == ["above"]
    assert not protected.reserve_released

    released = eligible_profiles(
        profiles=(below_reserve,),
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
    )
    assert [profile.name for profile in released.profiles] == ["below"]
    assert released.reserve_released
    assert released.note == "note: every account is under the 10% weekly reserve -- releasing it"


def test_ranking_uses_soonest_weekly_reset_and_unreadable_timestamps_sort_last():
    unreadable = ProfileUsage(
        name="unreadable",
        source="live",
        usage=usage(five_hour=40.0, seven_day=30.0, seven_day_resets_at="not-a-time"),
    )
    later = ProfileUsage(
        name="later",
        source="live",
        usage=usage(five_hour=40.0, seven_day=30.0, seven_day_resets_at="2026-08-25T00:00:00Z"),
    )
    soonest = ProfileUsage(
        name="soonest",
        source="live",
        usage=usage(five_hour=40.0, seven_day=30.0, seven_day_resets_at="2026-08-22T00:00:00Z"),
    )

    assert isinf(resets_at(timestamp="not-a-time"))
    assert [profile.name for profile in rank_profiles(profiles=(unreadable, later, soonest))] == [
        "soonest",
        "later",
        "unreadable",
    ]


def test_resets_at_returns_epoch_seconds_for_aware_timestamp():
    timestamp = "2026-08-21T12:00:00Z"
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    assert resets_at(timestamp=timestamp) == parsed.timestamp()


def test_resets_at_values_compare_against_wall_clock_time():
    now = time.time()

    assert resets_at(timestamp="2000-01-01T00:00:00Z") < now
    assert resets_at(timestamp="2099-01-01T00:00:00Z") > now


def test_resets_at_unknown_timestamps_are_infinity_and_sort_last():
    assert isinf(resets_at(timestamp=None))
    assert isinf(resets_at(timestamp=""))
    assert isinf(resets_at(timestamp="not-a-time"))


def test_resets_at_accepts_nonzero_utc_offsets():
    assert resets_at(timestamp="2026-08-21T14:00:00+02:00") == resets_at(
        timestamp="2026-08-21T12:00:00Z"
    )


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (2 * 86400 + 2 * 3600 + 12 * 60, "2d 2h 12m"),
        (2 * 3600 + 12 * 60, "2h 12m"),
        (12 * 60, "12m"),
        (-10, "0m"),
    ],
)
def test_duration_format_drops_zero_units_from_the_left(*, seconds, expected):
    assert hasattr(caam_rendering, "fmt_duration")
    assert caam_rendering.fmt_duration(seconds=seconds) == expected


def test_until_renders_dash_for_missing_or_unreadable_reset_timestamp():
    assert hasattr(caam_rendering, "until")
    assert (
        caam_rendering.until(
            timestamp=None,
            now=datetime.fromisoformat("2026-08-21T12:00:00+00:00"),
        )
        == "-"
    )
    assert (
        caam_rendering.until(
            timestamp="not-a-time",
            now=datetime.fromisoformat("2026-08-21T12:00:00+00:00"),
        )
        == "-"
    )


def display_width(*, text: str) -> int:
    return sum(2 if character == "✅" else 1 for character in text)


def test_current_column_pads_by_display_width_for_active_check_mark():
    assert hasattr(caam_rendering, "current_cell")
    active = f"{'active':<13} {caam_rendering.current_cell(is_active=True)} {15.0:6.0f}%"
    inactive = f"{'inactive':<13} {caam_rendering.current_cell(is_active=False)} {15.0:6.0f}%"

    assert display_width(text=active) == display_width(text=inactive)


def test_table_renders_remaining_quota_reset_durations_and_source_text():
    now = datetime.fromisoformat("2026-08-21T12:00:00+00:00")
    rows = (
        ProfileUsage(
            name="active",
            source="live",
            usage=usage(
                five_hour=20.0,
                seven_day=30.0,
                five_hour_resets_at="2026-08-21T14:30:00+00:00",
                seven_day_resets_at="2026-08-23T15:12:00+00:00",
                fable=40.0,
                fable_resets_at="2026-08-22T12:05:00+00:00",
            ),
        ),
        ProfileUsage(name="dark", source="dark: no token", usage=None),
        ProfileUsage(
            name="nofable",
            source="live",
            usage=usage(
                five_hour=90.0,
                seven_day=95.0,
                five_hour_resets_at="2026-08-21T12:01:00+00:00",
                seven_day_resets_at="2026-08-21T13:00:00+00:00",
                fable=None,
                fable_resets_at=None,
            ),
        ),
    )

    assert hasattr(caam_rendering, "render_table")
    assert caam_rendering.render_table(rows=rows, active_name="active", now=now) == (
        "\n"
        "PROFILE       CURRENT       5H      5H RESET      WEEK    WEEK RESET      "
        "FABLE   FABLE RESET   SOURCE\n"
        "active        ✅           80%        2h 30m       70%     2d 3h 12m       "
        "60%      1d 0h 5m   live\n"
        "dark                         -             -         -             -          -"
        "             -   dark: no token\n"
        "nofable                    10%            1m        5%         1h 0m         -"
        "             -   live\n"
        "\n"
    )


def test_cached_row_past_reset_renders_unknown_and_stale_source():
    now = datetime.fromisoformat("2026-08-21T12:00:00+00:00")
    row = ProfileUsage(
        name="cached",
        source="cached 1.0h",
        usage=usage(
            five_hour=20.0,
            seven_day=30.0,
            five_hour_resets_at="2026-08-21T11:59:00+00:00",
            seven_day_resets_at="2026-08-23T15:12:00+00:00",
            fable=40.0,
            fable_resets_at="2026-08-22T12:05:00+00:00",
        ),
    )

    assert hasattr(caam_rendering, "render_table")
    assert caam_rendering.render_table(rows=(row,), active_name="active", now=now) == (
        "\n"
        "PROFILE       CURRENT       5H      5H RESET      WEEK    WEEK RESET      "
        "FABLE   FABLE RESET   SOURCE\n"
        "cached                       ?         reset         ?         reset          ?"
        "         reset   cached 1.0h, stale\n"
        "\n"
    )


def test_trigger_header_matches_source_format_string(*, monkeypatch):
    monkeypatch.setenv("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "85.5")
    monkeypatch.setenv("CAAM_ROTATE_WEEKLY_RESERVE", "10.6")
    monkeypatch.setenv("CAAM_ROTATE_MIN_HEADROOM_GAIN", "9.6")

    assert hasattr(caam_rendering, "trigger_header")
    assert caam_rendering.trigger_header(stamp="2026-08-21T12:00:00Z") == (
        "2026-08-21T12:00:00Z  triggers: 5h-remaining < 14% or "
        "weekly-remaining < 11% (candidate must gain >=10 pts)"
    )


def test_decision_lines_match_source_format_strings():
    assert hasattr(caam_rendering, "SwitchTargetSummary")
    target = caam_rendering.SwitchTargetSummary(
        name="target",
        weekly_used=65.0,
        weekly_reset="2026-08-22T12:00:00+00:00",
        source="live",
        now=datetime.fromisoformat("2026-08-21T12:00:00+00:00"),
    )
    assert hasattr(caam_rendering, "decision_hold_allowance")
    assert (
        caam_rendering.decision_hold_allowance(
            label="5-hour window",
            spent=21.0,
            weekly_remaining=34.0,
            reserve=10.6,
        )
        == "hold: 5-hour window is the binding allowance and still has 79% left "
        "(weekly 34%, reserve 11%)"
    )
    assert hasattr(caam_rendering, "decision_forced")
    assert caam_rendering.decision_forced(threshold=85.5) == (
        "forced: ignoring the 86% trigger, rotating to the best target now"
    )
    assert hasattr(caam_rendering, "decision_trigger")
    assert (
        caam_rendering.decision_trigger(
            label="weekly reserve",
            spent=92.0,
            weekly_remaining=8.0,
            dimension="seven_day",
        )
        == "trigger: weekly reserve -- 92% spent, weekly 8% left -- comparing "
        "candidates on seven_day"
    )
    assert hasattr(caam_rendering, "decision_dry_run")
    assert (
        caam_rendering.decision_dry_run(
            active_name="active",
            target=target,
        )
        == "DRY-RUN would switch active -> target (35% week left, resets in "
        "1d 0h 0m -- soonest, live)"
    )
    assert hasattr(caam_rendering, "decision_hold_no_candidate")
    assert caam_rendering.decision_hold_no_candidate(
        gain_needed=10.0,
        dimension="five_hour",
        active_name="active",
    ) == (
        "hold: no candidate has >=10.00 points more five_hour headroom than active "
        "(all similarly spent, exhausted, or unverifiable)"
    )
    assert hasattr(caam_rendering, "decision_switched")
    assert (
        caam_rendering.decision_switched(
            active_name="active",
            current_five_hour_used=21.0,
            target=target,
        )
        == "SWITCHED active -> target (5h left was 79%; target has 35% week "
        "left resetting in 1d 0h 0m -- soonest, live)"
    )
