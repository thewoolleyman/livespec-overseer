"""The report-only undeclared-idle attention arc, end to end.

These re-home coverage the foreman-test deletion took with it: the seat retired by
SPECIFICATION v047 owned the only tests that walked a track from
`idle-with-context-left` into `undeclared-idle` and back out of it again.

The behaviour under test is `overseer-j2vbcq`'s: a session idle ABOVE the wind-down
threshold that has declared neither `ready`, `blocked` nor `winding-down` tells the
daemon nothing about whether it is waiting on a human or has simply run out of queue.
Past a floor that condition becomes an attention row and one alert — report-only, never
a keystroke and never a restart — and past a further bound it stops being raised at all,
because a report that stands forever is a shield rather than a signal.
"""

from __future__ import annotations

import contextlib
import io as _io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_config
import _supervisor_undeclared_idle
import registry
import supervisor
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _idling_above_threshold(*, tmp_path):
    """A track idle at an empty prompt well above threshold, declaring nothing.

    Ticked once so the condition episode starts; the caller advances the clock to
    choose where in the floor/bound window the next observation lands.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    track = mapped_track(repo=repo, topic=topic, session=session)
    with contextlib.redirect_stderr(_io.StringIO()):
        first = sup.evaluate(track=track, act=True)
    assert first.status == _supervisor_undeclared_idle.UNDECLARED_IDLE_SOURCE_STATUS
    return sup, fake, track, clock


def _evaluate(*, sup, track, act=True):
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=act)
    return view, err.getvalue()


# The condition episode only accumulates across observations no further apart than
# `CONDITION_CONTINUITY_GAP`, so a streak is grown by ticking rather than by one jump.
_STEP = _supervisor_config.CONDITION_CONTINUITY_GAP - 1.0


def _idle_for(*, sup, track, clock, seconds: float, act: bool = True) -> str:
    """Keep the track continuously idle until its episode is at least ``seconds`` old.

    Returns everything the daemon emitted across the ramp, because an edge-triggered
    alert fires on the tick that first crosses a floor rather than on the last one.
    """
    log: list[str] = []
    elapsed = 0.0
    while elapsed < seconds:
        clock["t"] += _STEP
        elapsed += _STEP
        _, err = _evaluate(sup=sup, track=track, act=act)
        log.append(err)
    return "".join(log)


def test_an_undeclared_idle_track_below_the_floor_stays_on_the_plain_idle_leaf(*, tmp_path):
    sup, fake, track, clock = _idling_above_threshold(tmp_path=tmp_path)
    _idle_for(
        sup=sup,
        track=track,
        clock=clock,
        seconds=_supervisor_config.UNDECLARED_IDLE_AFTER - 2 * _STEP,
    )

    view, _ = _evaluate(sup=sup, track=track)

    assert view.status == _supervisor_undeclared_idle.UNDECLARED_IDLE_SOURCE_STATUS
    assert not fake.has(method="respawn")


def test_past_the_floor_it_becomes_an_attention_row_naming_the_streak_and_the_bound(*, tmp_path):
    sup, fake, track, clock = _idling_above_threshold(tmp_path=tmp_path)
    _idle_for(sup=sup, track=track, clock=clock, seconds=_supervisor_config.UNDECLARED_IDLE_AFTER)

    view, _ = _evaluate(sup=sup, track=track)

    assert view.status == _supervisor_undeclared_idle.UNDECLARED_IDLE_STATUS
    assert supervisor.needs_attention(row=view) is True
    note = view.note or ""
    assert "undeclared 2h" in note
    assert "no ready, blocked or winding-down declaration" in note
    assert "report-only, reported until 8h" in note
    assert not fake.has(method="respawn")


def test_the_alert_names_the_fixed_floor_rather_than_the_growing_streak_age(*, tmp_path):
    """Keying the alert text on the floor is what keeps it edge-triggered.

    Quoting the live streak age would change the text every tick, and an alert
    re-emits when its own text changes — burying the daemon log under identical lines.
    """
    sup, _fake, track, clock = _idling_above_threshold(tmp_path=tmp_path)
    first_err = _idle_for(
        sup=sup, track=track, clock=clock, seconds=_supervisor_config.UNDECLARED_IDLE_AFTER
    )
    second_err = _idle_for(sup=sup, track=track, clock=clock, seconds=3600.0)
    later, tail_err = _evaluate(sup=sup, track=track)
    second_err += tail_err

    assert "undeclared idle (2h)" in first_err
    assert "report-only, no restart authorized" in first_err
    assert "current streak age is in the row note" in first_err
    assert later.status == _supervisor_undeclared_idle.UNDECLARED_IDLE_STATUS
    assert "undeclared 3h" in (later.note or "")
    assert "undeclared idle" not in second_err


def test_a_read_only_evaluation_reports_the_status_without_alerting(*, tmp_path):
    """`list` classifies the row identically while raising no alert of its own."""
    sup, _fake, track, clock = _idling_above_threshold(tmp_path=tmp_path)
    ramp = _idle_for(
        sup=sup,
        track=track,
        clock=clock,
        seconds=_supervisor_config.UNDECLARED_IDLE_AFTER,
        act=False,
    )

    view, err = _evaluate(sup=sup, track=track, act=False)

    assert view.status == _supervisor_undeclared_idle.UNDECLARED_IDLE_STATUS
    assert "undeclared idle" not in ramp
    assert "undeclared idle" not in err


def test_past_the_reported_until_bound_the_condition_stops_being_raised(*, tmp_path):
    """The bound. The episode clock keeps running, so the row falls back to plain idle."""
    sup, _fake, track, clock = _idling_above_threshold(tmp_path=tmp_path)
    _idle_for(
        sup=sup,
        track=track,
        clock=clock,
        seconds=_supervisor_config.UNDECLARED_IDLE_REPORTED_UNTIL,
    )

    view, err = _evaluate(sup=sup, track=track)

    assert view.status == _supervisor_undeclared_idle.UNDECLARED_IDLE_SOURCE_STATUS
    assert view.note is None
    assert "undeclared idle" not in err


def test_a_session_that_declares_blocked_leaves_the_condition_entirely(*, tmp_path):
    """The condition is about the ABSENCE of a declaration, so declaring ends it."""
    sup, _fake, track, clock = _idling_above_threshold(tmp_path=tmp_path)
    _idle_for(sup=sup, track=track, clock=clock, seconds=_supervisor_config.UNDECLARED_IDLE_AFTER)
    raised, _ = _evaluate(sup=sup, track=track)
    state = Path(track.repo) / "tmp" / "overseer" / track.topic / ".overseer-state"
    state.write_text("blocked: waiting on the maintainer\n", encoding="utf-8")

    declared, _ = _evaluate(sup=sup, track=track)

    assert raised.status == _supervisor_undeclared_idle.UNDECLARED_IDLE_STATUS
    assert declared.status == "blocked:human"
