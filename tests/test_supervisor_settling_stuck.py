"""Tests for below-threshold settling liveness attention."""

import contextlib
import io as _io

import _supervisor_config
import pytest
import registry
import supervisor
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def foreman_settling_capture(*, ctx: int) -> str:
    return (
        "last daemon-log line for this track: 2026-08-20T12:36:09Z\n"
        "waiting at a prompt whose border shape is not recognized\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def test_low_context_settling_past_bound_is_attention_not_green(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SETTLING_STUCK_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path, topic="livespec-overseer-foreman")
    session = registry.tmux_id(repo=str(repo), topic=topic, allow_reserved=True)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=foreman_settling_capture(ctx=14))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    first = sup.evaluate(track=track, act=True)
    clock["t"] += 31.0
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        stuck = sup.evaluate(track=track, act=True)
        clock["t"] += 61.0
        again = sup.evaluate(track=track, act=True)

    assert first.status == "settling"
    assert stuck.status == "settling-stuck"
    assert "settling 0m" in (stuck.note or "")
    assert supervisor.needs_attention(row=stuck) is True
    assert "settling stuck (0m)" in err.getvalue()
    assert err.getvalue().count("overseer[SURFACE]") == 1
    assert again.status == "settling-stuck"
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_above_threshold_settling_does_not_alert(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SETTLING_STUCK_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=foreman_settling_capture(ctx=80))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "settling"
    clock["t"] += 31.0
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        row = sup.evaluate(track=track, act=True)

    assert row.status == "settling"
    assert supervisor.needs_attention(row=row) is False
    assert "settling stuck" not in err.getvalue()


def test_streaming_pane_does_not_accumulate_settling_stuck(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SETTLING_STUCK_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=[
            idle_capture(ctx=40, body="frame one"),
            idle_capture(ctx=40, body="frame two"),
            idle_capture(ctx=40, body="frame three"),
        ],
    )
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "working"
    clock["t"] += 31.0
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        row = sup.evaluate(track=track, act=True)

    assert row.status == "warned"
    assert "settling stuck" not in err.getvalue()


def test_mid_tick_managed_flip_does_not_accumulate_settling_stuck(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SETTLING_STUCK_AFTER", 30.0, raising=False)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=14), cmd=["node", "zsh"])
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "settling"
    clock["t"] += 31.0
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        row = sup.evaluate(track=track, act=True)

    assert row.status == "session-gone"
    assert "settling stuck" not in err.getvalue()
