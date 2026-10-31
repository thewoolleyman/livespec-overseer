"""Tests for caam credential parsing and usage polling."""

from __future__ import annotations

import http.client
import importlib
import io
import json
import urllib.error
from datetime import datetime, timezone
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
    # The response reports this limit 92% spent; the record stores what is LEFT.
    assert usage.fable_remaining == 8.0
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
    assert usage.fable_remaining is None
    assert usage.fable_resets_at is None


def test_weekly_only_limits_are_a_readable_usage_record(*, tmp_path: Path):
    """Ultra's lack of a five-hour allowance is a reading, not an error."""
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)
    body = json.dumps(
        {
            "five_hour": None,
            "limits": [
                {
                    "kind": "weekly_all",
                    "percent": 95,
                    "resets_at": "weekly-reset",
                },
                {
                    "kind": "weekly_scoped",
                    "percent": 20,
                    "resets_at": "scoped-reset",
                    "scope": {"model": {"display_name": "Fable"}},
                },
            ],
        }
    ).encode()

    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=Response(body=body)),
    )

    assert why is None
    assert usage is not None
    assert usage.five_hour_remaining is None
    assert usage.seven_day_remaining == 5.0


def test_weekly_only_row_names_the_absent_short_window(*, tmp_path: Path):
    """A readable Ultra account must not look dark merely because 5h is absent."""
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)
    body = json.dumps(
        {
            "limits": [
                {
                    "kind": "weekly_all",
                    "percent": 95,
                    "resets_at": "2026-11-07T00:00:00Z",
                }
            ]
        }
    ).encode()
    usage, why = module.fetch_usage(
        creds_path=creds,
        now=1000.0,
        transport=RecordingTransport(response=Response(body=body)),
    )
    assert why is None
    assert usage is not None
    decision = importlib.import_module("caam_decision")
    row = decision.ProfileUsage(name="ultra", source="live", usage=usage)

    table = decision.render_table(
        rows=(row,),
        active_name="ultra",
        now=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )

    assert "ultra" in table
    assert "5%" in table
    assert "no 5h limit" in table
    assert "dark:" not in table


def test_generic_limits_drive_each_reading_and_show_unknown_kinds(*, tmp_path: Path):
    """A temporary short window is evaluated only while the response reports it."""
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    def read(*, limits: list[dict[str, object]]) -> tuple[object, object]:
        return module.fetch_usage(
            creds_path=creds,
            now=1000.0,
            transport=RecordingTransport(
                response=Response(body=json.dumps({"limits": limits}).encode())
            ),
        )

    weekly_only, why = read(
        limits=[
            {"kind": "weekly_all", "percent": 20, "resets_at": "2026-11-07T00:00:00Z"},
            {"kind": "experimental", "percent": 40, "resets_at": "later"},
        ]
    )
    assert why is None
    assert weekly_only is not None
    decision = importlib.import_module("caam_decision")
    assert decision.triggered(usage=weekly_only) is False
    assert weekly_only.limit(kind="experimental") is not None
    table = decision.render_table(
        rows=(decision.ProfileUsage(name="ultra", source="live", usage=weekly_only),),
        active_name="ultra",
        now=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )
    assert "experimental 60%" in table

    temporary_short, why = read(
        limits=[
            {"kind": "five_hour", "percent": 90, "resets_at": "soon"},
            {"kind": "weekly_all", "percent": 20, "resets_at": "2026-11-07T00:00:00Z"},
        ]
    )
    assert why is None
    assert temporary_short is not None
    assert decision.triggered(usage=temporary_short) is True


def test_malformed_generic_limits_remain_unreadable(*, tmp_path: Path):
    module = caam_usage_module()
    creds = tmp_path / ".credentials.json"
    write_creds(path=creds, bearer="tok", expires_at_ms=9_000_000)

    for body in (
        {"limits": [{"kind": "weekly_all", "percent": 10}, None]},
        {"limits": [{"kind": "weekly_all"}]},
        {"limits": [{"percent": 10}]},
        {"limits": [], "five_hour": {}, "seven_day": {"utilization": 10}},
    ):
        usage, why = module.fetch_usage(
            creds_path=creds,
            now=1000.0,
            transport=RecordingTransport(response=Response(body=json.dumps(body).encode())),
        )

        assert usage is None
        assert why == "unexpected response shape"


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
