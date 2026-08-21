"""Tests for caam credential parsing and usage polling."""

from __future__ import annotations

import http.client
import importlib
import io
import json
import urllib.error
from pathlib import Path
from types import ModuleType

__all__: list[str] = []


def caam_usage_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_usage.py"
    assert module_path.is_file()
    return importlib.import_module("caam_usage")


def write_creds(*, path: Path, bearer: str | None, expires_at_ms: int | None) -> None:
    oauth: dict[str, object] = {}
    if bearer is not None:
        oauth["accessToken"] = bearer
    if expires_at_ms is not None:
        oauth["expiresAt"] = expires_at_ms
    path.write_text(json.dumps({"claudeAiOauth": oauth}), encoding="utf-8")


def usage_body(*, limits: list[dict[str, object]] | None = None) -> bytes:
    return json.dumps(
        {
            "five_hour": {
                "utilization": 12.5,
                "resets_at": "2026-08-21T12:00:00Z",
            },
            "seven_day": {
                "utilization": 34.5,
                "resets_at": "2026-08-25T12:00:00Z",
            },
            "limits": [] if limits is None else limits,
        }
    ).encode()


class Response:
    def __init__(self, *, body: bytes) -> None:
        self._body = io.BytesIO(body)

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class RecordingTransport:
    def __init__(self, *, response: Response | BaseException) -> None:
        self.response = response
        self.requests: list[object] = []
        self.timeouts: list[float] = []

    def __call__(self, request: object, timeout: float) -> Response:
        self.requests.append(request)
        self.timeouts.append(timeout)
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def test_read_creds_converts_expiry_from_milliseconds(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=1_800_000)

    assert module.read_creds(path=creds) == ("tok", 1800.0)


def test_read_creds_treats_non_object_json_as_absent(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    creds.write_text("[]\n", encoding="utf-8")

    assert module.read_creds(path=creds) == (None, None)


def test_read_creds_treats_malformed_json_as_absent(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    creds.write_text("{oops}\n", encoding="utf-8")

    assert module.read_creds(path=creds) == (None, None)


def test_expired_token_is_skipped_without_issuing_request(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="expired", expires_at_ms=3_600_000)
    transport = RecordingTransport(response=Response(body=usage_body()))

    usage, why = module.fetch_usage(creds_path=creds, now=7200.0, transport=transport)

    assert usage is None
    assert why == "token expired 1.0h ago"
    assert transport.requests == []


def test_expiry_skew_margin_is_inclusive_at_sixty_seconds(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="almost-expired", expires_at_ms=1_060_000)

    assert module.live_token(path=creds, now=1000.0) == (
        None,
        "token expired -0.0h ago",
    )

    write_creds(path=creds, bearer="usable", expires_at_ms=1_061_000)
    assert module.live_token(path=creds, now=1000.0) == ("usable", None)


def test_fetch_usage_returns_parseable_http_error_message(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)
    error = urllib.error.HTTPError(
        url="https://example.invalid",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b'{"error":{"message":"rate limited"}}'),
    )

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=error),
    )

    assert usage is None
    assert why == "rate limited"


def test_fetch_usage_returns_status_for_unparseable_http_error(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)
    error = urllib.error.HTTPError(
        url="https://example.invalid",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b"not json"),
    )

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=error),
    )

    assert usage is None
    assert why == "HTTP 401"


def test_fetch_usage_returns_transport_exception_reason(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=OSError("socket closed")),
    )

    assert usage is None
    assert why == "OSError: socket closed"


def test_fetch_usage_returns_http_protocol_exception_reason(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=http.client.BadStatusLine("garbled")),
    )

    assert usage is None
    assert why == "BadStatusLine: garbled"


def test_fetch_usage_extracts_fable_only_from_matching_weekly_scope(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(
            response=Response(
                body=usage_body(
                    limits=[
                        {
                            "kind": "weekly_scoped",
                            "percent": 90,
                            "resets_at": "wrong-model",
                            "scope": {"model": {"display_name": "Opus"}},
                        },
                        {
                            "kind": "monthly_scoped",
                            "percent": 91,
                            "resets_at": "wrong-kind",
                            "scope": {"model": {"display_name": "Fable"}},
                        },
                        {
                            "kind": "weekly_scoped",
                            "percent": 92,
                            "resets_at": "fable-reset",
                            "scope": {"model": {"display_name": "Fable"}},
                        },
                    ]
                )
            )
        ),
    )

    assert why is None
    assert usage is not None
    assert usage.fable == 92.0
    assert usage.fable_resets_at == "fable-reset"


def test_absent_fable_limit_is_not_an_error(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=Response(body=usage_body())),
    )

    assert why is None
    assert usage is not None
    assert usage.fable is None
    assert usage.fable_resets_at is None


def test_malformed_response_yields_unexpected_shape(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=Response(body=b'{"five_hour": {}}')),
    )

    assert usage is None
    assert why == "unexpected response shape"


def test_usage_polling_has_no_oauth_refresh_path():
    module = caam_usage_module()

    assert not hasattr(module, "refresh_token")
    assert not hasattr(module, "refresh_oauth")
