"""History events for ready declarations held by the restart interlock."""

from __future__ import annotations

import contextlib
import io
import json

import _supervisor_config
import registry
import signals
from test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_ready_held_by_idle_pane_with_busy_session_status_is_reported(*, tmp_path, monkeypatch):
    """A false harness busy state is distinguishable from work in event history."""
    monkeypatch.setattr(_supervisor_config, "READY_HOLD_REPORT_AFTER", 30.0, raising=False)
    monkeypatch.setattr(_supervisor_config, "READY_HOLD_REPORT_WINDOW", 60.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session[session] = "busy"
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "working"
    clock["t"] += 31.0
    with contextlib.redirect_stderr(io.StringIO()) as err:
        assert sup.evaluate(track=track, act=True).status == "working"
        clock["t"] += 1.0
        assert sup.evaluate(track=track, act=True).status == "working"
        clock["t"] += 60.0
        assert sup.evaluate(track=track, act=True).status == "working"

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    held = [event for event in events if event["event"] == "ready-replacement-held"]
    assert len(held) == 2
    assert held[0]["topic"] == topic
    assert "busy: session-file status busy" in held[0]["message"]
    assert "idle composer with no spinner or background wait" in held[0]["message"]


def test_ready_hold_events_name_each_busy_source_and_settle_guard(*, tmp_path, monkeypatch):
    """Every restart interlock guard leaves a durable, specific history event."""
    monkeypatch.setattr(_supervisor_config, "READY_HOLD_REPORT_AFTER", 30.0, raising=False)
    cases = (
        ("pane spinner", busy_capture(ctx=40), "idle", "busy: pane spinner"),
        (
            "background wait",
            "Waiting for 2 background\n  Ctx: 40% left\n",
            "idle",
            "busy: background wait",
        ),
        ("not idle", "stale pane with no composer\n  Ctx: 40% left\n", "idle", "not-idle"),
        (
            "unsettled",
            [
                idle_capture(ctx=40, body="one"),
                idle_capture(ctx=40, body="two"),
                idle_capture(ctx=40, body="three"),
                idle_capture(ctx=40, body="four"),
                idle_capture(ctx=40, body="five"),
                idle_capture(ctx=40, body="six"),
            ],
            "idle",
            "unsettled",
        ),
    )
    for index, (_name, capture, status, expected) in enumerate(cases):
        repo, topic = make_plan(
            tmp_path=tmp_path, repo_name=f"repo-{index}", topic=f"topic-{index}"
        )
        session = registry.tmux_id(repo=str(repo), topic=topic)
        fake = FakeTmux()
        fake.serve(session=session, repo=repo, capture=capture)
        clock = {"t": 1000.0}
        sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda clock=clock: clock["t"])
        sup.claude_status_by_session[session] = status
        declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
        track = mapped_track(repo=repo, topic=topic, session=session)

        sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        with contextlib.redirect_stderr(io.StringIO()) as err:
            sup.evaluate(track=track, act=True)

        events = [json.loads(line) for line in err.getvalue().splitlines()]
        assert any(
            event["event"] == "ready-replacement-held" and expected in event["message"]
            for event in events
        )


def test_ready_hold_event_names_post_settle_pane_identity_mismatch(*, tmp_path, monkeypatch):
    """The final identity recheck cannot leave a ready declaration silently held."""
    monkeypatch.setattr(_supervisor_config, "READY_HOLD_REPORT_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40), cmd=["node", "zsh"])
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "settling"
    fake._cmd_idx.pop(session, None)
    clock["t"] += 31.0
    with contextlib.redirect_stderr(io.StringIO()) as err:
        assert sup.evaluate(track=track, act=True).status == "settling"

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    assert any(
        event["event"] == "ready-replacement-held" and "pane-identity mismatch" in event["message"]
        for event in events
    )


def test_second_ready_declaration_gets_its_own_hold_window(*, tmp_path, monkeypatch):
    """A ready hold ends with its declaration; a later ready episode starts a fresh window."""
    monkeypatch.setattr(_supervisor_config, "READY_HOLD_REPORT_AFTER", 30.0, raising=False)
    monkeypatch.setattr(_supervisor_config, "READY_HOLD_REPORT_WINDOW", 5.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session[session] = "busy"
    state_file = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    clock["t"] += 31.0
    with contextlib.redirect_stderr(io.StringIO()) as first:
        sup.evaluate(track=track, act=True)
    state_file.unlink()
    clock["t"] += 9.0
    sup.evaluate(track=track, act=True)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1002.0)
    clock["t"] += 1.0
    with contextlib.redirect_stderr(io.StringIO()) as second:
        sup.evaluate(track=track, act=True)

    assert "ready-replacement-held" in first.getvalue()
    assert "ready-replacement-held" not in second.getvalue()
