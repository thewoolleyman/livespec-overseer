"""Daemon stderr event records are structured and edge-triggered."""

from __future__ import annotations

import contextlib
import datetime
import importlib
import io as _io
import json
import time

import registry
from _supervisor_foreman import heartbeat_path
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
    started = time.monotonic()
    with contextlib.redirect_stderr(err):
        sup.log(message="tick 1 complete", event="daemon-tick")
    elapsed = time.monotonic() - started

    assert elapsed < 0.05
    assert [json.loads(line)["event"] for line in err.getvalue().splitlines()] == ["daemon-tick"]


def test_otel_export_queue_overflow_is_reported_without_blocking(*, tmp_path, monkeypatch):
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
    started = time.monotonic()
    with contextlib.redirect_stderr(err):
        sup.log(message="tick 1 complete", event="daemon-tick")
        sup.log(message="tick 2 complete", event="daemon-tick")
    elapsed = time.monotonic() - started

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert elapsed < 0.05
    assert [event["event"] for event in events] == [
        "daemon-tick",
        "daemon-tick",
        "otel-export-failed",
    ]
    assert events[2]["error"] == "OTLP export queue full"


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
        clock["now"] += 60.0
        sup.log(message="tick 2 complete", event="daemon-tick")
        clock["now"] += 10.0
        sup.log(message="tick 3 complete", event="daemon-tick")

    alert_events = [
        event["event"]
        for line in err.getvalue().splitlines()
        if (event := json.loads(line))["severity"] == "alert"
    ]
    assert alert_events == [
        "otel-export-failed",
        "otel-export-failure-age-60",
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

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert [event["event"] for event in events] == [
        "daemon-tick",
        "otel-export-rejected",
    ]
    assert events[1]["rejected_spans"] == 2


def test_foreman_stale_alert_dedups_when_age_and_tick_advance(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    path = heartbeat_path(repo=str(repo))
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "written_at": "1970-01-01T00:00:00Z",
                "pid": 309170,
                "tick_generation": 42,
                "tick_interval_seconds": 10,
            }
        ),
        encoding="utf-8",
    )
    clock = {"now": 60 * 60.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        now=lambda: clock["now"],
        watch_repos=[str(repo)],
        watch_set_path=None,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        _ = sup.tick(act=True)
        clock["now"] += 60.0
        sup.tick_generation += 1
        _ = sup.tick(act=True)

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "foreman-heartbeat-stale"
    assert event["repo"] == "repo"
    assert event["topic"] == "foreman"
    assert event["age_minutes"] == 60
    assert event["pid"] == 309170
    assert event["tick"] == 42
    assert event["interval"] == 10
    assert "foreman heartbeat stale: foreman heartbeat stale" not in event["message"]
