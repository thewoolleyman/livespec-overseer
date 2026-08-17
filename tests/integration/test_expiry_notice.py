"""Integration-tier scenario tests for the v016 bounded expiry-notice.

Tier: `tests.integration` is one of the documented governed scenario tiers.
"""

from __future__ import annotations

import io as _io

import _supervisor_config

from overseer import registry, signals
from overseer.test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux

MAX_AGE = _supervisor_config.READY_ARM_MAX_AGE


def _open_delivered_round(*, tmp_path, clock, ctx=40):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    opened = sup.evaluate(track=track, act=True)

    assert len(fake.paste_texts()) == 1
    return repo, topic, session, fake, sup, track, opened.status


def _expire_a_declaration(*, fixture, clock, mtime):
    """Declare ready, age it past the maximum, and let the daemon expire it."""
    repo, topic, session, _fake, sup, track, _status = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)
    clock["t"] = mtime + MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)
    assert signals.read_state(repo=str(repo), topic=topic) is None


def _notice_texts(*, fake: FakeTmux) -> list[str]:
    return [text for text in fake.paste_texts() if "EXPIRED" in text]


def test_scenario_an_expired_ready_declaration_is_answered_with_one_expiry_notice(*, tmp_path):
    """One notice per round, naming the state-file path and the fresh-ready rule, and
    the once-per-round bound is DURABLE across a daemon instance swap."""
    clock = {"t": 1000.0}
    fixture = _open_delivered_round(tmp_path=tmp_path, clock=clock)
    repo, topic, session, fake, sup, track, status = fixture
    assert status == "warned"
    bands = registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    _expire_a_declaration(fixture=fixture, clock=clock, mtime=1010.0)
    clock["t"] += 1.0
    sup.evaluate(track=track, act=True)

    notices = _notice_texts(fake=fake)
    assert len(notices) == 1
    assert str(signals.state_path(repo=str(repo), topic=topic)) in notices[0]
    assert "A restart requires a fresh ready." in notices[0]
    assert "blocked: <one-line reason>" in notices[0]
    assert registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=sup.stamp_path
    ).expiry_notice_sent

    # A fresh daemon instance over the same sidecar, and a second expiry in the same
    # round: the durable bound holds and no notified band is re-sent.
    successor = make_supervisor(
        tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO()
    )
    successor_fixture = (repo, topic, session, fake, successor, track, status)
    _expire_a_declaration(fixture=successor_fixture, clock=clock, mtime=clock["t"] + 10.0)
    clock["t"] += 1.0
    successor.evaluate(track=track, act=True)

    assert len(_notice_texts(fake=fake)) == 1
    assert (
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == bands
    )
    assert len([call for call in fake.calls if call[0] == "respawn"]) == 0


def test_scenario_repeated_expiries_never_resend_an_already_notified_band(*, tmp_path):
    """However many declarations expire inside one round, the round's durable record and
    its notified bands survive and at most one expiry-notice is sent."""
    clock = {"t": 1000.0}
    fixture = _open_delivered_round(tmp_path=tmp_path, clock=clock)
    repo, topic, session, fake, sup, track, _status = fixture
    bands = registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    for _cycle in range(3):
        _expire_a_declaration(fixture=fixture, clock=clock, mtime=clock["t"] + 10.0)
        clock["t"] += 1.0
        sup.evaluate(track=track, act=True)

    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.at == 1000.0
    assert record.bands == bands
    assert len(_notice_texts(fake=fake)) == 1
    assert len([call for call in fake.calls if call[0] == "respawn"]) == 0


def test_an_armed_declaration_that_saw_more_output_degrades_without_expiry_notice(*, tmp_path):
    """Activity degrades a declaration, so ready-expiry notice no longer applies."""
    clock = {"t": 1000.0}
    fixture = _open_delivered_round(tmp_path=tmp_path, clock=clock)
    repo, topic, session, fake, sup, track, _status = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1190.0
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))

    assert sup.evaluate(track=track, act=True).status == "working"
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_WINDING_DOWN
    assert state.detail == "auto @1190"

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    winding_down = sup.evaluate(track=track, act=True)

    assert winding_down.status == "winding-down"
    assert _notice_texts(fake=fake) == []
