"""Coverage for caam usage polling edge paths."""

from __future__ import annotations

import http.client
import importlib
import io
import json
import socket
from pathlib import Path
from types import ModuleType
from typing import ClassVar

__all__: list[str] = []


def caam_usage_module() -> ModuleType:
    return importlib.import_module("caam_usage")


def caam_oauth_get_module() -> ModuleType:
    """The provider REQUEST boundary, which both reads now share.

    The default HTTPS transport moved out of `caam_usage` when the capacity
    source began reading a second endpoint with the same credential under the
    same **Never refresh** rule, so the connection class to stand in for lives
    here. These tests still drive it through `fetch_usage`, which is the point:
    the usage poll's behaviour against a real connection is unchanged by the
    move.
    """
    return importlib.import_module("caam_oauth_get")


def write_creds(*, path: Path, bearer: str | None, expires_at_ms: int | None) -> None:
    oauth: dict[str, object] = {}
    if bearer is not None:
        oauth["accessToken"] = bearer
    if expires_at_ms is not None:
        oauth["expiresAt"] = expires_at_ms
    path.write_text(json.dumps({"claudeAiOauth": oauth}), encoding="utf-8")


def test_bad_credential_shapes_are_absent_tokens(*, tmp_path: Path):
    module = caam_usage_module()
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text("[1]", encoding="utf-8")

    assert module.read_creds(path=missing) == (None, None)
    assert module.read_creds(path=malformed) == (None, None)
    assert module.live_token(path=malformed, now=1000.0) == (None, "no token in snapshot")


def test_live_token_uses_wall_clock_when_now_is_not_injected(*, monkeypatch, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="expired", expires_at_ms=3_600_000)
    monkeypatch.setattr(module.time, "time", lambda: 7200.0)

    assert module.live_token(path=creds) == (None, "token expired 1.0h ago")


def test_non_object_and_bad_numeric_usage_shapes_are_unexpected(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    class Response:
        def __init__(self, *, body: bytes) -> None:
            self.body = body

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self.body

    def transport(*, request: object, timeout: float) -> Response:
        return Response(body=b"[]")

    usage, why = module.fetch_usage(creds_path=creds, now=1000.0, transport=transport)
    assert usage is None
    assert why == "unexpected response shape"

    def bad_numeric_transport(*, request: object, timeout: float) -> Response:
        return Response(
            body=json.dumps(
                {
                    "five_hour": {"utilization": {}},
                    "seven_day": {"utilization": 1},
                }
            ).encode()
        )

    usage, why = module.fetch_usage(creds_path=creds, now=1000.0, transport=bad_numeric_transport)
    assert usage is None
    assert why == "unexpected response shape"


def test_fable_match_without_percent_defaults_to_a_full_allowance(*, tmp_path: Path):
    """A scoped limit reporting no spent share reads as nothing spent, hence all left.

    The OUTCOME is unchanged by the remaining flip -- an account with an unspent
    scoped allowance can serve the pin either way. Only the figure that expresses
    it moved ends, from zero spent to a hundred left.
    """
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "five_hour": {"utilization": 12},
                    "seven_day": {"utilization": 34},
                    "limits": [
                        {
                            "kind": "weekly_scoped",
                            "scope": {"model": {"display_name": "Fable"}},
                        }
                    ],
                }
            ).encode()

    def transport(*, request: object, timeout: float) -> Response:
        return Response()

    usage, why = module.fetch_usage(creds_path=creds, now=1000.0, transport=transport)
    assert why is None
    assert usage is not None
    assert usage.fable_remaining == 100.0


def test_default_https_transport_success_and_http_error(*, monkeypatch, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    class FakeHttpResponse:
        def __init__(self, *, status: int, body: bytes) -> None:
            self.status = status
            self.reason = "reason"
            self.headers: dict[str, str] = {}
            self.closed = False
            self._body = io.BytesIO(body)

        def read(self, size: int = -1) -> bytes:
            return self._body.read(size)

        def close(self) -> None:
            self.closed = True

    class FakeConnection:
        responses: ClassVar[list[FakeHttpResponse]] = []
        requests: ClassVar[list[tuple[str, str, dict[str, str]]]] = []

        def __init__(self, host: str, timeout: float) -> None:
            self.host = host
            self.timeout = timeout

        def request(self, method: str, target: str, headers: dict[str, str]) -> None:
            self.requests.append((method, target, headers))

        def getresponse(self) -> FakeHttpResponse:
            return self.responses.pop(0)

    FakeConnection.responses = [
        FakeHttpResponse(
            status=200,
            body=json.dumps(
                {
                    "five_hour": {"utilization": 12},
                    "seven_day": {"utilization": 34},
                    "limits": [],
                }
            ).encode(),
        ),
        FakeHttpResponse(
            status=429,
            body=b'{"error":{"message":"rate limited"}}',
        ),
    ]
    FakeConnection.requests = []
    monkeypatch.setattr(caam_oauth_get_module().http.client, "HTTPSConnection", FakeConnection)

    usage, why = module.fetch_usage(creds_path=creds, now=1000.0)
    assert why is None
    assert usage is not None
    assert FakeConnection.requests[0] == (
        "GET",
        "/api/oauth/usage",
        {"Authorization": "Bearer tok"},
    )

    usage, why = module.fetch_usage(creds_path=creds, now=1000.0)
    assert usage is None
    assert why == "rate limited"


def test_default_transport_rejects_non_https_usage_url(*, monkeypatch, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)
    monkeypatch.setattr(module, "USAGE_URL", "http://example.invalid/usage")

    usage, why = module.fetch_usage(creds_path=creds, now=1000.0)

    assert usage is None
    assert why == "ValueError: "


def test_default_transport_reads_a_chunked_keep_alive_body_without_waiting_for_close(
    *, monkeypatch
):
    """The provider answers both GETs chunked on a connection it keeps open.

    Measured 2026-11-13 on the role holder (overseer-4ji2n4): the profile and
    usage GETs come back `Transfer-Encoding: chunked` and the server does not
    close. Under the repository's declared Python floor, 3.10.16, reading such
    a body with `HTTPResponse.read(-1)` reads the socket to EOF and blocks
    until the request timeout, so every confirmation failed with
    `TimeoutError`. This drives a REAL `http.client.HTTPResponse` over a
    socket pair that is never closed, with the real profile body shape.
    """
    oauth = caam_oauth_get_module()
    server, client = socket.socketpair()
    profile = json.dumps(
        {
            "account": {"uuid": "acct-1", "has_claude_max": True},
            "organization": {"rate_limit_tier": "default_claude_max_20x"},
        }
    ).encode()
    server.sendall(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n"
        + f"{len(profile):x}\r\n".encode()
        + profile
        + b"\r\n0\r\n\r\n"
    )
    client.settimeout(2.0)

    class KeptAliveConnection:
        def __init__(self, host: str, timeout: float) -> None:
            self.host = host
            self.timeout = timeout

        def request(self, method: str, target: str, headers: dict[str, str]) -> None:
            assert (method, target) == ("GET", "/api/oauth/profile")

        def getresponse(self) -> http.client.HTTPResponse:
            response = http.client.HTTPResponse(client)
            response.begin()
            return response

    monkeypatch.setattr(oauth.http.client, "HTTPSConnection", KeptAliveConnection)
    try:
        body, why = oauth.get_json(
            request=oauth.OAuthRequest(
                url="https://api.anthropic.com/api/oauth/profile", headers={}
            )
        )
    finally:
        server.close()
        client.close()

    assert why is None
    assert body == json.loads(profile)
