"""What a pass must REMEMBER about refusals, in the operation's durable store.

Three keys, and each one exists because attribution or the hold cannot be
decided from a single pass's readings:

``active_since``       the moment the operation last observed the active account
                       become active. A refusal recorded before it belongs to
                       whatever was active then, so without this the operation
                       would attribute an old refusal to a new account.
``departed_accounts``  the short-window and weekly resets last read on each
                       account the operation has left and not yet returned to.
                       Concurrent sessions MAY still be spending a departed
                       account's credential after a switch, and their refusals
                       belong to it; the resets are what tell those refusals
                       apart from the new account's own.
``refusals``           every refusal attributed to an account, with the reset
                       the provider reported and the reset that window's own
                       reading carried at the moment of attribution. The second
                       figure is what ends a hold for a refusal that reported no
                       reset.

A FOURTH memory belongs to the same family and is NOT held here: the attribution
floor a lapsed refusal leaves, which `caam_refusal_lapse` owns, because dropping
a lapsed refusal from ``refusals`` does not stop the transcript it was read from
carrying the record.

CONCURRENT WRITERS MAY OVERWRITE ONE ANOTHER, and contracts.md bounds what that
costs: a lost refusal memory ends a hold early, at most one return follows and
the refusal is then attributed afresh; a lost departed entry can attribute a
lagging session's refusal to the new account, costing at most one switch off it;
a lost activation time costs exactly one pass on which nothing is attributed,
because attribution fails closed without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import jsonio
from caam_decision import ProfileUsage, UsageRecord, resets_at
from caam_refusals import WINDOW_FIVE_HOUR, WINDOW_SEVEN_DAY, Refusal

__all__: list[str] = [
    "Activation",
    "DepartedEntry",
    "RememberedRefusal",
    "departed_entries",
    "keep_refusals",
    "record_activation",
    "remember_refusals",
    "remembered_refusals",
]

_ACTIVE_SINCE: Final = "active_since"
_DEPARTED_ACCOUNTS: Final = "departed_accounts"
_REFUSALS: Final = "refusals"
_WINDOW_RESET_KEYS: Final = {
    WINDOW_FIVE_HOUR: "five_hour_resets_at",
    WINDOW_SEVEN_DAY: "seven_day_resets_at",
}


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
class DepartedEntry:
    """An account the operation has left, and the resets last read on it."""

    account: str
    five_hour_reset_at: float | None
    seven_day_reset_at: float | None


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


def record_activation(
    *,
    state: dict[str, object],
    active_name: str,
    profiles: tuple[ProfileUsage, ...],
    now: float,
) -> Activation:
    """The moment this account became active, recording it where it is unknown.

    Where nothing is stored, or the stored record names a different account, the
    current pass's time is recorded and the pass is marked FRESH. Recording an
    activation also departs the account the previous one named, whatever trigger
    the departure was made on and whether or not the operation made the switch
    itself -- an operator's hand switch is observed here exactly as the
    operation's own is.
    """
    stored = jsonio.as_object(value=state.get(_ACTIVE_SINCE)) or {}
    account = stored.get("account")
    at = jsonio.as_float(value=stored.get("at"))
    if account == active_name and at is not None:
        _keep_departed(state=state, active_name=active_name, now=now)
        return Activation(at=at, fresh=False)
    _depart(
        state=state,
        account=account if isinstance(account, str) else None,
        profiles=profiles,
    )
    state[_ACTIVE_SINCE] = {"account": active_name, "at": now}
    _keep_departed(state=state, active_name=active_name, now=now)
    return Activation(at=now, fresh=True)


def departed_entries(*, state: dict[str, object], active_name: str) -> tuple[DepartedEntry, ...]:
    """Every kept departed entry other than the active account's.

    An account returned to is never compared with its own reset times, which is
    what lets its own later refusal be attributed to it. Expiry is not judged
    here: `record_activation` has already dropped every entry whose later reset
    has passed, so what remains is by construction still departed.
    """
    stored = jsonio.as_object(value=state.get(_DEPARTED_ACCOUNTS)) or {}
    return tuple(
        DepartedEntry(
            account=account,
            five_hour_reset_at=_stored_reset(record=record, window=WINDOW_FIVE_HOUR),
            seven_day_reset_at=_stored_reset(record=record, window=WINDOW_SEVEN_DAY),
        )
        for account, value in stored.items()
        for record in (jsonio.as_object(value=value) or {},)
        if account != active_name
    )


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
    if not isinstance(account, str) or window not in _WINDOW_RESET_KEYS or recorded_at is None:
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


def _depart(
    *,
    state: dict[str, object],
    account: str | None,
    profiles: tuple[ProfileUsage, ...],
) -> None:
    if account is None:
        return
    reading = next(
        (profile.usage for profile in profiles if profile.name == account and profile.usage),
        None,
    )
    stored = jsonio.as_object(value=state.get(_DEPARTED_ACCOUNTS)) or {}
    state[_DEPARTED_ACCOUNTS] = {
        **stored,
        account: {
            "five_hour_resets_at": None if reading is None else reading.five_hour_resets_at,
            "seven_day_resets_at": None if reading is None else reading.seven_day_resets_at,
        },
    }


def _keep_departed(*, state: dict[str, object], active_name: str, now: float) -> None:
    """Drop the active account's entry, and any entry both of whose resets passed."""
    stored = jsonio.as_object(value=state.get(_DEPARTED_ACCOUNTS))
    if stored is None:
        return
    state[_DEPARTED_ACCOUNTS] = {
        account: value
        for account, value in stored.items()
        if account != active_name and _still_departed(value=value, now=now)
    }


def _still_departed(*, value: object, now: float) -> bool:
    record = jsonio.as_object(value=value) or {}
    latest = max(
        (
            reset
            for window in _WINDOW_RESET_KEYS
            for reset in (_stored_reset(record=record, window=window),)
            if reset is not None
        ),
        default=None,
    )
    # An entry whose resets could not be read at all is kept: it cannot be shown
    # to have expired, and dropping it would re-open the lagging-session window
    # the entry exists to close.
    return latest is None or now < latest


def _stored_reset(*, record: dict[str, object], window: str) -> float | None:
    raw = record.get(_WINDOW_RESET_KEYS[window])
    reset = resets_at(timestamp=raw if isinstance(raw, str) else None)
    return None if reset == float("inf") else reset


def _reading_reset(*, reading: UsageRecord, window: str) -> float | None:
    raw = reading.five_hour_resets_at if window == WINDOW_FIVE_HOUR else reading.seven_day_resets_at
    reset = resets_at(timestamp=raw)
    return None if reset == float("inf") else reset
