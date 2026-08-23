"""Banded operator reporting for OTLP export failures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import streams
from _supervisor_config import OTEL_EXPORT_FAILURE_ALERT_BANDS, iso_now
from _supervisor_liveness_time import age_label

if TYPE_CHECKING:
    import _supervisor_otel
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "OtelExportFailureState",
    "report_export_result",
]


@dataclass(kw_only=True)
class OtelExportFailureState:
    first_seen: float | None = None
    alerted_bands: set[int] = field(default_factory=set)
    last_identity: str | None = None


def report_export_result(
    *,
    sup: Supervisor,
    result: _supervisor_otel.EmitResult,
    state: OtelExportFailureState,
) -> None:
    """Report failed/rejected exports once on entry, then once per crossed age band."""
    if result.error is None and result.rejected_spans <= 0:
        state.first_seen = None
        state.alerted_bands = set()
        state.last_identity = None
        return
    now = sup.now()
    if state.first_seen is None:
        state.first_seen = now
        state.alerted_bands = set()
    age = max(0.0, now - state.first_seen)
    identity = _identity(result=result)
    if state.last_identity != identity:
        state.last_identity = identity
        _write_alert(sup=sup, result=result, age=age, condition=_condition(result=result))
    for band in _crossed_bands(age=age):
        if band in state.alerted_bands:
            continue
        state.alerted_bands.add(band)
        _write_alert(
            sup=sup,
            result=result,
            age=band,
            condition=f"otel-export-failure-age-{band}",
        )


def _identity(*, result: _supervisor_otel.EmitResult) -> str:
    # Identity follows the same rule as the stale-foreman alert dedup:
    # key on the stable operator condition and keep volatile payload out.
    # `error`, `rejected_spans`, `span_count`, and `sent` remain reported
    # fields, but transport detail and counters can vary every tick without
    # changing the operator response. `sent` is stable for the rejected path,
    # but redundant once the condition has selected failed versus rejected.
    return _condition(result=result)


def _condition(*, result: _supervisor_otel.EmitResult) -> str:
    if result.error is not None:
        return "otel-export-failed"
    return "otel-export-rejected"


def _crossed_bands(*, age: float) -> list[int]:
    return [int(band) for band in OTEL_EXPORT_FAILURE_ALERT_BANDS if age >= band]


def _write_alert(
    *,
    sup: Supervisor,
    result: _supervisor_otel.EmitResult,
    age: float,
    condition: str,
) -> None:
    cause = result.error or "partial rejection"
    message = (
        f"OTLP export failed ({age_label(seconds=age)}): {cause}; "
        f"rejected_spans={result.rejected_spans}; span_count={result.span_count}"
    )
    record = {
        "ts": iso_now(),
        "event": condition,
        "severity": "alert",
        "daemon_instance_id": sup.daemon_instance_id,
        "tick_generation": sup.tick_generation,
        "message": message,
        "error": result.error,
        "rejected_spans": result.rejected_spans,
        "span_count": result.span_count,
        "sent": result.sent,
        "age_seconds": int(age),
    }
    streams.write_stderr(
        text=f"{json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
    )
