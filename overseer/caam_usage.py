"""Credential parsing and usage polling for caam account rotation.

The provider REQUEST itself lives in `caam_oauth_get`, which the capacity source
reads its own endpoint through. What stays here is everything specific to the
usage answer: which credential a token comes out of, whether that token is still
live, and the usage record one response parses into.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Final

import jsonio
from caam_decision import UsageLimit, UsageRecord
from caam_extra_usage import extra_usage_from, window_dollars_from
from caam_oauth_get import OAuthRequest, OAuthTransport, get_json

__all__: list[str] = [
    "USAGE_URL",
    "fetch_usage",
    "live_token",
    "read_creds",
    "remaining_from_utilization",
]

USAGE_URL: Final = "https://api.anthropic.com/api/oauth/usage"
_EXPIRY_SKEW_S: Final = 60.0
_FULL_ALLOWANCE: Final = 100.0


def remaining_from_utilization(*, utilization: float) -> float:
    """THE boundary between the two directions a quota percentage can run in.

    The usage response reports UTILIZATION -- how much of an allowance has been
    spent -- and everything past this call holds and says REMAINING. Deriving
    from utilization is what the specification requires and is unchanged; what
    this function buys is that the derivation happens in exactly one named
    place, so a reader never has to work out which way an unlabelled figure runs
    and the two directions cannot circulate side by side unannounced.
    """
    return _FULL_ALLOWANCE - utilization


def read_creds(*, path: Path) -> tuple[str | None, float | None]:
    """Return (access_token, expires_at_epoch_seconds). Either may be None."""

    try:
        oauth = _oauth_object(path=path)
    except (OSError, ValueError):
        return None, None
    if oauth is None:
        return None, None

    token_value = oauth.get("accessToken")
    expires_value = oauth.get("expiresAt")
    token = token_value if isinstance(token_value, str) else None
    expires_at = jsonio.as_float(value=expires_value)
    return token, None if expires_at is None else expires_at / 1000.0


def live_token(*, path: Path, now: float | None = None) -> tuple[str | None, str | None]:
    """Token from a snapshot, but only if it has not already expired."""

    checked_at = time.time() if now is None else now
    token, expires_at = read_creds(path=path)
    if token is None:
        return None, "no token in snapshot"
    if expires_at is not None and expires_at <= checked_at + _EXPIRY_SKEW_S:
        return None, "token expired %.1fh ago" % ((checked_at - expires_at) / 3600)
    return token, None


def fetch_usage(
    *,
    creds_path: Path,
    now: float | None = None,
    transport: OAuthTransport | None = None,
) -> tuple[UsageRecord | None, str | None]:
    """Return (usage, None) or (None, reason). Never raises."""

    token, why = live_token(path=creds_path, now=now)
    if token is None:
        return None, why

    body, why = get_json(
        request=OAuthRequest(url=USAGE_URL, headers={"Authorization": "Bearer " + token}),
        transport=transport,
    )
    if body is None:
        return None, why
    return _usage_record(body=body)


def _oauth_object(*, path: Path) -> dict[str, object] | None:
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    if jsonio.is_parse_failure(result=parsed):
        return None
    body = parsed.unwrap()
    if body is None:
        return None
    return jsonio.as_object(value=body.get("claudeAiOauth"))


def _usage_record(*, body: dict[str, object]) -> tuple[UsageRecord | None, str | None]:
    try:
        limits = _limits(body=body)
    except ValueError:
        return None, "unexpected response shape"

    five_hour = _limit(limits=limits, kind="five_hour")
    seven_day = _limit(limits=limits, kind="weekly_all")
    fable = _fable_limit(limits=limits)
    record = UsageRecord(
        five_hour_remaining=None if five_hour is None else five_hour.remaining,
        seven_day_remaining=None if seven_day is None else seven_day.remaining,
        five_hour_resets_at=None if five_hour is None else five_hour.resets_at,
        seven_day_resets_at=None if seven_day is None else seven_day.resets_at,
        fable_remaining=None if fable is None else fable.remaining,
        fable_resets_at=None if fable is None else fable.resets_at,
        # The dollar meter rides on the SAME response, and is read here rather
        # than through a second request: an account can be stopped by it while
        # every percentage above still reads healthy, so a record carrying only
        # the percentages describes an account it cannot account for.
        extra_usage=extra_usage_from(body=body),
        five_hour_dollars=_window_dollars(limit=five_hour),
        seven_day_dollars=_window_dollars(limit=seven_day),
    )
    object.__setattr__(record, "_limits", limits)
    return record, None


def _limits(*, body: dict[str, object]) -> tuple[UsageLimit, ...]:
    values = jsonio.as_list(value=body.get("limits"))
    if values is None:
        raise ValueError
    if values:
        listed = tuple(_usage_limit(value=value) for value in values)
        return (*_legacy_known_limits(body=body, listed=listed), *listed)
    return _legacy_limits(body=body)


def _legacy_known_limits(
    *, body: dict[str, object], listed: tuple[UsageLimit, ...]
) -> tuple[UsageLimit, ...]:
    """Keep old mixed responses readable while the list rollout completes."""
    known = {limit.kind for limit in listed}
    return tuple(
        _legacy_limit(body=body, body_key=body_key, kind=kind)
        for body_key, kind in (("five_hour", "five_hour"), ("seven_day", "weekly_all"))
        if kind not in known and jsonio.as_object(value=body.get(body_key)) is not None
    )


def _legacy_limits(*, body: dict[str, object]) -> tuple[UsageLimit, ...]:
    """Read the pre-list response shape only while providers still emit it."""
    return tuple(
        _legacy_limit(body=body, body_key=body_key, kind=kind)
        for body_key, kind in (("five_hour", "five_hour"), ("seven_day", "weekly_all"))
    )


def _legacy_limit(*, body: dict[str, object], body_key: str, kind: str) -> UsageLimit:
    limit = jsonio.as_object(value=body.get(body_key)) or {}
    utilization = _required_float(value=limit.get("utilization"))
    return UsageLimit(
        kind=kind,
        remaining=remaining_from_utilization(utilization=utilization),
        resets_at=_optional_string(value=limit.get("resets_at")),
        dollars=window_dollars_from(window=limit),
    )


def _usage_limit(*, value: object) -> UsageLimit:
    limit = jsonio.as_object(value=value)
    if limit is None:
        raise ValueError
    kind = limit.get("kind")
    parsed = jsonio.as_float(value=limit.get("percent"))
    if kind == "weekly_scoped" and parsed is None:
        parsed = 0.0
    if not isinstance(kind, str) or parsed is None:
        raise ValueError
    return UsageLimit(
        kind=kind,
        remaining=remaining_from_utilization(utilization=parsed),
        resets_at=_optional_string(value=limit.get("resets_at")),
        model=_limit_model(limit=limit),
        dollars=window_dollars_from(window=limit),
    )


def _limit(*, limits: tuple[UsageLimit, ...], kind: str) -> UsageLimit | None:
    return next((limit for limit in limits if limit.kind == kind), None)


def _window_dollars(*, limit: UsageLimit | None):
    return None if limit is None else limit.dollars


def _required_float(*, value: object) -> float:
    parsed = jsonio.as_float(value=value)
    if parsed is None:
        raise ValueError
    return parsed


def _fable_limit(*, limits: tuple[UsageLimit, ...]) -> UsageLimit | None:
    return next(
        (limit for limit in limits if limit.kind == "weekly_scoped" and limit.model == "Fable"),
        None,
    )


def _limit_model(*, limit: dict[str, object]) -> str | None:
    scope = jsonio.as_object(value=limit.get("scope")) or {}
    model = jsonio.as_object(value=scope.get("model")) or {}
    name = model.get("display_name")
    return name if isinstance(name, str) else None


def _optional_string(*, value: object) -> str | None:
    return value if isinstance(value, str) else None
