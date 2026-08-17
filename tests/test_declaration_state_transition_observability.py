"""Declaration state transitions leave edge logs and on-disk diagnostics."""

from __future__ import annotations

import contextlib
import io as _io

import _supervisor_config
import _supervisor_state
import pytest
import registry
import signals
from test_supervisor_builders import (
    arm_ready_marker,
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_stale_blocked_void_leaves_diagnostic_and_one_edge_log(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value="blocked: stale reason", mtime=800.0)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        assert sup.evaluate(track=track, act=True).status == "working"

    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_BLOCKED_VOIDED
    assert "session resumed generating" in state.detail
    assert err.getvalue().count("voided stale blocked declaration") == 1

    with contextlib.redirect_stderr(_io.StringIO()) as second_err:
        assert sup.evaluate(track=track, act=True).status == "working"
    assert second_err.getvalue().count("voided stale blocked declaration") == 0


def test_ready_expiry_leaves_diagnostic_and_one_edge_log(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: 1001.0 + _supervisor_config.READY_ARM_MAX_AGE + 1.0,
    )
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity="claude:topic:topic",
        stamp_path=sup.stamp_path,
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        assert _supervisor_state.expire_aged_ready(sup=sup, track=track) is True

    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_READY_EXPIRED
    assert "ready declaration exceeded" in state.detail
    assert err.getvalue().count("expired ready declaration") == 1

    with contextlib.redirect_stderr(_io.StringIO()) as second_err:
        assert _supervisor_state.expire_aged_ready(sup=sup, track=track) is False
    assert second_err.getvalue().count("expired ready declaration") == 0


def test_successful_restart_consumes_ready_with_diagnostic_and_one_edge_log(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        assert sup.evaluate(track=track, act=True).status == "restarting"

    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_RESTARTED
    assert "restart completed" in state.detail
    assert err.getvalue().count("consumed ready declaration") == 1

    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()) as second_err:
        sup.evaluate(track=track, act=True)
    assert not fake.has(method="respawn")
    assert second_err.getvalue().count("consumed ready declaration") == 0


def test_idle_marker_clear_leaves_diagnostic_and_one_edge_log(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    track = mapped_track(repo=repo, topic=topic, session=session)

    _ = sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1

    sup.claude_status_by_session = {session: "busy"}
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        assert sup.evaluate(track=track, act=True).status == "working"

    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_IDLE_NUDGE_CLEARED
    assert "session left idle episode" in state.detail
    assert err.getvalue().count("cleared idle-with-context-left marker") == 1

    sup.claude_status_by_session = {session: "idle"}
    with contextlib.redirect_stderr(_io.StringIO()) as second_err:
        assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1
    assert second_err.getvalue().count("cleared idle-with-context-left marker") == 0
