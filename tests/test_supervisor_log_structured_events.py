"""Daemon stderr event records are structured and edge-triggered."""

from __future__ import annotations

import contextlib
import datetime
import importlib
import io as _io
import json
import threading
import time
from dataclasses import dataclass, field

import _supervisor_otel_report
import registry
from _supervisor_otel import EmitResult, OtelConfig
from _supervisor_otel_seam import OtelSeam
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@dataclass(kw_only=True)
class _HeldExport:
    """An export the test can observe ENTERED, hold open, and then release.

    The three events are the causal handshake: `entered` proves the exporter is
    occupied, `release` is the only thing that lets it finish, and `returned` proves
    whether it has finished yet — which is what lets a caller's completion be read as
    "while the export was still held" rather than "soon enough". `calls` is the
    enqueue count: an overflow must report without starting an export of its own.
    """

    entered: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    returned: threading.Event = field(default_factory=threading.Event)
    calls: list[dict[str, object]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def emit(self, request: dict[str, object]) -> EmitResult:
        """The injected emitter seam. Positional, because `emit_daemon_event` calls it so."""
        with self.lock:
            self.calls.append(request)
        self.entered.set()
        # A liveness guard so a failing test cannot wedge the suite, NOT a latency budget.
        _ = self.release.wait(timeout=5.0)
        self.returned.set()
        return EmitResult(sent=True, span_count=1, rejected_spans=0, error=None)


def _start_log(
    *,
    sup,
    message: str,
    callers: list[threading.Thread],
) -> threading.Event:
    """Log one daemon event from its own thread; return the event set once it COMPLETES.

    The caller runs off the main thread so a blocking log call fails a bounded wait
    instead of wedging the test. Only a thread that actually started is recorded, so
    cleanup joins exactly what is owned — joining an unstarted thread raises
    `RuntimeError` and would replace a failing assertion with that noise.
    """
    logged = threading.Event()

    def log_tick() -> None:
        sup.log(message=message, event="daemon-tick")
        logged.set()

    caller = threading.Thread(target=log_tick)
    caller.start()
    callers.append(caller)
    return logged


def _count_export_alerts(
    *,
    tmp_path,
    results: list[EmitResult],
    seconds_per_tick: float,
) -> list[dict[str, object]]:
    clock = {"now": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        now=lambda: clock["now"],
    )
    state = _supervisor_otel_report.OtelExportFailureState()

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        for result in results:
            _supervisor_otel_report.report_export_result(
                sup=sup,
                result=result,
                state=state,
            )
            clock["now"] += seconds_per_tick
    return [json.loads(line) for line in err.getvalue().splitlines()]


def test_daemon_log_lines_are_structured_events_with_shared_envelope(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    declare(repo=repo, topic=topic, value="blocked: x")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    event = json.loads(err.getvalue().splitlines()[0])
    assert event["event"] == "blocked-human"
    assert event["severity"] == "alert"
    assert event["repo"] == "repo"
    assert event["topic"] == topic
    assert event["session"] == session
    assert event["pane"] == session
    assert event["daemon_instance_id"] == sup.daemon_instance_id
    assert event["tick_generation"] == sup.tick_generation
    assert "blocked on human" in event["message"]
    assert datetime.datetime.fromisoformat(str(event["ts"]).replace("Z", "+00:00"))


def test_daemon_level_log_event_has_no_track_but_keeps_instance_and_tick(*, tmp_path):
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    sup.tick_generation = 7

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.log(message="interrupted; exiting", event="daemon-interrupted")

    event = json.loads(err.getvalue())
    assert event == {
        "daemon_instance_id": sup.daemon_instance_id,
        "event": "daemon-interrupted",
        "message": "interrupted; exiting",
        "severity": "info",
        "tick_generation": 7,
        "ts": event["ts"],
    }


def test_successful_otel_export_is_silent(*, tmp_path):
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        otel=OtelSeam(
            config=OtelConfig(
                endpoint="https://api.honeycomb.io",
                ingest_key="key",
                service_name="svc",
                service_namespace="ns",
            ),
            emitter=lambda _request: EmitResult(
                sent=True,
                span_count=1,
                rejected_spans=0,
                error=None,
            ),
        ),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.log(message="tick 1 complete", event="daemon-tick")

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert [event["event"] for event in events] == ["daemon-tick"]


def test_slow_otel_export_does_not_block_daemon_event_log(*, tmp_path):
    entered = threading.Event()
    release = threading.Event()

    def slow_emit(_request: dict[str, object]) -> EmitResult:
        entered.set()
        release.wait(timeout=5.0)
        return EmitResult(sent=True, span_count=1, rejected_spans=0, error=None)

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        otel=OtelSeam(
            config=OtelConfig(
                endpoint="https://api.honeycomb.io",
                ingest_key="key",
                service_name="svc",
                service_namespace="ns",
            ),
            emitter=slow_emit,
        ),
    )

    err = _io.StringIO()
    log_done = threading.Event()

    def log_event() -> None:
        with contextlib.redirect_stderr(err):
            sup.log(message="tick 1 complete", event="daemon-tick")
        log_done.set()

    thread = threading.Thread(target=log_event)
    thread.start()
    assert entered.wait(timeout=1.0)
    assert log_done.wait(timeout=1.0)
    release.set()
    thread.join(timeout=1.0)
    assert not thread.is_alive()
    with contextlib.redirect_stderr(err):
        sup.otel.exporter.flush(sup=sup)
    assert [json.loads(line)["event"] for line in err.getvalue().splitlines()] == ["daemon-tick"]


def test_otel_export_queue_overflow_is_reported_without_blocking(*, tmp_path, monkeypatch):
    """A full queue reports the overflow WHILE the only in-flight export is still held.

    The nonblocking claim is CAUSAL, not a stopwatch reading. An elapsed-time bound over
    two log calls proves neither that the queue overflowed nor that the caller ever waited
    on the exporter: it ran BEFORE the event assertions, and the emitter's bare sleep
    established no occupancy for it to measure. Such a bound was observed failing once at
    0.3047s against 0.05s. What slowed those two calls was never established — and that
    is the point rather than a missing detail, because the reading cannot separate the
    behaviour under test from anything else happening on the host, so no cause is claimed
    for it here. So this follows the entered/release/completion handshake of its sibling
    `test_slow_otel_export_does_not_block_daemon_event_log`: the first export is observably
    ENTERED and held, and the second daemon log call is observed to COMPLETE — with the
    queue-full error already reported — while that first export has provably not returned.
    Every bounded wait here is a liveness guard against a hang, never a latency budget.
    """
    async_otel = importlib.import_module("_supervisor_otel_async")
    monkeypatch.setattr(async_otel, "_MAX_IN_FLIGHT", 1)

    held = _HeldExport()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        otel=OtelSeam(
            config=OtelConfig(
                endpoint="https://api.honeycomb.io",
                ingest_key="key",
                service_name="svc",
                service_namespace="ns",
            ),
            emitter=held.emit,
        ),
    )

    err = _io.StringIO()
    callers: list[threading.Thread] = []
    try:
        with contextlib.redirect_stderr(err):
            first_logged = _start_log(sup=sup, message="tick 1 complete", callers=callers)
            # The single queue slot is OCCUPIED and its caller is already back, so the
            # second log below provably meets a full queue rather than a timing window.
            assert held.entered.wait(timeout=1.0)
            assert first_logged.wait(timeout=1.0)
            second_logged = _start_log(sup=sup, message="tick 2 complete", callers=callers)
            assert second_logged.wait(timeout=1.0)
            # The causal safety assertion: the second caller completed, and the exact
            # queue-full error was already reported, while the held export had NOT
            # returned. `returned` is unset across the whole inspection, both sides of it.
            assert not held.returned.is_set()
            overflow = json.loads(err.getvalue().splitlines()[-1])
            assert overflow["event"] == "otel-export-failed"
            assert overflow["error"] == "OTLP export queue full"
            assert not held.returned.is_set()
    finally:
        # Failure-safe: release the held export, join the callers this test owns, and
        # finish the exporter's own pending work so nothing runs on past the test.
        held.release.set()
        for caller in callers:
            caller.join(timeout=5.0)
        with contextlib.redirect_stderr(err):
            sup.otel.exporter.flush(sup=sup)

    assert [caller.is_alive() for caller in callers] == [False, False]
    # An overflow REPORTS; it must never enqueue a second export of its own.
    assert len(held.calls) == 1
    assert [json.loads(line)["event"] for line in err.getvalue().splitlines()] == [
        "daemon-tick",
        "daemon-tick",
        "otel-export-failed",
    ]


def test_otel_export_queue_overflow_dedups_fixed_queue_full_error(
    *,
    tmp_path,
    monkeypatch,
):
    async_otel = importlib.import_module("_supervisor_otel_async")
    monkeypatch.setattr(async_otel, "_MAX_IN_FLIGHT", 1)

    def slow_emit(_request: dict[str, object]) -> EmitResult:
        time.sleep(0.25)
        return EmitResult(sent=True, span_count=1, rejected_spans=0, error=None)

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        otel=OtelSeam(
            config=OtelConfig(
                endpoint="https://api.honeycomb.io",
                ingest_key="key",
                service_name="svc",
                service_namespace="ns",
            ),
            emitter=slow_emit,
        ),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.log(message="tick 1 complete", event="daemon-tick")
        for tick in range(16):
            sup.log(message=f"tick {tick + 2} complete", event="daemon-tick")

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    alerts = [event for event in events if event["event"] == "otel-export-failed"]
    assert len(alerts) == 1
    assert alerts[0]["error"] == "OTLP export queue full"


def test_failed_otel_export_surfaces_cause_and_rejected_count(*, tmp_path):
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        otel=OtelSeam(
            config=OtelConfig(
                endpoint="https://api.honeycomb.io",
                ingest_key="bad-key",
                service_name="svc",
                service_namespace="ns",
            ),
            emitter=lambda _request: EmitResult(
                sent=False,
                span_count=3,
                rejected_spans=3,
                error="HTTP 401 Unauthorized",
            ),
        ),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.log(message="tick 1 complete", event="daemon-tick")

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert [event["event"] for event in events] == [
        "daemon-tick",
        "otel-export-failed",
    ]
    alert = events[1]
    assert alert["severity"] == "alert"
    assert alert["error"] == "HTTP 401 Unauthorized"
    assert alert["rejected_spans"] == 3
    assert "HTTP 401 Unauthorized" in alert["message"]
    assert "rejected_spans=3" in alert["message"]


def test_persistent_otel_export_failure_reports_each_age_band_once(*, tmp_path):
    clock = {"now": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        now=lambda: clock["now"],
        otel=OtelSeam(
            config=OtelConfig(
                endpoint="https://api.honeycomb.io",
                ingest_key="bad-key",
                service_name="svc",
                service_namespace="ns",
            ),
            emitter=lambda _request: EmitResult(
                sent=False,
                span_count=1,
                rejected_spans=1,
                error="OSError: offline",
            ),
        ),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.log(message="tick 1 complete", event="daemon-tick")
        sup.otel.exporter.flush(sup=sup)
        clock["now"] += 60.0
        sup.log(message="tick 2 complete", event="daemon-tick")
        sup.otel.exporter.flush(sup=sup)
        clock["now"] += 10.0
        sup.log(message="tick 3 complete", event="daemon-tick")
        sup.otel.exporter.flush(sup=sup)

    alert_events = [
        event["event"]
        for line in err.getvalue().splitlines()
        if (event := json.loads(line))["severity"] == "alert"
    ]
    assert alert_events == [
        "otel-export-failed",
        "otel-export-failure-age-60",
    ]


def test_otel_export_failure_realerting_counts_stable_conditions_not_payload(
    *,
    tmp_path,
):
    ticks = 20
    seconds_per_tick = 60.0

    identical_failure = _count_export_alerts(
        tmp_path=tmp_path,
        results=[
            EmitResult(
                sent=False,
                span_count=1,
                rejected_spans=1,
                error="OSError: offline",
            )
            for _tick in range(ticks)
        ],
        seconds_per_tick=seconds_per_tick,
    )
    rejection = _count_export_alerts(
        tmp_path=tmp_path,
        results=[
            EmitResult(sent=True, span_count=4, rejected_spans=2, error=None)
            for _tick in range(ticks)
        ],
        seconds_per_tick=seconds_per_tick,
    )
    flapping = _count_export_alerts(
        tmp_path=tmp_path,
        results=[
            (
                EmitResult(
                    sent=False,
                    span_count=1,
                    rejected_spans=1,
                    error="OSError: offline",
                )
                if tick % 2 == 0
                else EmitResult(sent=True, span_count=1, rejected_spans=0, error=None)
            )
            for tick in range(ticks)
        ],
        seconds_per_tick=seconds_per_tick,
    )
    varying_failure = _count_export_alerts(
        tmp_path=tmp_path,
        results=[
            EmitResult(
                sent=False,
                span_count=tick + 1,
                rejected_spans=tick + 1,
                error=f"OSError: offline attempt {tick}",
            )
            for tick in range(ticks)
        ],
        seconds_per_tick=seconds_per_tick,
    )

    assert len(identical_failure) == 4
    assert len(rejection) == 4
    assert len(flapping) == 10
    assert len(varying_failure) == 4
    assert varying_failure[0]["error"] == "OSError: offline attempt 0"
    assert [event["event"] for event in varying_failure] == [
        "otel-export-failed",
        "otel-export-failure-age-60",
        "otel-export-failure-age-300",
        "otel-export-failure-age-900",
    ]


def test_partially_rejected_otel_export_surfaces_rejected_count(*, tmp_path):
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        otel=OtelSeam(
            config=OtelConfig(
                endpoint="https://api.honeycomb.io",
                ingest_key="key",
                service_name="svc",
                service_namespace="ns",
            ),
            emitter=lambda _request: EmitResult(
                sent=True,
                span_count=4,
                rejected_spans=2,
                error=None,
            ),
        ),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.log(message="tick 1 complete", event="daemon-tick")
        # The rejection is surfaced by the ASYNC exporter; drain it before reading
        # stderr so the event ordering is deterministic (matches the flush other
        # cases in this file use, e.g. test_slow_otel_export_*).
        sup.otel.exporter.flush(sup=sup)

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert [event["event"] for event in events] == [
        "daemon-tick",
        "otel-export-rejected",
    ]
    assert events[1]["rejected_spans"] == 2
