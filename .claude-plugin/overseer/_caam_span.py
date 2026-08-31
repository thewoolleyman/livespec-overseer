"""OTLP span emission for caam rotation events — fail-open, env-gated, silent when unset.

The daemon exports its own closed event catalog through `_supervisor_otel`; this module
is the caam half of the same wire convention. It differs on the wire in exactly one
place — the instrumentation scope is `livespec.overseer.caam` rather than the daemon's —
so a Honeycomb reader can separate rotation events from supervision events while both
land in one dataset under the same `service.name`/`service.namespace` resource.

Config comes from the environment through `_supervisor_otel.config_from_env`
(`OTEL_EXPORTER_OTLP_ENDPOINT`, `HONEYCOMB_INGEST_KEY_LIVESPEC`, `OTEL_SERVICE_NAME`), so
there is ONE reader for both halves and this path invents no second set of variable
names. "Unconfigured" means the ENDPOINT is absent. An endpoint with NO key is a
misconfiguration the collector must be allowed to reject and report; keying the
degradation on the key instead would silently no-op exactly the request whose rejection
is the signal.

TWO DELIBERATE DIVERGENCES from `_supervisor_otel.emit_daemon_event`, both forced by
where caam runs rather than by taste:

  - FAIL-OPEN. caam emission sits inside model ENFORCEMENT, which has to keep working
    when telemetry does not. `emit_daemon_event` lets an emitter's exception propagate,
    which is right for the daemon, where the export IS the call. Here every advisory
    failure is folded into the returned `EmitResult.error` instead — using the same
    narrow advisory-error tuple `caam_enforcement` already carries, not a broad catch,
    which the boundary-catch gate reserves for a program's single `main()`. The guard
    wraps the payload BUILD as well as the transport: a record that cannot name a span
    is exactly as fatal to an enforcement pass as an unreachable collector, and just as
    unacceptable.

  - THE PAYLOAD BUILDER IS PRIVATE HERE RATHER THAN SHARED. `_supervisor_otel` sits one
    line under the 250-LLOC hard ceiling, so it cannot carry a scope-parameterized
    public builder without first being decomposed — a change to the load-bearing daemon
    export path that this foundation item deliberately does not make. If a third scope
    ever needs this mapping, extract the builder into a module of its own and have both
    callers import its PUBLIC entry point; do not reach for these private helpers from
    outside this file.

A caam event is instantaneous, so the span is zero-duration
(`startTimeUnixNano == endTimeUnixNano`) rather than carrying an invented duration, and
`severity` rides as an ordinary attribute. `status.code` 2 is reserved for records
carrying an `error`: an alert-severity rotation hold is a correct observation correctly
reported, and marking it failed would make a healthy enforcement pass look broken.

PARENTAGE RIDES ON THREE RESERVED RECORD KEYS (work-item overseer-m7qrgp.3). A record
may name its own `trace.id` / `span.id` and its parent's `span.parent_id`; each is
otherwise minted fresh, exactly as before, so an unlinked record is unchanged on the
wire. They are stripped from `_attributes` rather than shipped as ordinary attributes:
OTLP already carries all three as span FIELDS, and duplicating them would make a
Honeycomb reader group traces by an attribute that only sometimes exists.
"""

from __future__ import annotations

import datetime
import secrets
from collections.abc import Callable, Mapping
from typing import Final, cast

from _supervisor_otel import EmitResult, OtelConfig

__all__: list[str] = [
    "CAAM_SCOPE_NAME",
    "CAAM_SCOPE_VERSION",
    "PARENT_SPAN_ID_KEY",
    "SPAN_ID_KEY",
    "TRACE_ID_KEY",
    "emit_caam_event",
    "iso_timestamp",
]

CAAM_SCOPE_NAME: Final = "livespec.overseer.caam"
CAAM_SCOPE_VERSION: Final = "1.0.0"

TRACE_ID_KEY: Final = "trace.id"
SPAN_ID_KEY: Final = "span.id"
PARENT_SPAN_ID_KEY: Final = "span.parent_id"
_LINK_KEYS: Final = frozenset({TRACE_ID_KEY, SPAN_ID_KEY, PARENT_SPAN_ID_KEY})
_TRACE_ID_BYTES: Final = 16
_SPAN_ID_BYTES: Final = 8

_TRACES_PATH: Final = "/v1/traces"
_JSON_HEADER: Final = "application/json"
_TEAM_HEADER: Final = "x-honeycomb-team"
_NANOS_PER_SECOND: Final = 1_000_000_000
_SPAN_KIND_INTERNAL: Final = 1
_STATUS_OK: Final = 1
_STATUS_ERROR: Final = 2
# The advisory-error tuple `caam_enforcement` already uses for its non-fatal work.
# Named types, not `except Exception`: the broad-catch gate grants a program exactly one
# boundary catch, in `main()`, and a telemetry seam is not it.
_ADVISORY_ERRORS: Final = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)

CaamSpanPayload = dict[str, object]


def emit_caam_event(
    *,
    record: Mapping[str, object],
    config: OtelConfig,
    emitter: Callable[[dict[str, object]], object],
) -> EmitResult:
    """Export one caam record as a zero-duration span, and never raise at the caller.

    The emitter is called POSITIONALLY, matching `emit_daemon_event`, so a test can
    inject `list.append` as the whole transport.
    """
    endpoint = config.endpoint
    if endpoint is None:
        return _not_sent(error=None)
    try:
        emitted = emitter(_request(record=record, config=config, endpoint=endpoint))
    except _ADVISORY_ERRORS as exc:
        return _not_sent(error=f"{type(exc).__name__}: {exc}")
    # A real transport reports its own outcome, including an HTTP rejection and the
    # rejected-span count. Collapsing that to `sent=True` would swallow the very
    # failures export-failure reporting exists to surface.
    if isinstance(emitted, EmitResult):
        return emitted
    return EmitResult(sent=True, span_count=1, rejected_spans=0, error=None)


def _not_sent(*, error: str | None) -> EmitResult:
    return EmitResult(sent=False, span_count=0, rejected_spans=0, error=error)


def _request(
    *,
    record: Mapping[str, object],
    config: OtelConfig,
    endpoint: str,
) -> dict[str, object]:
    base = endpoint.rstrip("/")
    headers = {"Content-Type": _JSON_HEADER}
    if config.ingest_key is not None:
        headers[_TEAM_HEADER] = config.ingest_key
    return {
        "url": base if base.endswith(_TRACES_PATH) else f"{base}{_TRACES_PATH}",
        "headers": headers,
        "payload": _payload(record=record, config=config),
    }


def _payload(*, record: Mapping[str, object], config: OtelConfig) -> CaamSpanPayload:
    nanos = _unix_nanos(record=record)
    span = {
        "traceId": _minted(record=record, key=TRACE_ID_KEY, width=_TRACE_ID_BYTES),
        "spanId": _minted(record=record, key=SPAN_ID_KEY, width=_SPAN_ID_BYTES),
        "parentSpanId": _parent(record=record),
        "name": _required_str(record=record, key="event"),
        "kind": _SPAN_KIND_INTERNAL,
        "startTimeUnixNano": nanos,
        "endTimeUnixNano": nanos,
        "attributes": _attributes(record=record),
        "status": {"code": _STATUS_ERROR if "error" in record else _STATUS_OK},
    }
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _attribute(key="service.name", value=config.service_name),
                        _attribute(key="service.namespace", value=config.service_namespace),
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": CAAM_SCOPE_NAME, "version": CAAM_SCOPE_VERSION},
                        "spans": [span],
                    }
                ],
            }
        ]
    }


def _minted(*, record: Mapping[str, object], key: str, width: int) -> str:
    """The id the record named, or a fresh one -- an unlinked record is unchanged."""

    value = record.get(key)
    return value if isinstance(value, str) and value else secrets.token_hex(width)


def _parent(*, record: Mapping[str, object]) -> str:
    """A root span's parent is the empty string, which is what OTLP expects."""

    value = record.get(PARENT_SPAN_ID_KEY)
    return value if isinstance(value, str) else ""


def _attributes(*, record: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        _attribute(key=key, value=value)
        for key, value in sorted(record.items())
        if key != "event" and key not in _LINK_KEYS
    ]


def _attribute(*, key: str, value: object) -> dict[str, object]:
    return {"key": key, "value": _value(value=value)}


def _value(*, value: object) -> dict[str, object]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, list):
        values: list[dict[str, object]] = []
        for item in cast(list[object], value):
            values.append(_value(value=item))
        return {"arrayValue": {"values": values}}
    return {"stringValue": str(value)}


def iso_timestamp(*, at: float) -> str:
    """A pass's own checked-at instant, as the ISO-8601 `ts` this builder consumes.

    Shared by both caam record builders so one convention describes the wire. The
    pass clock is used rather than a fresh reading so every record from one pass
    carries the SAME instant: each span is a statement about that pass, and the
    records within it must be groupable by it.
    """

    moment = datetime.datetime.fromtimestamp(at, tz=datetime.timezone.utc)
    return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _unix_nanos(*, record: Mapping[str, object]) -> str:
    raw = _required_str(record=record, key="ts")
    parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return str(int(parsed.timestamp() * _NANOS_PER_SECOND))


def _required_str(*, record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError
    return value
