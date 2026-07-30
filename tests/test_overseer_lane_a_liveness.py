"""Acceptance tests for Lane A liveness foundations."""

import contextlib
import io as _io
import os

import pytest
import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_blocked_alerts_quantize_age_to_bands(*, tmp_path):
    """A standing blocked declaration reports age on entry and crossed bands only.

    This pins both directions: age belongs in the alert, but a free-running age
    must not change the alert line every tick.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    declare(repo=repo, topic=topic, value="blocked: needs a human", mtime=100.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)
        assert view.status == "blocked:human"
        assert "15m" in (view.note or "")
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)
        clock["t"] = 100.0 + (4 * 3600.0) + 1.0
        view = sup.evaluate(track=track, act=True)
        assert "4h" in (view.note or "")
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)
        clock["t"] = 100.0 + (24 * 3600.0) + 1.0
        view = sup.evaluate(track=track, act=True)
        assert "24h" in (view.note or "")
    surfaced = [ln for ln in err.getvalue().splitlines() if "overseer[SURFACE]" in ln]
    assert len(surfaced) == 3, surfaced
    assert "blocked on human (15m):" in surfaced[0]
    assert "blocked on human (4h):" in surfaced[1]
    assert "blocked on human (24h):" in surfaced[2]


def test_blocked_age_bands_reset_for_a_new_declaration(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    clock = {"t": 100.0 + (4 * 3600.0) + 1.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    state = declare(repo=repo, topic=topic, value="blocked: first", mtime=100.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=track, act=True)
        state.write_text("blocked: second\n")
        os.utime(state, (clock["t"], clock["t"]))
        sup.evaluate(track=track, act=True)
    surfaced = [ln for ln in err.getvalue().splitlines() if "overseer[SURFACE]" in ln]
    assert len(surfaced) == 2, surfaced
    assert "blocked on human (4h): first" in surfaced[0]
    assert "blocked on human (0m): second" in surfaced[1]


def test_condition_alert_rearms_when_that_condition_clears(*, tmp_path):
    """A cleared condition re-arms even while another condition keeps the row in NEEDS YOU."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=50))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        declare(repo=repo, topic=topic, value="blocked: same reason")
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        declare(repo=repo, topic=topic, value="redy")
        malformed = sup.evaluate(track=track, act=True)
        assert malformed.note is not None and malformed.note.startswith("BAD state file")
        declare(repo=repo, topic=topic, value="blocked: same reason")
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
    surfaced = [ln for ln in err.getvalue().splitlines() if "overseer[SURFACE]" in ln]
    blocked_lines = [ln for ln in surfaced if "blocked on human" in ln]
    assert len(blocked_lines) == 2, surfaced


def test_stale_last_known_ctx_demotes_to_unknown_and_surfaces_low_track(*, tmp_path):
    """A stale last-known ctx value cannot keep satisfying ctx gates forever.

    The low last-known value still surfaces as attention because losing sight of a
    low-context track is itself actionable. A fresh parse restores normal ctx gates.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    assert wrapup_count(fake=fake) == 1

    registry.clear_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    fake.calls.clear()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=None))
    clock["t"] += 3600.0 + 1.0
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)
    assert view.status == "ctx-stale"
    assert view.ctx is None
    assert "ctx unreadable (1h)" in (view.note or "")
    assert not fake.has(method="paste")
    assert "context unreadable for 1h" in err.getvalue()

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=55))
    view = sup.evaluate(track=track, act=True)
    assert view.status == "idle-with-context-left"
    assert view.ctx == 55


def test_stale_above_threshold_ctx_is_a_note_not_attention(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=70))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=None))
    clock["t"] += 3600.0 + 1.0
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)
    assert view.status == "idle"
    assert view.ctx is None
    assert "ctx unreadable (1h)" in (view.note or "")
    assert "overseer[SURFACE]" not in err.getvalue()
    assert signals.read_state(repo=str(repo), topic=topic) is None
