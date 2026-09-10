"""Reading the extra-usage DOLLAR meter the usage response carries, and what it means.

The response this operation already fetches reports two independent things about
an account: how much of each included allowance is left, as a percentage, and
how many pay-as-you-go DOLLARS have been spent once an included allowance ran
out. Only the percentages were ever read. That is why an account could print a
healthy table while every session on it was refused: the meter that had actually
stopped it was in the same response, one key away, and was parsed and dropped.

Reading and MEANING live together here because the meaning is the whole reason
to read it. `spend_capped` is the predicate selection turns on -- an account at
its monthly dollar cap has exhausted its included quota and the paid path that
was standing in for it, so it can serve no request at all -- and `spending_dollars`
is the one the operator surfaces turn on. Every predicate fails CLOSED on an
absent meter: an account whose response carried no `extra_usage` block is never
reported as capped and never as spending, because not having read a meter is a
different fact from having read one that says something.
"""

from __future__ import annotations

import jsonio
from caam_decision_models import ExtraUsage, UsageRecord, WindowDollars

__all__: list[str] = [
    "dollars_left",
    "extra_usage_from",
    "spend_capped",
    "spending_dollars",
    "window_dollars_from",
]

_NOTHING_SPENT = 0.0
_NO_SCALE_DECIMAL_PLACES = 0


def extra_usage_from(*, body: dict[str, object]) -> ExtraUsage | None:
    """The dollar meter as the response reports it, or None when it reports none.

    Both flags are read as `is True` rather than for truthiness, which is the
    fail-closed direction on the one dimension where a wrong reading costs money:
    a string, a number or anything else the response might carry in place of a
    boolean arms nothing.

    `monthly_limit` and `used_credits` arrive in MINOR units (cents for USD),
    scaled by the response's own `decimal_places` -- measured live: `used_credits:
    10737, monthly_limit: 10000, decimal_places: 2`, i.e. $107.37 spent of a
    $100.00 cap. Reading those two fields as already-dollars printed an ALERT two
    orders of magnitude too high while the account was, correctly, capped.
    """
    block = jsonio.as_object(value=body.get("extra_usage"))
    if block is None:
        return None
    decimal_places = _decimal_places(block=block)
    return ExtraUsage(
        is_enabled=block.get("is_enabled") is True,
        spend_limit_reached=block.get("spend_limit_reached") is True,
        monthly_limit=_major_units(
            value=jsonio.as_float(value=block.get("monthly_limit")), decimal_places=decimal_places
        ),
        used_credits=_major_units(
            value=jsonio.as_float(value=block.get("used_credits")), decimal_places=decimal_places
        ),
    )


def _decimal_places(*, block: dict[str, object]) -> int:
    """How many fractional digits the block's minor-unit figures scale by.

    A response that never reports `decimal_places` is read as scale zero, which
    leaves the raw figure untouched -- the correct reading for a fixture written
    before the field shipped, since inventing a scale the response never named
    would be a guess, not a reading.
    """
    value = jsonio.as_float(value=block.get("decimal_places"))
    return _NO_SCALE_DECIMAL_PLACES if value is None else int(value)


def _major_units(*, value: float | None, decimal_places: int) -> float | None:
    """A minor-unit figure (cents) converted to its major unit (dollars)."""
    return None if value is None else value / (10**decimal_places)


def window_dollars_from(*, window: dict[str, object]) -> WindowDollars | None:
    """The dollar figures one usage window reports, or None when it reports none.

    All three are null on a Max subscription, so None is the ORDINARY answer here
    rather than an edge case. Reporting an all-null record instead would claim a
    reading the response never made, which is exactly the confusion between "no
    figure" and "a figure of nothing" this module exists to keep apart.
    """
    dollars = WindowDollars(
        limit=jsonio.as_float(value=window.get("limit_dollars")),
        used=jsonio.as_float(value=window.get("used_dollars")),
        remaining=jsonio.as_float(value=window.get("remaining_dollars")),
    )
    if dollars.limit is None and dollars.used is None and dollars.remaining is None:
        return None
    return dollars


def spend_capped(*, usage: UsageRecord | None) -> bool:
    """Whether this account has reached its monthly extra-usage spend limit.

    The disqualifying fact. An account here has spent its included quota AND the
    dollar allowance that was covering it afterwards, so it cannot serve a
    request immediately -- the same class as an account with nothing left on its
    weekly allowance, and the same answer: not a candidate, and a reason to leave
    when it is the account in use.

    An unread account answers False, because being unreadable is a different fact
    that the live-verification rule already carries; this predicate must not
    quietly stand in for it.
    """
    return (
        usage is not None
        and usage.extra_usage is not None
        and usage.extra_usage.spend_limit_reached
    )


def spending_dollars(*, extra_usage: ExtraUsage | None) -> bool:
    """Whether this account has actually spent pay-as-you-go dollars this month.

    Keyed on dollars SPENT rather than on the enabled flag, because the two
    disagree in BOTH directions and the spend is what costs money. An account
    auto-disabled on reaching its cap reads `is_enabled` false while every dollar
    of that cap is gone; a designated last-resort paid account reads it true from
    the moment it is armed, long before it costs anything.
    """
    return (
        extra_usage is not None
        and extra_usage.used_credits is not None
        and extra_usage.used_credits > _NOTHING_SPENT
    )


def dollars_left(*, extra_usage: ExtraUsage | None) -> float | None:
    """What the monthly dollar cap has LEFT -- the direction every quota figure runs in.

    None when there is no cap to measure against, which is the reading for an
    account that never enabled extra usage at all: it has no dollar balance, not
    a balance of nothing.

    Never negative. A cap can be overshot inside a single request -- measured
    2026-09-08 at $107.37 spent against a $100 cap -- and reporting minus seven
    dollars as a balance would read as a debt owed rather than as nothing left.
    """
    if extra_usage is None or extra_usage.monthly_limit is None:
        return None
    spent = _NOTHING_SPENT if extra_usage.used_credits is None else extra_usage.used_credits
    return max(_NOTHING_SPENT, extra_usage.monthly_limit - spent)
