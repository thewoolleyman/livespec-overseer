"""Foreman self-restart tests for old uncertifiable ready declarations."""

import contextlib
import importlib
import io as _io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import foreman_runtime_identity
import foreman_stop_state
import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def foreman_track(*, repo):
    topic = foreman_runtime_identity.canonical_session_name(repo=repo)
    return registry.ForemanSeat(
        topic=topic,
        repo=str(repo),
        tmux=topic,
        epic="overseer-foreman-epic",
        added_at="2026-08-23T00:00:00Z",
    )


def test_foreman_ready_below_self_restart_floor_does_not_respawn(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    track = foreman_track(repo=repo)
    fake = FakeTmux()
    fake.serve(session=track.tmux, repo=repo, capture=idle_capture(ctx=79))
    declare(repo=repo, topic=track.topic, value=signals.STATE_READY, mtime=1000.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0 + 3599.0)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    assert not fake.has(method="respawn")


def test_self_restart_helper_ignores_non_foreman_tracks(*, tmp_path):
    module_path = (
        Path(__file__).resolve().parents[1] / "overseer" / ("_supervisor_foreman_self_restart.py")
    )
    assert module_path.is_file()
    helper = importlib.import_module("_supervisor_foreman_self_restart")
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=79))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0 + 3601.0)

    restarted = helper.maybe_self_restart_foreman(
        sup=sup,
        track=registry.Track(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic="overseer-plan-epic",
        ),
        session=session,
        pane=session,
        obs=None,
        age=3601.0,
    )

    assert not restarted
    assert not fake.has(method="respawn")


def test_foreman_self_restart_respawns_once_and_persists_loud_fact(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    track = foreman_track(repo=repo)
    fake = FakeTmux()
    fake.serve(session=track.tmux, repo=repo, capture=idle_capture(ctx=79))
    declare(repo=repo, topic=track.topic, value=signals.STATE_READY, mtime=1000.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0 + 3601.0)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    respawns = [call for call in fake.calls if call[0] == "respawn"]
    assert len(respawns) == 1
    _method, pane, cwd, command, env = respawns[0]
    assert pane == track.tmux
    assert cwd == str(repo)
    assert "claude " in command
    assert f"-n {track.topic}" in command
    assert env["LIVESPEC_PLAN_UNATTENDED"] == "1"
    assert "daemon failed to act within 1h" in err.getvalue()
    persisted = registry.read_foreman_self_restart(
        repo=str(repo), topic=track.topic, stamp_path=sup.stamp_path
    )
    assert persisted.attempted
    assert persisted.reason == "daemon failed to act within 1h"

    declare(repo=repo, topic=track.topic, value=signals.STATE_READY, mtime=5000.0)
    second = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 5000.0 + 3601.0)
    with contextlib.redirect_stderr(err):
        second_view = second.evaluate(track=track, act=True)

    assert second_view.status == "ready-uncertifiable"
    assert len([call for call in fake.calls if call[0] == "respawn"]) == 1
    assert "foreman self-restart already used for this session lineage" in err.getvalue()


def test_foreman_self_restart_refuses_declared_hold_with_reason(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    track = foreman_track(repo=repo)
    fake = FakeTmux()
    fake.serve(session=track.tmux, repo=repo, capture=idle_capture(ctx=79))
    declare(repo=repo, topic=track.topic, value=signals.STATE_READY, mtime=1000.0)
    hold = foreman_stop_state.foreman_hold_path(repo=repo)
    hold.parent.mkdir(parents=True, exist_ok=True)
    hold.write_text("# Hold\n\nmaintenance window\n", encoding="utf-8")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0 + 3601.0)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    assert not fake.has(method="respawn")
    assert "foreman self-restart refused because foreman loop is held: maintenance window" in (
        err.getvalue()
    )
