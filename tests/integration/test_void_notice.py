"""Integration-tier scenario test for the ready-void notice.

Tier: `tests.integration` is one of the documented governed scenario tiers.
"""

from __future__ import annotations

import io as _io

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

_NOTICE_SENTINEL = "ready declaration was voided because this session resumed work"


def _open_delivered_round(*, tmp_path, clock):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"
    assert len(fake.paste_texts()) == 1
    return repo, topic, session, fake, sup, track


def _void_stale_ready(*, fixture, clock, mtime):
    repo, topic, session, fake, sup, track = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)
    clock["t"] = mtime + 180.0
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))

    voided = sup.evaluate(track=track, act=True)

    assert voided.status == "working"
    assert signals.read_state(repo=str(repo), topic=topic) is None


def _notice_pastes(*, fake):
    return [text for text in fake.paste_texts() if _NOTICE_SENTINEL in text]


def test_scenario_a_voided_ready_declaration_is_answered_with_one_notice(*, tmp_path):
    """Scenario: A voided ready declaration is answered with one durable bounded void-notice.

    Given a delivered round in which a stale ready declaration was voided, the next
    guarded idle observation sends one bounded void-notice. The notice names the exact
    state-file path, the three writable values, and the fresh-ready restart rule. A second
    void in the same round sends no second notice, even through a daemon instance swap, and
    no already-notified escalation band is re-sent.
    """
    clock = {"t": 1000.0}
    fixture = _open_delivered_round(tmp_path=tmp_path, clock=clock)
    repo, topic, session, fake, _sup, _track = fixture
    _void_stale_ready(
        fixture=fixture,
        clock=clock,
        mtime=1010.0,
    )

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    noticed = _sup.evaluate(track=_track, act=True)

    assert noticed.status == "warned"
    notices = _notice_pastes(fake=fake)
    assert len(notices) == 1
    notice = notices[0]
    assert str(signals.state_path(repo=str(repo), topic=topic)) in notice
    assert "winding-down" in notice
    assert "ready" in notice
    assert "blocked: <one-line reason>" in notice
    assert "restart requires a fresh ready" in notice
    assert len(fake.paste_texts()) == 2

    restarted_sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: clock["t"],
        out=_io.StringIO(),
    )
    restarted_fixture = repo, topic, session, fake, restarted_sup, _track
    _void_stale_ready(
        fixture=restarted_fixture,
        clock=clock,
        mtime=1300.0,
    )
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    repeated = restarted_sup.evaluate(track=_track, act=True)

    assert repeated.status == "warned"
    assert len(_notice_pastes(fake=fake)) == 1
    assert len(fake.paste_texts()) == 2


def test_failed_void_notice_paste_is_retried_within_the_same_round(*, tmp_path):
    clock = {"t": 1000.0}
    fixture = _open_delivered_round(tmp_path=tmp_path, clock=clock)
    repo, topic, session, fake, sup, track = fixture
    _void_stale_ready(
        fixture=fixture,
        clock=clock,
        mtime=1010.0,
    )

    fake.paste_ok = False
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    first = sup.evaluate(track=track, act=True)

    assert first.status == "warned"
    assert len(fake.paste_texts()) == 2
    assert len(_notice_pastes(fake=fake)) == 1
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.void_notice_sent is False

    fake.paste_ok = True
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    second = sup.evaluate(track=track, act=True)

    assert second.status == "warned"
    assert len(fake.paste_texts()) == 3
    assert len(_notice_pastes(fake=fake)) == 2
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.void_notice_sent is True
