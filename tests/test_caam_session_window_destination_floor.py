"""A session-window move never lands on an account already due to leave (overseer-xwfyxy)."""

from __future__ import annotations

from caam_decision import ProfileUsage, UsageRecord, eligible_profiles, session_destination_floor
from caam_decision_models import ActiveAccount, ExtraUsage


def _usage(*, five_hour_left: float, seven_day_left: float = 80.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five_hour_left,
        seven_day_remaining=seven_day_left,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )


def _choose(*, active_left: float, candidate_left: float, dimension: str) -> tuple[str, ...]:
    result = eligible_profiles(
        profiles=(
            ProfileUsage(
                name="anthropic-b",
                source="live",
                usage=_usage(five_hour_left=candidate_left, seven_day_left=95.0),
            ),
        ),
        active=ActiveAccount(
            name="anthropic-a",
            usage=_usage(five_hour_left=active_left, seven_day_left=50.0),
            scoped_pin=False,
        ),
        force=False,
        dimension=dimension,
    )
    return tuple(profile.name for profile in result.profiles)


def test_a_candidate_at_or_below_the_session_floor_is_not_a_destination(monkeypatch) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)

    assert _choose(active_left=1.0, candidate_left=12.0, dimension="five_hour") == ()
    assert _choose(active_left=1.0, candidate_left=20.0, dimension="five_hour") == ()


def test_a_candidate_above_the_session_floor_is_a_destination(monkeypatch) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)

    assert _choose(active_left=1.0, candidate_left=21.0, dimension="five_hour") == ("anthropic-b",)


def test_the_weekly_comparison_does_not_read_the_session_floor(monkeypatch) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)

    assert _choose(active_left=1.0, candidate_left=12.0, dimension="seven_day") == ("anthropic-b",)


def test_a_spend_capped_active_admits_any_positive_balance(monkeypatch) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)
    capped = UsageRecord(
        five_hour_remaining=0.0,
        seven_day_remaining=70.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
        extra_usage=ExtraUsage(
            is_enabled=False, spend_limit_reached=True, monthly_limit=100.0, used_credits=100.0
        ),
    )
    plain = ActiveAccount(name="anthropic-a", usage=_usage(five_hour_left=5.0), scoped_pin=False)
    blocked = ActiveAccount(name="anthropic-a", usage=capped, scoped_pin=False)

    assert session_destination_floor(active=plain) == 20.0
    assert session_destination_floor(active=blocked) == 0.0
