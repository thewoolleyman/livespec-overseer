"""When a refusal that reported NO reset stops holding its account.

The hold has to end on OBSERVATION rather than on a clock, because the provider
told the operation nothing about when the window recovers. Every case below is
one reading the operation could take next, and the direction they share is the
one that matters: a reading that cannot settle the question leaves the hold
standing.
"""

from __future__ import annotations

from caam_decision import ProfileUsage, UsageRecord
from caam_refusal_hold import refusal_state
from caam_refusal_store import remember_refusals
from caam_refusals import WINDOW_FIVE_HOUR, WINDOW_SEVEN_DAY, Refusal

__all__: list[str] = []

NOW = 1_800_000_000.0
RECORDED_AT = NOW - 540.0
RESET = "2027-01-15T09:00:00Z"
MUCH_LATER = "2027-01-15T15:00:00Z"


def reading(
    *,
    five_hour_remaining: float = 45.0,
    seven_day_remaining: float = 60.0,
    five_hour_resets_at: str | None = RESET,
    seven_day_resets_at: str | None = RESET,
) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five_hour_remaining,
        seven_day_remaining=seven_day_remaining,
        five_hour_resets_at=five_hour_resets_at,
        seven_day_resets_at=seven_day_resets_at,
        fable_remaining=None,
        fable_resets_at=None,
    )


def held_state(*, window: str, baseline: UsageRecord) -> dict[str, object]:
    state: dict[str, object] = {}
    remember_refusals(
        state=state,
        account="anthropic-3",
        refusals=(Refusal(recorded_at=RECORDED_AT, window=window, resets_at=None),),
        reading=baseline,
    )
    return state


def still_held(*, state: dict[str, object], later: tuple[ProfileUsage, ...]) -> bool:
    return (
        "anthropic-3"
        in refusal_state(state=state, profiles=later, active_name="anthropic-1", now=NOW).held
    )


def test_an_account_with_no_reading_at_all_stays_held() -> None:
    """No reading is not a reading showing recovery, so nothing ends the hold."""
    state = held_state(window=WINDOW_FIVE_HOUR, baseline=reading())

    assert still_held(state=state, later=())


def test_a_dark_account_whose_row_carries_no_usage_stays_held() -> None:
    state = held_state(window=WINDOW_FIVE_HOUR, baseline=reading())
    dark = (ProfileUsage(name="anthropic-3", source="dark: HTTP 429", usage=None),)

    assert still_held(state=state, later=dark)


def test_a_fully_replenished_weekly_reading_ends_a_weekly_refusals_hold() -> None:
    """The window the refusal NAMED is the one read, not the other one."""
    state = held_state(window=WINDOW_SEVEN_DAY, baseline=reading())
    replenished = (
        ProfileUsage(
            name="anthropic-3",
            source="live",
            usage=reading(seven_day_remaining=100.0, five_hour_remaining=1.0),
        ),
    )

    assert not still_held(state=state, later=replenished)


def test_a_weekly_window_that_moved_on_ends_the_hold_while_the_short_one_is_ignored() -> None:
    state = held_state(window=WINDOW_SEVEN_DAY, baseline=reading())
    moved_on = (
        ProfileUsage(
            name="anthropic-3",
            source="live",
            usage=reading(seven_day_resets_at=MUCH_LATER, five_hour_resets_at=RESET),
        ),
    )

    assert not still_held(state=state, later=moved_on)


def test_a_baseline_whose_reset_could_not_be_read_leaves_the_hold_standing() -> None:
    """There is no baseline to compare a later reset against, so nothing is proven."""
    state = held_state(window=WINDOW_FIVE_HOUR, baseline=reading(five_hour_resets_at=None))
    later = (ProfileUsage(name="anthropic-3", source="live", usage=reading()),)

    assert still_held(state=state, later=later)


def test_a_later_reading_whose_reset_cannot_be_read_leaves_the_hold_standing() -> None:
    state = held_state(window=WINDOW_FIVE_HOUR, baseline=reading())
    unreadable = (
        ProfileUsage(name="anthropic-3", source="live", usage=reading(five_hour_resets_at=None)),
    )

    assert still_held(state=state, later=unreadable)
