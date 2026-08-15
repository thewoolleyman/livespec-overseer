"""Beside-tests for recovered-round closure guard edges."""

from __future__ import annotations

import _supervisor_observe
import _supervisor_round_recovery
import registry
import signals
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _request(*, tmp_path, ctx=80):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=900.0,
        session_identity="claude:topic:topic",
        stamp_path=sup.stamp_path,
    )
    registry.add_notified_band(repo=str(repo), topic=topic, band=50, stamp_path=sup.stamp_path)
    obs = _supervisor_observe.observe(
        sup=sup,
        track=track,
        session=session,
        target=session,
        key=(str(repo), topic),
    )
    request = _supervisor_round_recovery.RecoveryRequest(
        sup=sup,
        track=track,
        obs=obs,
        session=session,
        target=session,
        threshold=50,
    )
    return repo, topic, fake, request


def _round_at(*, repo, topic, request):
    return registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=request.sup.stamp_path
    ).at


def test_recovered_round_closure_treats_daemon_idle_marker_as_absent(*, tmp_path):
    repo, topic, fake, request = _request(tmp_path=tmp_path)
    state = declare(
        repo=repo,
        topic=topic,
        value=signals.STATE_IDLE_WITH_CONTEXT_LEFT,
        mtime=1001.0,
    )

    assert _supervisor_round_recovery.close_recovered_round(request=request) is True

    assert _round_at(repo=repo, topic=topic, request=request) is None
    assert state.read_text(encoding="utf-8") == f"{signals.STATE_IDLE_WITH_CONTEXT_LEFT}\n"
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_recovered_round_closure_defers_when_pane_identity_changes(*, tmp_path):
    repo, topic, _fake, request = _request(tmp_path=tmp_path)

    request.sup.tmux.cmds[request.session] = "zsh"

    assert _supervisor_round_recovery.close_recovered_round(request=request) is False
    assert _round_at(repo=repo, topic=topic, request=request) == 900.0


def test_recovered_round_closure_defers_when_state_appears_during_reread(*, tmp_path, monkeypatch):
    repo, topic, _fake, request = _request(tmp_path=tmp_path)
    original_observe = _supervisor_observe.observe

    def observe_and_declare(*, sup, track, session, target, key):
        declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
        return original_observe(sup=sup, track=track, session=session, target=target, key=key)

    monkeypatch.setattr(_supervisor_observe, "observe", observe_and_declare)

    assert _supervisor_round_recovery.close_recovered_round(request=request) is False
    assert _round_at(repo=repo, topic=topic, request=request) == 900.0
