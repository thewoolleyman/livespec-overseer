"""OTLP span emission for daemon event records."""

from __future__ import annotations

import importlib
import json
import pathlib

__all__: list[str] = []


def test_daemon_event_builds_zero_duration_otlp_span_with_matching_attributes():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_supervisor_otel.py"
    assert module_path.is_file()
    otel = importlib.import_module("overseer._supervisor_otel")
    emitted: list[dict[str, object]] = []
    config = otel.OtelConfig(
        endpoint="https://api.honeycomb.io",
        ingest_key="key",
        service_name="livespec-overseer",
        service_namespace="livespec-family",
    )
    record = {
        "ts": "2026-08-22T12:34:56.123456Z",
        "event": "blocked-human",
        "severity": "alert",
        "daemon_instance_id": "daemon-1",
        "tick_generation": 7,
        "message": "needs attention",
        "repo": "livespec-overseer",
        "topic": "foreman",
        "tmux": "session",
        "status": "blocked:human",
        "session_identity": "codex:session",
        "ctx": 42,
    }

    result = otel.emit_daemon_event(record=record, config=config, emitter=emitted.append)

    assert result == otel.EmitResult(sent=True, span_count=1, rejected_spans=0, error=None)
    request = emitted[0]
    assert request["url"] == "https://api.honeycomb.io/v1/traces"
    assert request["headers"] == {
        "Content-Type": "application/json",
        "x-honeycomb-team": "key",
    }
    payload = request["payload"]
    assert isinstance(payload, dict)
    resource_span = payload["resourceSpans"][0]
    assert resource_span["resource"]["attributes"] == [
        {"key": "service.name", "value": {"stringValue": "livespec-overseer"}},
        {"key": "service.namespace", "value": {"stringValue": "livespec-family"}},
    ]
    span = resource_span["scopeSpans"][0]["spans"][0]
    assert span["name"] == "blocked-human"
    assert span["kind"] == 1
    assert span["parentSpanId"] == ""
    assert span["startTimeUnixNano"] == span["endTimeUnixNano"] == "1787402096123456000"
    assert span["status"] == {"code": 1}
    attributes = {item["key"]: item["value"] for item in span["attributes"]}
    assert "event" not in attributes
    assert attributes["topic"] == {"stringValue": "foreman"}
    assert attributes["daemon_instance_id"] == {"stringValue": "daemon-1"}
    assert attributes["tick_generation"] == {"intValue": "7"}
    assert attributes["ctx"] == {"intValue": "42"}
    assert attributes["session_identity"] == {"stringValue": "codex:session"}


def test_unconfigured_otel_export_is_local_only():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_supervisor_otel.py"
    assert module_path.is_file()
    otel = importlib.import_module("overseer._supervisor_otel")
    emitted: list[dict[str, object]] = []

    result = otel.emit_daemon_event(
        record={"event": "daemon-log", "ts": "2026-08-22T00:00:00Z"},
        config=otel.OtelConfig(
            endpoint=None,
            ingest_key=None,
            service_name="livespec-overseer",
            service_namespace="livespec-family",
        ),
        emitter=emitted.append,
    )

    assert result == otel.EmitResult(sent=False, span_count=0, rejected_spans=0, error=None)
    assert emitted == []


def test_otel_config_reads_only_environment_names_settled_for_the_daemon(*, monkeypatch):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_supervisor_otel.py"
    assert module_path.is_file()
    otel = importlib.import_module("overseer._supervisor_otel")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("HONEYCOMB_INGEST_KEY_LIVESPEC", "secret-key")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "overseer-dev")

    config = otel.config_from_env()

    assert config == otel.OtelConfig(
        endpoint="http://127.0.0.1:4318",
        ingest_key="secret-key",
        service_name="overseer-dev",
        service_namespace="livespec-family",
    )


def test_default_otel_emitter_posts_http_json_and_reports_rejections(*, monkeypatch):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_supervisor_otel.py"
    assert module_path.is_file()
    otel = importlib.import_module("overseer._supervisor_otel")
    captured: dict[str, object] = {}

    class FakeResponse:
        status = 200
        reason = "OK"

        def read(self, *, size: int = -1) -> bytes:
            return json.dumps({"partialSuccess": {"rejectedSpans": 2}}).encode()

        def close(self) -> None:
            captured["closed"] = True

    class FakeConnection:
        def __init__(self, *, host: str, timeout: float):
            captured["host"] = host
            captured["timeout"] = timeout

        def request(
            self,
            *,
            method: str,
            target: str,
            body: bytes,
            headers: dict[str, str],
        ) -> None:
            captured["method"] = method
            captured["target"] = target
            captured["body"] = body
            captured["headers"] = headers

        def getresponse(self) -> FakeResponse:
            return FakeResponse()

        def close(self) -> None:
            captured["connection_closed"] = True

    monkeypatch.setattr(otel.http.client, "HTTPConnection", FakeConnection)
    request = {
        "url": "http://127.0.0.1:4318/v1/traces",
        "headers": {"Content-Type": "application/json"},
        "payload": {"resourceSpans": []},
    }

    result = otel.default_emitter(request=request)

    assert result == otel.EmitResult(sent=True, span_count=0, rejected_spans=2, error=None)
    assert captured["host"] == "127.0.0.1:4318"
    assert captured["target"] == "/v1/traces"
    assert captured["headers"] == {"Content-Type": "application/json"}
    assert json.loads(captured["body"]) == {"resourceSpans": []}
