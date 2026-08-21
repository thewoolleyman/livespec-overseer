"""Coverage for caam usage polling edge paths."""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
from types import ModuleType
from typing import ClassVar

__all__: list[str] = []


def caam_usage_module() -> ModuleType:
    return importlib.import_module("caam_usage")


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


def test_fable_match_without_percent_defaults_to_zero(*, tmp_path: Path):
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
    assert usage.fable == 0.0


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
    monkeypatch.setattr(module.http.client, "HTTPSConnection", FakeConnection)

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
