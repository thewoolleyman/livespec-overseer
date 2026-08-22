"""Daemon stderr event records are structured and edge-triggered."""

from __future__ import annotations

import contextlib
import datetime
import io as _io
import json

import registry
from _supervisor_foreman import heartbeat_path
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
