"""OTLP span emission for caam records: the wire shape, fail-open, and the no-op.

Three properties, and only the first is about the payload. The other two are the
reason this seam is a separate module from `_supervisor_otel`: caam emission runs
INSIDE model enforcement, so an unreachable collector must cost an enforcement pass
nothing, and an unconfigured host must send nothing at all rather than degrade to a
half-configured export.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_SAMPLE_TS = "2026-08-22T12:34:56.123456Z"
_SAMPLE_TS_NANOS = "1787402096123456000"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_caam_span.py"
    assert module_path.is_file()
    # The flat name, not `overseer._supervisor_otel`: this package imports its
    # siblings FLAT, so the module object `_caam_span` binds its `EmitResult` and
    # `OtelConfig` from is the flat one. Importing the packaged alias here would
    # yield DIFFERENT class objects and make every equality assertion below lie.
    return importlib.import_module("overseer._caam_span"), importlib.import_module(
        "_supervisor_otel"
    )


def _configured(*, otel, endpoint: str, ingest_key: str | None):
    return otel.OtelConfig(
        endpoint=endpoint,
        ingest_key=ingest_key,
        service_name="livespec-overseer",
        service_namespace="livespec-family",
    )


def test_a_caam_record_becomes_a_zero_duration_span_in_the_caam_scope():
    caam, otel = _modules()
    emitted: list[dict[str, object]] = []
    record = {
        "ts": _SAMPLE_TS,
        "event": "caam-account-switched",
        "account": "fable-primary",
        "topic": "foreman",
        "dry_run": False,
        "weekly_left_percent": 41.5,
        "attempt": 2,
        "candidates": ["fable-primary", "fable-spare"],
    }

    result = caam.emit_caam_event(
        record=record,
        config=_configured(otel=otel, endpoint="https://api.honeycomb.io", ingest_key="key"),
        emitter=emitted.append,
    )

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
    scope_span = resource_span["scopeSpans"][0]
    assert scope_span["scope"] == {
        "name": "livespec.overseer.caam",
        "version": caam.CAAM_SCOPE_VERSION,
    }
    span = scope_span["spans"][0]
    assert span["name"] == "caam-account-switched"
    assert span["kind"] == 1
    assert span["parentSpanId"] == ""
    assert span["startTimeUnixNano"] == span["endTimeUnixNano"] == _SAMPLE_TS_NANOS
    assert span["status"] == {"code": 1}
    attributes = {item["key"]: item["value"] for item in span["attributes"]}
    assert "event" not in attributes
    assert attributes["account"] == {"stringValue": "fable-primary"}
    assert attributes["topic"] == {"stringValue": "foreman"}
    assert attributes["dry_run"] == {"boolValue": False}
    assert attributes["attempt"] == {"intValue": "2"}
    assert attributes["weekly_left_percent"] == {"doubleValue": 41.5}
    assert attributes["candidates"] == {
        "arrayValue": {"values": [{"stringValue": "fable-primary"}, {"stringValue": "fable-spare"}]}
    }


def test_a_record_carrying_an_error_key_is_the_only_thing_that_sets_status_error():
    """`status.code` reflects the daemon's own failure, never the event's severity.

    An `alert`-severity caam event is a correct observation correctly reported; the
    sibling daemon path settled that `severity` is an attribute and `status.code` 2 is
    reserved for the `error`-carrying events. This also pins the two request legs the
    happy-path test cannot reach: an endpoint that ALREADY names `/v1/traces` is not
    suffixed twice, and a config with no ingest key sends no team header.
    """
    caam, otel = _modules()
    emitted: list[dict[str, object]] = []
    record = {
        "ts": _SAMPLE_TS,
        "event": "caam-usage-poll-failed",
        "severity": "alert",
        "error": "HTTPError: 503",
    }

    result = caam.emit_caam_event(
        record=record,
        config=_configured(otel=otel, endpoint="http://localhost:4318/v1/traces/", ingest_key=None),
        emitter=emitted.append,
    )

    assert result.sent is True
    request = emitted[0]
    assert request["url"] == "http://localhost:4318/v1/traces"
    assert request["headers"] == {"Content-Type": "application/json"}
    payload = request["payload"]
    assert isinstance(payload, dict)
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["status"] == {"code": 2}
    attributes = {item["key"]: item["value"] for item in span["attributes"]}
    assert attributes["severity"] == {"stringValue": "alert"}
    assert attributes["error"] == {"stringValue": "HTTPError: 503"}


def test_an_emitter_that_raises_does_not_propagate_out_of_the_emit_call():
    """Fail-open: telemetry transport failure must never abort an enforcement pass."""
    caam, otel = _modules()

    def _unreachable_collector(request):
        raise RuntimeError("collector unreachable")

    result = caam.emit_caam_event(
        record={"ts": _SAMPLE_TS, "event": "caam-pass-started"},
        config=_configured(otel=otel, endpoint="https://api.honeycomb.io", ingest_key="key"),
        emitter=_unreachable_collector,
    )

    assert result == otel.EmitResult(
        sent=False,
        span_count=0,
        rejected_spans=0,
        error="RuntimeError: collector unreachable",
    )


def test_a_malformed_record_fails_open_rather_than_raising_at_the_caller():
    """The fail-open guard wraps the BUILD too, not only the transport.

    A record with no `event` cannot name a span, and the builder says so by raising —
    but it raises INSIDE enforcement, so the guard has to be outside the payload
    construction rather than around the emitter call alone.
    """
    caam, otel = _modules()
    emitted: list[dict[str, object]] = []

    result = caam.emit_caam_event(
        record={"ts": _SAMPLE_TS},
        config=_configured(otel=otel, endpoint="https://api.honeycomb.io", ingest_key="key"),
        emitter=emitted.append,
    )

    assert result.sent is False
    assert result.error is not None
    assert result.error.startswith("TypeError")
    assert emitted == []


def test_an_emitter_reporting_its_own_result_is_reported_verbatim():
    """The real transport returns an `EmitResult`; a partial rejection must survive it.

    Collapsing every non-raising emitter to `sent=True` would swallow exactly the
    HTTP-rejection and partial-success counts the export-failure reporting depends on.
    """
    caam, otel = _modules()
    rejected = otel.EmitResult(
        sent=False, span_count=1, rejected_spans=1, error="HTTP 400 Bad Request"
    )

    result = caam.emit_caam_event(
        record={"ts": _SAMPLE_TS, "event": "caam-pass-started"},
        config=_configured(otel=otel, endpoint="https://api.honeycomb.io", ingest_key="key"),
        emitter=lambda request: rejected,
    )

    assert result is rejected


def test_an_unconfigured_environment_emits_nothing_and_raises_nothing(*, monkeypatch):
    """No endpoint means no traffic — read through the SHARED env reader, not a literal.

    `_supervisor_otel.config_from_env` is the one reader for both halves of the fleet
    convention, so this leg also pins that the caam path adds no second set of variable
    names. "Unconfigured" is the ENDPOINT being absent: an endpoint with no key is a
    misconfiguration the collector must be allowed to reject, not one this seam hides.
    """
    caam, otel = _modules()
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("HONEYCOMB_INGEST_KEY_LIVESPEC", raising=False)
    emitted: list[dict[str, object]] = []

    config = otel.config_from_env()
    result = caam.emit_caam_event(
        record={"ts": _SAMPLE_TS, "event": "caam-pass-started"},
        config=config,
        emitter=emitted.append,
    )

    assert config.endpoint is None
    assert result == otel.EmitResult(sent=False, span_count=0, rejected_spans=0, error=None)
    assert emitted == []
