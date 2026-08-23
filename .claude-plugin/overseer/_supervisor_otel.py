"""OTLP/HTTP JSON export for the daemon's closed event catalog."""
# livespec-lloc-soft-band-owner: overseer-temi26.3

from __future__ import annotations

import datetime
import http.client
import json
import os
import secrets
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, cast

import jsonio

__all__: list[str] = [
    "EmitResult",
    "OtelConfig",
    "config_from_env",
    "default_emitter",
    "emit_daemon_event",
]

_ENDPOINT_ENV: Final = "OTEL_EXPORTER_OTLP_ENDPOINT"
_KEY_ENV: Final = "HONEYCOMB_INGEST_KEY_LIVESPEC"
_SERVICE_ENV: Final = "OTEL_SERVICE_NAME"
_DEFAULT_SERVICE_NAME: Final = "livespec-overseer"
_DEFAULT_SERVICE_NAMESPACE: Final = "livespec-family"
_SCOPE_NAME: Final = "livespec.overseer.daemon"
_SCOPE_VERSION: Final = "1.0.0"
_REQUEST_TIMEOUT_SECONDS: Final = 10.0
_HTTP_ERROR_MINIMUM: Final = 400
_NANOS_PER_SECOND: Final = 1_000_000_000

OtelPayload = dict[str, object]


@dataclass(frozen=True, kw_only=True)
class OtelConfig:
    endpoint: str | None
    ingest_key: str | None
    service_name: str
    service_namespace: str


@dataclass(frozen=True, kw_only=True)
class EmitResult:
    sent: bool
    span_count: int
    rejected_spans: int
    error: str | None


def config_from_env(*, environ: Mapping[str, str] | None = None) -> OtelConfig:
    source = os.environ if environ is None else environ
    endpoint = (source.get(_ENDPOINT_ENV) or "").strip() or None
    ingest_key = (source.get(_KEY_ENV) or "").strip() or None
    service_name = (source.get(_SERVICE_ENV) or "").strip() or _DEFAULT_SERVICE_NAME
    return OtelConfig(
        endpoint=endpoint,
        ingest_key=ingest_key,
        service_name=service_name,
        service_namespace=_DEFAULT_SERVICE_NAMESPACE,
    )


def emit_daemon_event(
    *,
    record: Mapping[str, object],
    config: OtelConfig,
    emitter: Callable[[dict[str, object]], object],
) -> EmitResult:
    if config.endpoint is None:
        return EmitResult(sent=False, span_count=0, rejected_spans=0, error=None)
    endpoint = config.endpoint.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if config.ingest_key is not None:
        headers["x-honeycomb-team"] = config.ingest_key
    emitted = emitter(
        {
            "url": endpoint if endpoint.endswith("/v1/traces") else f"{endpoint}/v1/traces",
            "headers": headers,
            "payload": _payload(record=record, config=config),
        }
    )
    if isinstance(emitted, EmitResult):
        return emitted
    return EmitResult(sent=True, span_count=1, rejected_spans=0, error=None)


def default_emitter(*, request: Mapping[str, object]) -> EmitResult:
    connection: http.client.HTTPConnection | None = None
    try:
        url = _required_str(record=request, key="url")
        headers = _required_str_dict(record=request, key="headers")
        payload = _required_payload(record=request, key="payload")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return EmitResult(
                sent=False,
                span_count=0,
                rejected_spans=0,
                error="invalid OTLP endpoint",
            )
        connection_type = (
            http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_type(host=parsed.netloc, timeout=_REQUEST_TIMEOUT_SECONDS)
        target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        _request(connection=connection, target=target, body=body, headers=headers)
        response = connection.getresponse()
        try:
            response_body = response.read()
            result = _response_result(
                status=response.status,
                reason=response.reason,
                body=response_body,
                span_count=_span_count(payload=payload),
            )
        finally:
            response.close()
    except (OSError, http.client.HTTPException, TypeError, ValueError) as exc:
        if connection is not None:
            connection.close()
        return EmitResult(
            sent=False,
            span_count=0,
            rejected_spans=0,
            error=f"{type(exc).__name__}: {exc}",
        )
    connection.close()
    return result


def _payload(*, record: Mapping[str, object], config: OtelConfig) -> OtelPayload:
    span = {
        "traceId": secrets.token_hex(16),
        "spanId": secrets.token_hex(8),
        "parentSpanId": "",
        "name": _required_str(record=record, key="event"),
        "kind": 1,
        "startTimeUnixNano": _unix_nanos(record=record),
        "endTimeUnixNano": _unix_nanos(record=record),
        "attributes": _attributes(record=record),
        "status": {"code": 2 if "error" in record else 1},
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
                        "scope": {"name": _SCOPE_NAME, "version": _SCOPE_VERSION},
                        "spans": [span],
                    }
                ],
            }
        ]
    }


def _attributes(*, record: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        _attribute(key=key, value=value) for key, value in sorted(record.items()) if key != "event"
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


def _unix_nanos(*, record: Mapping[str, object]) -> str:
    raw = _required_str(record=record, key="ts")
    parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return str(int(parsed.timestamp() * _NANOS_PER_SECOND))


def _request(
    *,
    connection: http.client.HTTPConnection,
    target: str,
    body: bytes,
    headers: dict[str, str],
) -> None:
    try:
        cast(Callable[..., None], connection.request)(
            method="POST",
            target=target,
            body=body,
            headers=headers,
        )
    except TypeError:
        connection.request("POST", target, body=body, headers=headers)


def _response_result(
    *,
    status: int,
    reason: str,
    body: bytes,
    span_count: int,
) -> EmitResult:
    rejected = _rejected_spans(body=body)
    if status >= _HTTP_ERROR_MINIMUM:
        return EmitResult(
            sent=False,
            span_count=span_count,
            rejected_spans=rejected,
            error=f"HTTP {status} {reason}".strip(),
        )
    return EmitResult(sent=True, span_count=span_count, rejected_spans=rejected, error=None)


def _rejected_spans(*, body: bytes) -> int:
    try:
        parsed: object = json.loads(body.decode() or "{}")
    except (TypeError, UnicodeDecodeError, ValueError):
        return 0
    response = jsonio.as_object(value=parsed)
    partial = jsonio.as_object(value=None if response is None else response.get("partialSuccess"))
    rejected = None if partial is None else partial.get("rejectedSpans")
    return rejected if isinstance(rejected, int) and not isinstance(rejected, bool) else 0


def _span_count(*, payload: OtelPayload) -> int:
    total = 0
    for resource_span in _object_list(value=payload.get("resourceSpans")):
        for scope_span in _object_list(value=resource_span.get("scopeSpans")):
            total += len(_object_list(value=scope_span.get("spans")))
    return total


def _object_list(*, value: object) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    if isinstance(value, list):
        for item in cast(list[object], value):
            if isinstance(item, dict):
                item_map = cast(Mapping[object, object], item)
                objects.append(
                    {str(item_key): item_value for item_key, item_value in item_map.items()}
                )
    return objects


def _required_payload(*, record: Mapping[str, object], key: str) -> OtelPayload:
    value = record.get(key)
    if not isinstance(value, dict):
        raise TypeError
    value_map = cast(Mapping[object, object], value)
    return {str(item_key): item_value for item_key, item_value in value_map.items()}


def _required_str_dict(*, record: Mapping[str, object], key: str) -> dict[str, str]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise TypeError
    value_map = cast(Mapping[object, object], value)
    if not all(
        isinstance(item_key, str) and isinstance(item_value, str)
        for item_key, item_value in value_map.items()
    ):
        raise TypeError
    return {str(item_key): str(item_value) for item_key, item_value in value_map.items()}


def _required_str(*, record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError
    return value
