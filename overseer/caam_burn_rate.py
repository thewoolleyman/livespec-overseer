"""The SHORT-WINDOW BURN RATE, and the baseline reading it is measured from.

A percentage read on one pass says how much an account has left. It cannot say
how fast that balance is falling, and the short-window floor protects an account
only if the account cannot spend its remaining margin between two passes --
which, measured on host hp 2026-10-13, a small plan under fleet load can: an
account on a $20 plan fell about 70 short-window points in one 30-minute pass
where a $200 account fell about 10. So the operation remembers ONE reading of
the active account's short window and measures the fall across to the next.

THE PROJECTION HORIZON IS THE OPERATION'S OWN, not the schedule's. It defaults
to the documented interval of the schedule the operation installs, but it is
configurable independently of it and is read from here rather than from any
schedule, because the executable cannot read the schedule it was installed
under, duplicate schedules can run closer together, and an invocation without
the scheduled marker has no interval at all.

FOUR THINGS MAKE A BURN RATE UNKNOWN, and each is a case where the arithmetic
would be a measurement of something other than this account spending this
window: two readings of DIFFERENT short windows (the window reset between them,
so the balance rose), readings taken across a SWITCH (the fall belongs partly to
another account), readings of a different ACCOUNT, and readings CLOSER TOGETHER
than half a horizon (one percentage step amplified into a large rate). Unknown
is the whole answer in each -- never a defaulted rate, because every consumer of
a rate here uses it to decide whether to leave an account.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

import jsonio
from caam_decision import UsageRecord, resets_at
from caam_refusal_store import activation_at

__all__: list[str] = [
    "SHORT_WINDOW_BASELINE",
    "BaselineReading",
    "baseline_reading",
    "burn_rate",
    "projection_horizon_s",
    "replace_baseline",
]

SHORT_WINDOW_BASELINE: Final = "short_window_baseline"
# The documented interval of the schedule this operation installs, which is the
# default the ratified **Schedule** contract gives the horizon.
_DEFAULT_HORIZON_S: Final = "1800"
# The same tolerance the expiring-quota drain compares two reported resets with.
_RESET_TOLERANCE_S: Final = 60.0


def projection_horizon_s() -> float:
    """How far ahead the operation projects a short window, in seconds."""
    return float(os.environ.get("CAAM_ROTATE_PROJECTION_HORIZON_S", _DEFAULT_HORIZON_S))


@dataclass(frozen=True, kw_only=True)
class BaselineReading:
    """The remembered reading a burn rate is measured from.

    `resets_at` is kept as the provider's own string rather than a parsed
    instant so that a reading whose reset could not be read is remembered as
    exactly that -- unreadable -- rather than as an instant the comparison would
    then have to reserve a value for.
    """

    account: str
    remaining: float
    resets_at: str | None
    at: float


def baseline_reading(*, state: dict[str, object]) -> BaselineReading | None:
    """The remembered baseline, or None where the store holds no usable one."""
    stored = jsonio.as_object(value=state.get(SHORT_WINDOW_BASELINE)) or {}
    account = stored.get("account")
    at = jsonio.as_float(value=stored.get("at"))
    remaining = jsonio.as_float(value=stored.get("remaining"))
    if not isinstance(account, str) or at is None or remaining is None:
        return None
    raw_reset = stored.get("resets_at")
    return BaselineReading(
        account=account,
        remaining=remaining,
        resets_at=raw_reset if isinstance(raw_reset, str) else None,
        at=at,
    )


def replace_baseline(
    *, state: dict[str, object], active_name: str, current: UsageRecord, now: float
) -> None:
    """Remember this pass's reading, where the ratified rule allows it to.

    A VALID baseline -- one taken of the current active account and of the same
    short window -- is kept until this reading is at least half a horizon after
    it, so that closely spaced passes measure across the older baseline rather
    than amplifying one percentage step into a large rate. Anything else is
    replaced, because it cannot be measured against at all.
    """
    short = current.limit(kind="five_hour")
    if short is None:
        _ = state.pop(SHORT_WINDOW_BASELINE, None)
        return
    stored = baseline_reading(state=state)
    if (
        stored is not None
        and stored.account == active_name
        and _same_short_window(baseline=stored, current=current)
        and now - stored.at < projection_horizon_s() / 2
    ):
        return
    state[SHORT_WINDOW_BASELINE] = {
        "account": active_name,
        "remaining": short.remaining,
        "resets_at": short.resets_at,
        "at": now,
    }


def burn_rate(
    *, state: dict[str, object], active_name: str, current: UsageRecord, now: float
) -> float | None:
    """Short-window points per second, or None where the rate is UNKNOWN.

    Read BEFORE the baseline is replaced on every pass: a pass that overwrote
    the baseline first would measure every fall against its own reading.
    """
    short = current.limit(kind="five_hour")
    if short is None:
        return None
    baseline = baseline_reading(state=state)
    if baseline is None:
        return None
    elapsed = now - baseline.at
    if (
        baseline.account != active_name
        or not _same_short_window(baseline=baseline, current=current)
        or elapsed < projection_horizon_s() / 2
        or _activated_after(state=state, baseline=baseline)
    ):
        return None
    return (baseline.remaining - short.remaining) / elapsed


def _same_short_window(*, baseline: BaselineReading, current: UsageRecord) -> bool:
    """Whether two readings describe ONE short window, within the tolerance.

    An unreadable reset on either side answers no, and it does so through the
    arithmetic rather than through a guard of its own: the difference against an
    unreadable reset is infinite, the difference between two of them is not a
    number, and neither is within any tolerance.
    """
    stored = resets_at(timestamp=baseline.resets_at)
    short = current.limit(kind="five_hour")
    if short is None:
        return False
    reading = resets_at(timestamp=short.resets_at)
    return abs(reading - stored) <= _RESET_TOLERANCE_S


def _activated_after(*, state: dict[str, object], baseline: BaselineReading) -> bool:
    """Whether the active account became active after this baseline was taken.

    The stored activation always names the account the decision is about: the
    pass records it before the decision runs, rewriting it wherever it named
    another account, so reading the instant alone cannot be read off the wrong
    account. An activation the store cannot state at all answers YES, because a
    fall measured across an unknown switch belongs partly to another account.
    """
    activation = activation_at(state=state)
    return activation is None or activation > baseline.at
