"""Edge coverage for the daemon OTLP emitter."""

from __future__ import annotations

import json

from overseer import _supervisor_otel as otel

__all__: list[str] = []


def _config(*, endpoint: str = "http://collector:4318") -> otel.OtelConfig:
    return otel.OtelConfig(
        endpoint=endpoint,
        ingest_key=None,
        service_name="svc",
        service_namespace="ns",
    )


def _record(**fields: object) -> dict[str, object]:
    return {
        "ts": "2026-08-22T00:00:00Z",
        "event": "daemon-log",
        "severity": "info",
        **fields,
    }


def test_emit_uses_existing_traces_path_and_returns_transport_result():
    result = otel.EmitResult(sent=False, span_count=1, rejected_spans=1, error="HTTP 401")
    requests: list[dict[str, object]] = []

    actual = otel.emit_daemon_event(
        record=_record(),
        config=_config(endpoint="http://collector:4318/v1/traces"),
        emitter=lambda request: requests.append(request) or result,
    )

    assert actual == result
    assert requests[0]["url"] == "http://collector:4318/v1/traces"
    assert requests[0]["headers"] == {"Content-Type": "application/json"}


def test_span_status_code_two_is_reserved_for_daemon_error_events():
    requests: list[dict[str, object]] = []

    _ = otel.emit_daemon_event(
        record=_record(error="write failed", ok=True, ratio=1.5, bands=[50, "forty"]),
        config=_config(),
        emitter=requests.append,
    )

    payload = requests[0]["payload"]
    assert isinstance(payload, dict)
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["status"] == {"code": 2}
    attributes = {item["key"]: item["value"] for item in span["attributes"]}
    assert attributes["ok"] == {"boolValue": True}
    assert attributes["ratio"] == {"doubleValue": 1.5}
    assert attributes["bands"] == {
        "arrayValue": {"values": [{"intValue": "50"}, {"stringValue": "forty"}]}
    }


def test_default_emitter_rejects_invalid_request_shapes_and_endpoint():
    assert otel.default_emitter(request={}).error == "TypeError: "
    assert otel.default_emitter(request={"url": "http://x", "headers": {}, "payload": 1}).error == (
        "TypeError: "
    )
    assert otel.default_emitter(request={"url": "http://x", "payload": {}}).error == "TypeError: "
    assert otel.default_emitter(request={"url": "ftp://x", "headers": {}, "payload": {}}) == (
        otel.EmitResult(sent=False, span_count=0, rejected_spans=0, error="invalid OTLP endpoint")
    )
    assert (
        otel.default_emitter(
            request={"url": "http://x", "headers": {"bad": 1}, "payload": {}}
        ).error
        == "TypeError: "
    )


def test_default_emitter_reports_network_exception(*, monkeypatch):
    class BrokenConnection:
        def __init__(self, *, host: str, timeout: float):
            _ = (host, timeout)

        def request(self, *args: object, **kwargs: object) -> None:
            _ = (args, kwargs)
            raise OSError("offline")

        def close(self) -> None:
            pass

    monkeypatch.setattr(otel.http.client, "HTTPConnection", BrokenConnection)

    result = otel.default_emitter(
        request={"url": "http://collector/v1/traces", "headers": {}, "payload": {}}
    )

    assert result == otel.EmitResult(
        sent=False,
        span_count=0,
        rejected_spans=0,
        error="OSError: offline",
    )


def test_default_emitter_reports_http_error_and_counts_spans(*, monkeypatch):
    class Response:
        status = 401
        reason = "Unauthorized"

        def read(self) -> bytes:
            return json.dumps({"partialSuccess": {"rejectedSpans": 3}}).encode()

        def close(self) -> None:
            pass

    class PositionalConnection:
        def __init__(self, *, host: str, timeout: float):
            _ = (host, timeout)

        def request(self, *args: object, body: bytes, headers: dict[str, str]) -> None:
            _ = (args, body, headers)

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(otel.http.client, "HTTPConnection", PositionalConnection)
    payload = {
        "resourceSpans": [
            {"scopeSpans": [{"spans": [{"name": "one"}, {"name": "two"}]}]},
            {"scopeSpans": [{"spans": [{"name": "three"}]}]},
        ]
    }

    result = otel.default_emitter(
        request={"url": "http://collector/v1/traces", "headers": {}, "payload": payload}
    )

    assert result == otel.EmitResult(
        sent=False,
        span_count=3,
        rejected_spans=3,
        error="HTTP 401 Unauthorized",
    )


def test_default_emitter_ignores_malformed_rejection_bodies(*, monkeypatch):
    class Response:
        status = 200
        reason = "OK"

        def read(self) -> bytes:
            return b"{"

        def close(self) -> None:
            pass

    class Connection:
        def __init__(self, *, host: str, timeout: float):
            _ = (host, timeout)

        def request(self, *args: object, body: bytes, headers: dict[str, str]) -> None:
            _ = (args, body, headers)

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(otel.http.client, "HTTPConnection", Connection)

    result = otel.default_emitter(
        request={
            "url": "http://collector/v1/traces",
            "headers": {},
            "payload": {"resourceSpans": [1]},
        }
    )

    assert result == otel.EmitResult(sent=True, span_count=0, rejected_spans=0, error=None)


def test_default_emitter_counts_absent_resource_spans_as_zero(*, monkeypatch):
    class Response:
        status = 200
        reason = "OK"

        def read(self) -> bytes:
            return b"{}"

        def close(self) -> None:
            pass

    class Connection:
        def __init__(self, *, host: str, timeout: float):
            _ = (host, timeout)

        def request(self, *args: object, body: bytes, headers: dict[str, str]) -> None:
            _ = (args, body, headers)

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(otel.http.client, "HTTPConnection", Connection)

    result = otel.default_emitter(
        request={"url": "http://collector/v1/traces", "headers": {}, "payload": {}}
    )

    assert result == otel.EmitResult(sent=True, span_count=0, rejected_spans=0, error=None)
