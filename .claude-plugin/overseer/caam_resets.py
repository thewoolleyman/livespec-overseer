"""Provider-neutral quota-reset records and policy helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from math import inf
from urllib.parse import quote

import jsonio

__all__: list[str] = [
    "ClaimRequest",
    "QuotaReset",
    "ResetReading",
    "claim_identifier",
    "claim_request",
    "exhausted_claim",
    "lapsing_claim",
    "parse_anthropic_resets",
]


@dataclass(frozen=True, kw_only=True)
class QuotaReset:
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
    resets: tuple[QuotaReset, ...]
    unreadable_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class ClaimRequest:
    url: str
    body: dict[str, str]


def parse_anthropic_resets(*, body: dict[str, object]) -> ResetReading:
    """Map the reset blocks included in Anthropic's usage response."""
    generic = body.get("rate_limit_resets")
    if generic is not None:
        records = jsonio.as_list(value=generic)
        if records is None:
            error = jsonio.as_object(value=generic) or {}
            reason = error.get("error")
            return ResetReading(
                resets=(),
                unreadable_reason=(
                    reason if isinstance(reason, str) else "provider declined reset reading"
                ),
            )
        return ResetReading(
            resets=tuple(
                _record_reset(record=record)
                for value in records
                if (record := jsonio.as_object(value=value)) is not None
            )
        )
    cedar = jsonio.as_object(value=body.get("cedar_ember"))
    juniper = jsonio.as_object(value=body.get("juniper_tide"))
    if _declined(block=cedar) or _declined(block=juniper):
        return ResetReading(resets=(), unreadable_reason="client surface is ineligible")
    grants = None if cedar is None else jsonio.as_list(value=cedar.get("grants"))
    cedar_resets = tuple(
        _cedar_reset(grant=grant)
        for value in grants or []
        if (grant := jsonio.as_object(value=value)) is not None
    )
    return ResetReading(resets=(*cedar_resets, *_juniper_reset(block=juniper)))


def _resets_at(*, timestamp: str | None) -> float:
    if not timestamp:
        return inf
    normalized = timestamp.removesuffix("Z") + "+00:00" if timestamp.endswith("Z") else timestamp
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return inf


def claim_request(*, organization_uuid: str, reset: QuotaReset, request_id: str) -> ClaimRequest:
    """Build, but do not send, Anthropic's idempotent reset request."""
    body = {"program": reset.program, "request_id": request_id}
    if reset.reset_id is not None:
        body["grant_id"] = reset.reset_id
    return ClaimRequest(
        url=(
            "https://api.anthropic.com/api/organizations/"
            f"{quote(organization_uuid, safe='')}/reset_rate_limits"
        ),
        body=body,
    )


def exhausted_claim(
    *, resets: tuple[QuotaReset, ...], triggered: frozenset[str], at_limit: frozenset[str]
) -> QuotaReset | None:
    """Pick the narrowest usable reset that clears every triggered window."""
    qualifying = tuple(
        reset
        for reset in resets
        if reset.usable_now
        and reset.uses_left > 0
        and triggered.issubset(reset.clears)
        and (not reset.requires_limit or bool(at_limit & frozenset(reset.clears)))
    )
    return min(
        qualifying,
        key=lambda reset: (len(reset.clears), _resets_at(timestamp=reset.lapses_at), reset.program),
        default=None,
    )


def lapsing_claim(
    *,
    resets: tuple[QuotaReset, ...],
    spent: Mapping[str, float],
    at_limit: frozenset[str],
    now: float,
    eligibility_margin: float,
    expiry_horizon_s: float,
) -> QuotaReset | None:
    """Pick the soonest meaningful reset that will lapse within the horizon."""
    qualifying = tuple(
        reset
        for reset in resets
        if reset.usable_now
        and reset.uses_left > 0
        and (not reset.requires_limit or bool(at_limit & frozenset(reset.clears)))
        and now <= _resets_at(timestamp=reset.lapses_at) <= now + expiry_horizon_s
        and any(spent.get(window, 0.0) >= eligibility_margin for window in reset.clears)
    )
    return min(qualifying, key=lambda reset: _resets_at(timestamp=reset.lapses_at), default=None)


def claim_identifier(
    *, state: dict[str, object], account: str, reset: QuotaReset, new_id: Callable[[], str]
) -> str:
    """Persist and reuse the idempotency key for one account reset."""
    records = jsonio.as_object(value=state.get("reset_claims"))
    if records is None:
        records = {}
        state["reset_claims"] = records
    key = f"{account}:{reset.program}:{reset.reset_id or reset.program}"
    recorded = records.get(key)
    if isinstance(recorded, str):
        return recorded
    identifier = new_id()
    records[key] = identifier
    return identifier


def _record_reset(*, record: Mapping[str, object]) -> QuotaReset:
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


def _cedar_reset(*, grant: Mapping[str, object]) -> QuotaReset:
    return QuotaReset(
        program="cedar_ember",
        reset_id=_string(value=grant.get("id")),
        clears=_strings(value=grant.get("clears")),
        uses_left=_integer(value=grant.get("resets_left")),
        uses_total=_integer(value=grant.get("resets_total")),
        lapses_at=_string(value=grant.get("ends_at")),
        usable_now=grant.get("usable_now") is True,
        requires_limit=grant.get("use_requires_limit") is True,
    )


def _juniper_reset(*, block: Mapping[str, object] | None) -> tuple[QuotaReset, ...]:
    if block is None or "resets_per_week" not in block:
        return ()
    total = _integer(value=block.get("resets_per_week"))
    return (
        QuotaReset(
            program="juniper_tide",
            reset_id=None,
            clears=("five_hour",),
            uses_left=total,
            uses_total=total,
            lapses_at=_string(value=block.get("weekly_resets_at")),
            usable_now=block.get("available") is True,
            requires_limit=True,
        ),
    )


def _declined(*, block: Mapping[str, object] | None) -> bool:
    return (
        block is not None
        and block.get("eligible") is False
        and block.get("ineligible_reason") == "surface"
    )


def _strings(*, value: object) -> tuple[str, ...]:
    return tuple(entry for entry in jsonio.as_list(value=value) or [] if isinstance(entry, str))


def _string(*, value: object) -> str | None:
    return value if isinstance(value, str) else None


def _integer(*, value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
