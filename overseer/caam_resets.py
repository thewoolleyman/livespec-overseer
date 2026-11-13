"""Provider-neutral quota resets and the policy that chooses one to spend.

The Anthropic adapter owns its wire shape.  This module deliberately knows only
what a reset does to allowances, which keeps selection independent of the
provider that supplied it and gives a future provider one small interface to
implement.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import inf
from typing import cast

from caam_decision import resets_at

__all__: list[str] = [
    "QuotaReset",
    "ResetReading",
    "claim_identifier",
    "exhausted_claim",
    "lapsing_claim",
    "parse_anthropic_resets",
]


@dataclass(frozen=True, kw_only=True)
class QuotaReset:
    """One provider reset, expressed in terms every selection rule understands."""

    program: str
    reset_id: str | None
    clears: tuple[str, ...]
    uses_left: int
    uses_total: int
    lapses_at: str | None
    usable_now: bool
    requires_limit: bool


@dataclass(frozen=True, kw_only=True)
class ResetReading:
    """The resets an account holds, or the reason this client cannot read them."""

    resets: tuple[QuotaReset, ...]
    unreadable_reason: str | None = None


def parse_anthropic_resets(*, body: dict[str, object]) -> ResetReading:
    """Map Anthropic's two reset programs to the provider-neutral model.

    A client-surface refusal is deliberately distinct from a valid empty grant
    list.  The former says nothing about the account and must render as
    unreadable; the latter says the account currently holds no expiring grant.
    """
    generic = body.get("rate_limit_resets")
    if generic is not None:
        return _generic_reading(value=generic)
    blocks = tuple(
        value for value in (body.get("cedar_ember"), body.get("juniper_tide")) if value is not None
    )
    refusal = next((_surface_refusal(value=value) for value in blocks), None)
    if refusal is not None:
        return ResetReading(resets=(), unreadable_reason=refusal)
    cedar = _cedar_resets(value=body.get("cedar_ember"))
    juniper = _juniper_reset(value=body.get("juniper_tide"))
    return ResetReading(resets=(*cedar, *juniper))


def _generic_reading(*, value: object) -> ResetReading:
    if not isinstance(value, list):
        reason = _string(value=value.get("error")) if isinstance(value, dict) else None
        return ResetReading(
            resets=(), unreadable_reason=reason or "provider declined reset reading"
        )
    return ResetReading(
        resets=tuple(_generic_reset(record=record) for record in value if isinstance(record, dict))
    )


def _generic_reset(*, record: dict[str, object]) -> QuotaReset:
    return QuotaReset(
        program=_string(value=record.get("program")) or "unknown",
        reset_id=_string(value=record.get("grant_id")),
        clears=_strings(value=record.get("clears")),
        uses_left=_integer(value=record.get("uses_remaining")),
        uses_total=_integer(value=record.get("uses_total")),
        lapses_at=_string(value=record.get("expires_at")),
        usable_now=record.get("usable_now") is True,
        requires_limit=record.get("use_requires_limit") is True,
    )


def _surface_refusal(*, value: object) -> str | None:
    if not isinstance(value, dict) or value.get("eligible") is not False:
        return None
    reason = _string(value=value.get("ineligible_reason"))
    return "client surface is ineligible" if reason == "surface" else None


def _cedar_resets(*, value: object) -> tuple[QuotaReset, ...]:
    if not isinstance(value, dict):
        return ()
    grants = value.get("grants")
    if not isinstance(grants, list):
        return ()
    return tuple(
        QuotaReset(
            program="cedar_ember",
            reset_id=_string(value=grant.get("id")),
            clears=_strings(value=grant.get("clears")),
            uses_left=_integer(value=grant.get("resets_left")),
            uses_total=_integer(value=grant.get("resets_total")),
            lapses_at=_string(value=grant.get("ends_at")),
            usable_now=grant.get("usable_now") is True,
            requires_limit=grant.get("use_requires_limit") is True,
        )
        for grant in grants
        if isinstance(grant, dict)
    )


def _juniper_reset(*, value: object) -> tuple[QuotaReset, ...]:
    if not isinstance(value, dict) or "resets_per_week" not in value:
        return ()
    total = _integer(value=value.get("resets_per_week"))
    return (
        QuotaReset(
            program="juniper_tide",
            reset_id=None,
            clears=("five_hour",),
            uses_left=total,
            uses_total=total,
            lapses_at=_string(value=value.get("weekly_resets_at")),
            usable_now=value.get("available") is True,
            requires_limit=True,
        ),
    )


def _strings(*, value: object) -> tuple[str, ...]:
    return (
        tuple(entry for entry in value if isinstance(entry, str)) if isinstance(value, list) else ()
    )


def _string(*, value: object) -> str | None:
    return value if isinstance(value, str) else None


def _integer(*, value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def exhausted_claim(
    *, resets: tuple[QuotaReset, ...], triggered: frozenset[str], at_limit: frozenset[str]
) -> QuotaReset | None:
    """The narrowest usable reset that clears every window which fired.

    A provider may offer one reset that repairs a five-hour limit and another
    that repairs that limit plus the weekly budget.  Spending the narrow one
    preserves the broader grant for the case that actually needs it.
    """
    qualifying = tuple(
        reset
        for reset in resets
        if _usable(reset=reset, at_limit=at_limit) and triggered.issubset(reset.clears)
    )
    return min(qualifying, key=lambda reset: _narrowness_key(reset=reset), default=None)


def lapsing_claim(
    *,
    resets: tuple[QuotaReset, ...],
    spent: Mapping[str, float],
    at_limit: frozenset[str],
    now: float,
    eligibility_margin: float,
    expiry_horizon_s: float,
) -> QuotaReset | None:
    """The soonest-lapsing reset that would recover a meaningful allowance."""
    qualifying = tuple(
        reset
        for reset in resets
        if _usable(reset=reset, at_limit=at_limit)
        and _within_horizon(reset=reset, now=now, horizon=expiry_horizon_s)
        and any(spent.get(window, 0.0) >= eligibility_margin for window in reset.clears)
    )
    return min(qualifying, key=lambda reset: _lapse(reset=reset), default=None)


def claim_identifier(
    *, state: dict[str, object], account: str, reset: QuotaReset, new_id: Callable[[], str]
) -> str:
    """Persist and reuse a request identifier before the irreversible request.

    The claim memo lives outside the overwriteable polling cache.  A reporter
    may update that cache concurrently, but cannot discard this record and turn
    a retry into a second spend.
    """
    records = _claim_records(state=state)
    key = _reset_key(account=account, reset=reset)
    record = records.get(key)
    if isinstance(record, str):
        return record
    identifier = new_id()
    records[key] = identifier
    return identifier


def _claim_records(*, state: dict[str, object]) -> dict[str, object]:
    records = state.get("reset_claims")
    if isinstance(records, dict):
        return cast(dict[str, object], records)
    created: dict[str, object] = {}
    state["reset_claims"] = created
    return created


def _reset_key(*, account: str, reset: QuotaReset) -> str:
    identifier = reset.reset_id or reset.program
    return f"{account}:{reset.program}:{identifier}"


def _usable(*, reset: QuotaReset, at_limit: frozenset[str]) -> bool:
    return (
        reset.usable_now
        and reset.uses_left > 0
        and bool(reset.clears)
        and (not reset.requires_limit or bool(at_limit & frozenset(reset.clears)))
    )


def _narrowness_key(*, reset: QuotaReset) -> tuple[int, float, str]:
    return (len(reset.clears), _lapse(reset=reset), reset.program)


def _lapse(*, reset: QuotaReset) -> float:
    return resets_at(timestamp=reset.lapses_at)


def _within_horizon(*, reset: QuotaReset, now: float, horizon: float) -> bool:
    lapse = _lapse(reset=reset)
    return lapse != inf and now <= lapse <= now + horizon
