"""Credential parsing and usage polling for caam account rotation."""

from __future__ import annotations

import http.client
import io
import json
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import jsonio
from caam_decision import UsageRecord

__all__: list[str] = [
    "USAGE_URL",
    "fetch_usage",
    "live_token",
    "read_creds",
]

USAGE_URL: Final = "https://api.anthropic.com/api/oauth/usage"
_REQUEST_TIMEOUT_S: Final = 30.0
_EXPIRY_SKEW_S: Final = 60.0
_HTTP_ERROR_MINIMUM: Final = 400


@dataclass(frozen=True, kw_only=True)
class UsageRequest:
    url: str
    headers: dict[str, str]


class UsageHttpResponse(Protocol):
    def __enter__(self) -> UsageHttpResponse: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool | None: ...

    def read(self, *, size: int = -1) -> bytes: ...


class UsageTransport(Protocol):
    def __call__(self, request: UsageRequest, timeout: float) -> UsageHttpResponse: ...


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
    transport: UsageTransport | None = None,
) -> tuple[UsageRecord | None, str | None]:
    """Return (usage, None) or (None, reason). Never raises."""

    token, why = live_token(path=creds_path, now=now)
    if token is None:
        return None, why

    request = UsageRequest(url=USAGE_URL, headers={"Authorization": "Bearer " + token})
    open_usage = _open_usage if transport is None else transport
    try:
        with open_usage(request=request, timeout=_REQUEST_TIMEOUT_S) as response:
            parsed: object = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return None, _http_error_reason(error=exc)
    except (OSError, TypeError, UnicodeDecodeError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"

    body = jsonio.as_object(value=parsed)
    if body is None:
        return None, "unexpected response shape"
    return _usage_record(body=body)


def _oauth_object(*, path: Path) -> dict[str, object] | None:
    body = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    if body is None:
        return None
    return jsonio.as_object(value=body.get("claudeAiOauth"))


@dataclass(kw_only=True)
class _HttpResponse:
    response: http.client.HTTPResponse

    def __enter__(self) -> _HttpResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        self.response.close()
        return False

    def read(self, *, size: int = -1) -> bytes:
        return self.response.read(size)


def _open_usage(*, request: UsageRequest, timeout: float) -> UsageHttpResponse:
    parsed = urllib.parse.urlsplit(request.url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError

    connection = http.client.HTTPSConnection(parsed.netloc, timeout=timeout)
    target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connection.request("GET", target, headers=request.headers)
    response = connection.getresponse()
    if response.status >= _HTTP_ERROR_MINIMUM:
        body = response.read()
        raise urllib.error.HTTPError(
            url=request.url,
            code=response.status,
            msg=response.reason,
            hdrs=response.headers,
            fp=io.BytesIO(body),
        )
    return _HttpResponse(response=response)


def _http_error_reason(*, error: urllib.error.HTTPError) -> str:
    try:
        parsed: object = json.loads(error.read().decode())
    except (OSError, TypeError, UnicodeDecodeError, ValueError):
        return f"HTTP {error.code}"

    body = jsonio.as_object(value=parsed)
    detail = jsonio.as_object(value=None if body is None else body.get("error"))
    message = None if detail is None else detail.get("message")
    return message if isinstance(message, str) else f"HTTP {error.code}"


def _usage_record(*, body: dict[str, object]) -> tuple[UsageRecord | None, str | None]:
    try:
        five_hour = _limit_object(body=body, key="five_hour")
        seven_day = _limit_object(body=body, key="seven_day")
        five_hour_usage = _required_float(value=five_hour.get("utilization"))
        seven_day_usage = _required_float(value=seven_day.get("utilization"))
    except ValueError:
        return None, "unexpected response shape"

    fable, fable_resets_at = _fable_limit(body=body)
    return (
        UsageRecord(
            five_hour=five_hour_usage,
            seven_day=seven_day_usage,
            five_hour_resets_at=_optional_string(value=five_hour.get("resets_at")),
            seven_day_resets_at=_optional_string(value=seven_day.get("resets_at")),
            fable=fable,
            fable_resets_at=fable_resets_at,
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
            return _fable_percent(limit=limit), _optional_string(value=limit.get("resets_at"))
    return None, None


def _is_fable_limit(*, limit: dict[str, object]) -> bool:
    scope = jsonio.as_object(value=limit.get("scope")) or {}
    model = jsonio.as_object(value=scope.get("model")) or {}
    return limit.get("kind") == "weekly_scoped" and model.get("display_name") == "Fable"


def _optional_string(*, value: object) -> str | None:
    return value if isinstance(value, str) else None


def _fable_percent(*, limit: dict[str, object]) -> float:
    return jsonio.as_float(value=limit.get("percent")) or 0.0
