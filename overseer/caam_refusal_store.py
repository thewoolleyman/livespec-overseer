"""What a pass must REMEMBER about refusals, in the operation's durable store.

Each key exists because attribution or the hold cannot be decided from a single
pass's readings:

``active_since``       the moment the operation last observed the active account
                       become active. A refusal recorded before it belongs to
                       whatever was active then, so without this the operation
                       would attribute an old refusal to a new account.
``refusals``           every refusal attributed to an account, with the reset
                       the provider reported and the reset that window's own
                       reading carried at the moment of attribution. The second
                       figure is what ends a hold for a refusal that reported no
                       reset.

CONCURRENT WRITERS MAY OVERWRITE ONE ANOTHER, and contracts.md bounds what that
costs: a lost refusal memory ends a hold early, at most one return follows and
the refusal is then attributed afresh; a lost activation time costs exactly one
pass on which nothing is attributed, because attribution fails closed without
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import jsonio
from caam_decision import UsageRecord, resets_at
from caam_refusals import WINDOW_FIVE_HOUR, WINDOW_SEVEN_DAY, Refusal

__all__: list[str] = [
    "Activation",
    "RememberedRefusal",
    "keep_refusals",
    "record_activation",
    "remember_refusals",
    "remembered_refusals",
]

_ACTIVE_SINCE: Final = "active_since"
_REFUSALS: Final = "refusals"
_WINDOWS: Final = frozenset({WINDOW_FIVE_HOUR, WINDOW_SEVEN_DAY})


@dataclass(frozen=True, kw_only=True)
class Activation:
    """When the active account was last observed to become active.

    ``fresh`` marks the pass that RECORDED the moment rather than reading it:
    the operation has no evidence of what was active before, so such a pass
    attributes no refusal at all rather than guessing one.
    """

    at: float
    fresh: bool


@dataclass(frozen=True, kw_only=True)
class RememberedRefusal:
    """One attributed refusal, against the account it was attributed to.

    ``window_reset_at`` is the reset the named window's reading carried when the
    refusal was attributed -- the baseline a later reading is compared against
    for a refusal that reported no reset of its own.
    """

    account: str
    refusal: Refusal
    window_reset_at: float | None


def record_activation(*, state: dict[str, object], active_name: str, now: float) -> Activation:
    """The moment this account became active, recording it where it is unknown.

    Where nothing is stored, or the stored record names a different account, the
    current pass's time is recorded and the pass is marked FRESH.
    """
    stored = jsonio.as_object(value=state.get(_ACTIVE_SINCE)) or {}
    account = stored.get("account")
    at = jsonio.as_float(value=stored.get("at"))
    if account == active_name and at is not None:
        return Activation(at=at, fresh=False)
    state[_ACTIVE_SINCE] = {"account": active_name, "at": now}
    return Activation(at=now, fresh=True)


def remember_refusals(
    *,
    state: dict[str, object],
    account: str,
    refusals: tuple[Refusal, ...],
    reading: UsageRecord,
) -> None:
    """Remember each attributed refusal against its account.

    A refusal already remembered is not remembered twice: a transcript keeps its
    records, so every later pass reads the same refusal again, and the baseline
    reset recorded with it must stay the one its FIRST attribution read.
    """
    kept = remembered_refusals(state=state)
    seen = {(entry.account, entry.refusal.recorded_at, entry.refusal.window) for entry in kept}
    fresh = tuple(
        RememberedRefusal(
            account=account,
            refusal=refusal,
            window_reset_at=_reading_reset(reading=reading, window=refusal.window),
        )
        for refusal in refusals
        if (account, refusal.recorded_at, refusal.window) not in seen
    )
    if fresh:
        keep_refusals(state=state, remembered=(*kept, *fresh))


def remembered_refusals(*, state: dict[str, object]) -> tuple[RememberedRefusal, ...]:
    """Every refusal the store remembers, in the order they were attributed."""
    stored = jsonio.as_list(value=state.get(_REFUSALS)) or []
    return tuple(
        remembered
        for value in stored
        for record in (jsonio.as_object(value=value) or {},)
        for remembered in _remembered(record=record)
    )


def keep_refusals(*, state: dict[str, object], remembered: tuple[RememberedRefusal, ...]) -> None:
    """Replace the remembered set, which is how a lapsed refusal is dropped."""
    state[_REFUSALS] = [
        {
            "account": entry.account,
            "window": entry.refusal.window,
            "recorded_at": entry.refusal.recorded_at,
            "resets_at": entry.refusal.resets_at,
            "window_reset_at": entry.window_reset_at,
            "identity": entry.refusal.account,
        }
        for entry in remembered
    ]


def _remembered(*, record: dict[str, object]) -> tuple[RememberedRefusal, ...]:
    account = record.get("account")
    window = record.get("window")
    recorded_at = jsonio.as_float(value=record.get("recorded_at"))
    if not isinstance(account, str) or window not in _WINDOWS or recorded_at is None:
        return ()
    identity = record.get("identity")
    return (
        RememberedRefusal(
            account=account,
            refusal=Refusal(
                recorded_at=recorded_at,
                window=window,
                resets_at=jsonio.as_float(value=record.get("resets_at")),
                account=identity if isinstance(identity, str) else None,
            ),
            window_reset_at=jsonio.as_float(value=record.get("window_reset_at")),
        ),
    )


def _reading_reset(*, reading: UsageRecord, window: str) -> float | None:
    raw = reading.five_hour_resets_at if window == WINDOW_FIVE_HOUR else reading.seven_day_resets_at
    reset = resets_at(timestamp=raw)
    return None if reset == float("inf") else reset
