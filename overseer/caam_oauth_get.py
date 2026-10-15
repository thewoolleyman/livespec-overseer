"""THE provider request boundary: one read-only, OAuth-authenticated GET.

Split out of `caam_usage` when a SECOND endpoint began being read with the same
credential and the same rules -- the capacity source's live plan read
(`caam_capacity_source`). The cut is by cohesion: everything here is how the
operation REACHES the provider, while the module it left holds credential
parsing and the usage record it builds out of one answer.

Keeping it in one place is what the specification's **Never refresh** rule
needs. Both reads must be read-only, neither may invoke the OAuth token
endpoint, and neither may acquire a retry, a redirect follow or a refresh the
other does not have; a boundary that exists once cannot drift between its two
consumers.

Every failure leaves here as a REASON rather than as an exception, because both
consumers report a failed read as a condition of the ACCOUNT rather than as a
failure of the pass.
"""

from __future__ import annotations

import http.client
import io
import json
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Final, Protocol

import jsonio

__all__: list[str] = [
    "REQUEST_TIMEOUT_S",
    "OAuthHttpResponse",
    "OAuthRequest",
    "OAuthTransport",
    "get_json",
]

REQUEST_TIMEOUT_S: Final = 30.0
_HTTP_ERROR_MINIMUM: Final = 400


@dataclass(frozen=True, kw_only=True)
class OAuthRequest:
    """One read-only GET against the provider's OAuth-authenticated surface.

    Named for the AUTHENTICATION rather than for either endpoint, because the
    usage poll and the capacity read send the same shape with the same
    credential. A request type named for one of its two consumers would have
    made the shared boundary read as a borrowing.
    """

    url: str
    headers: dict[str, str]


class OAuthHttpResponse(Protocol):
    def __enter__(self) -> OAuthHttpResponse: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool | None: ...

    def read(self, *, size: int = -1) -> bytes: ...


class OAuthTransport(Protocol):
    def __call__(self, request: OAuthRequest, timeout: float) -> OAuthHttpResponse: ...


def get_json(
    *,
    request: OAuthRequest,
    transport: OAuthTransport | None = None,
) -> tuple[dict[str, object] | None, str | None]:
    """Return (body, None) or (None, reason). Never raises."""

    opener = _open_get if transport is None else transport
    try:
        with opener(request=request, timeout=REQUEST_TIMEOUT_S) as response:
            parsed: object = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return None, _http_error_reason(error=exc)
    except (OSError, http.client.HTTPException, TypeError, UnicodeDecodeError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"

    body = jsonio.as_object(value=parsed)
    if body is None:
        return None, "unexpected response shape"
    return body, None


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


def _open_get(*, request: OAuthRequest, timeout: float) -> OAuthHttpResponse:
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
