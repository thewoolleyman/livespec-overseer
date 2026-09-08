"""The operator-facing surfaces of the extra-usage dollar meter: the cells and the alert.

The stall this closes was SILENT, and that is the fact these two surfaces are
built around. On 2026-09-08 the pass printed a table of healthy percentages
every half hour while every session on the active account was being refused for
reaching a monthly DOLLAR cap, and nothing anywhere on the operator's surfaces
mentioned dollars at all. Reporting the state alone would have repeated that
failure at one remove -- a column is only read when someone is already looking
-- so the meter owes an ALERT as well, and the alert fires on the FIRST dollar
rather than at the cap, which is strictly earlier than "near" it.

Both surfaces live here so they cannot drift apart: the table says what is true
of every account, the alert says which of those facts needs somebody, and they
are the same reading.
"""

from __future__ import annotations

from caam_decision_models import ExtraUsage, ProfileUsage
from caam_extra_usage import dollars_left, spend_capped, spending_dollars

__all__: list[str] = [
    "extra_usage_cells",
    "spend_alert_lines",
]

_NO_READING = "-"
_UNKNOWN = "unknown"
_CAPPED = "CAPPED"

_CAPPED_ALERT = (
    "ALERT: {name} has reached its extra-usage monthly spend limit "
    "({used} spent of {limit}) -- it can serve no request and is not selectable"
)
_SPENDING_ALERT = (
    "ALERT: {name} is spending pay-as-you-go dollars "
    "({used} spent of {limit}, {left} left before it stops serving)"
)


def extra_usage_cells(*, extra_usage: ExtraUsage | None) -> tuple[str, str]:
    """The meter's STATE and its cap's remaining balance, as the table prints them.

    An account with no meter reading prints a dash in both, exactly as an
    unreadable percentage does, because that is the same fact: nothing was
    observed. It deliberately does NOT print "off" -- that would assert something
    about an account this pass never asked.
    """
    if extra_usage is None:
        return (_NO_READING, _NO_READING)
    return (
        _state_cell(extra_usage=extra_usage),
        _money(value=dollars_left(extra_usage=extra_usage), absent=_NO_READING),
    )


def spend_alert_lines(*, profiles: tuple[ProfileUsage, ...]) -> tuple[str, ...]:
    """One ALERT line per account that is spending dollars or has reached its cap.

    Nothing is emitted for a quiet fleet, and that silence is load-bearing: an
    alert every pass for an account that is merely ARMED to spend would be read
    past within a day, which is how a real one goes unnoticed. So the trigger is
    a dollar actually spent, and the line names what is left so an operator reads
    the proximity to the cap off the line itself.
    """
    return tuple(
        line for line in (alert_for(profile=profile) for profile in profiles) if line is not None
    )


def alert_for(*, profile: ProfileUsage) -> str | None:
    """This account's alert line, or None when it has nothing to report."""
    extra_usage = None if profile.usage is None else profile.usage.extra_usage
    used = _money(value=None if extra_usage is None else extra_usage.used_credits, absent=_UNKNOWN)
    limit = _money(
        value=None if extra_usage is None else extra_usage.monthly_limit, absent=_UNKNOWN
    )
    if spend_capped(usage=profile.usage):
        return _CAPPED_ALERT.format(name=profile.name, used=used, limit=limit)
    if spending_dollars(extra_usage=extra_usage):
        return _SPENDING_ALERT.format(
            name=profile.name,
            used=used,
            limit=limit,
            left=_money(value=dollars_left(extra_usage=extra_usage), absent=_UNKNOWN),
        )
    return None


def _state_cell(*, extra_usage: ExtraUsage) -> str:
    if extra_usage.spend_limit_reached:
        return _CAPPED
    return "on" if extra_usage.is_enabled else "off"


def _money(*, value: float | None, absent: str) -> str:
    """A dollar figure, or the caller's word for having no figure to print.

    The absent word differs by surface on purpose: a table cell that reads `-`
    everywhere else must read `-` here too, while a sentence needs a word.
    """
    return absent if value is None else f"${value:.2f}"
