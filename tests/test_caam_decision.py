"""Tests for the pure caam account-rotation decision core."""

from __future__ import annotations

import time
from datetime import datetime
from math import isinf

import pytest
from caam_decision import (
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
        active_name="active",
        current=current,
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
        active_name="active",
        current=current,
        force=True,
        dimension="five_hour",
    )
    assert [profile.name for profile in protected.profiles] == ["above"]
    assert not protected.reserve_released

    released = eligible_profiles(
        profiles=(below_reserve,),
        active_name="active",
        current=current,
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
