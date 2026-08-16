"""Integration-tier scenario tests for ready activity after the retired void notice.

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


def _ready_then_busy(*, fixture, clock, mtime):
    repo, topic, session, fake, sup, track = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)
    clock["t"] = mtime + 180.0
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))

    voided = sup.evaluate(track=track, act=True)

    assert voided.status == "working"
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_scenario_a_ready_declaration_is_not_answered_with_a_void_notice(*, tmp_path):
    """A ready declaration that sees more output remains armed and later restarts."""
    clock = {"t": 1000.0}
    fixture = _open_delivered_round(tmp_path=tmp_path, clock=clock)
    repo, topic, session, fake, _sup, _track = fixture
    _ready_then_busy(
        fixture=fixture,
        clock=clock,
        mtime=1010.0,
    )

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    restarted = _sup.evaluate(track=_track, act=True)

    assert restarted.status == "restarting"
    assert len(fake.paste_texts()) == 2


def test_failed_ordinary_paste_does_not_create_a_void_notice_retry(*, tmp_path):
    clock = {"t": 1000.0}
    fixture = _open_delivered_round(tmp_path=tmp_path, clock=clock)
    repo, topic, session, fake, sup, track = fixture
    _ready_then_busy(
        fixture=fixture,
        clock=clock,
        mtime=1010.0,
    )

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    first = sup.evaluate(track=track, act=True)

    assert first.status == "restarting"
    assert len(fake.paste_texts()) == 2
