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
from caam_decision import UsageRecord
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
        seven_day = _limit_object(body=body, key="seven_day")
        five_hour = (
            _limit_object(body=body, key="five_hour") if body.get("five_hour") is not None else None
        )
        short_window_present = five_hour is not None
        if short_window_present:
            five_hour_left = remaining_from_utilization(
                utilization=_required_float(value=five_hour.get("utilization"))
            )
        else:
            five_hour_left = 100.0
        seven_day_left = remaining_from_utilization(
            utilization=_required_float(value=seven_day.get("utilization"))
        )
    except ValueError:
        return None, "unexpected response shape"

    fable_left, fable_resets_at = _fable_limit(body=body)
    return (
        UsageRecord(
            five_hour_remaining=five_hour_left,
            seven_day_remaining=seven_day_left,
            five_hour_resets_at=(
                _optional_string(value=five_hour.get("resets_at"))
                if five_hour is not None
                else None
            ),
            seven_day_resets_at=_optional_string(value=seven_day.get("resets_at")),
            fable_remaining=fable_left,
            fable_resets_at=fable_resets_at,
            # The dollar meter rides on the SAME response, and is read here rather
            # than through a second request: an account can be stopped by it while
            # every percentage above still reads healthy, so a record carrying only
            # the percentages describes an account it cannot account for.
            extra_usage=extra_usage_from(body=body),
            five_hour_dollars=window_dollars_from(window=five_hour)
            if five_hour is not None
            else None,
            seven_day_dollars=window_dollars_from(window=seven_day),
            short_window_present=short_window_present,
        ),
        None,
    )


def _limit_object(*, body: dict[str, object], key: str) -> dict[str, object]:
    value = jsonio.as_object(value=body.get(key))
    if value is None:
        raise ValueError
    return value


def _required_float(*, value: object) -> float:
    parsed = jsonio.as_float(value=value)
    if parsed is None:
        raise ValueError
    return parsed


def _fable_limit(*, body: dict[str, object]) -> tuple[float | None, str | None]:
    limits = jsonio.as_list(value=body.get("limits")) or []
    for limit_value in limits:
        limit = jsonio.as_object(value=limit_value)
        if limit is not None and _is_fable_limit(limit=limit):
            return _fable_remaining(limit=limit), _optional_string(value=limit.get("resets_at"))
    return None, None


def _is_fable_limit(*, limit: dict[str, object]) -> bool:
    scope = jsonio.as_object(value=limit.get("scope")) or {}
    model = jsonio.as_object(value=scope.get("model")) or {}
    return limit.get("kind") == "weekly_scoped" and model.get("display_name") == "Fable"


def _optional_string(*, value: object) -> str | None:
    return value if isinstance(value, str) else None


def _fable_remaining(*, limit: dict[str, object]) -> float:
    """What the scoped allowance has left, from the spent share the limit reports.

    An unreadable or absent `percent` reads as nothing spent, hence a full
    allowance -- the same OUTCOME the spent-direction default carried, since an
    account with an untouched scoped allowance can serve the pin either way.
    """
    return remaining_from_utilization(
        utilization=jsonio.as_float(value=limit.get("percent")) or 0.0
    )
