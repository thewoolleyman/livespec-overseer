"""Integration edge coverage for the bounded expiry-notice."""

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


def _round_at(*, tmp_path, clock, ctx):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    return repo, topic, session, fake, sup, track


def _notices(*, fake: FakeTmux) -> list[str]:
    return [text for text in fake.paste_texts() if "EXPIRED" in text]


def test_expiry_notice_in_the_danger_band_keeps_danger_attention(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track = _round_at(tmp_path=tmp_path, clock=clock, ctx=18)

    assert sup.evaluate(track=track, act=True).status == "danger"

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1010.0 + MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)
    clock["t"] += 1.0
    noticed = sup.evaluate(track=track, act=True)

    assert noticed.status == "danger"
    assert len(_notices(fake=fake)) == 1


def test_a_round_closed_as_recovered_before_the_notice_lands_sends_none(*, tmp_path):
    """The notice is scoped to a round that is still open. A round whose context
    recovered above the threshold closes as recovered first, and the fresh round's own
    wrap-up re-teaches the protocol instead."""
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track = _round_at(tmp_path=tmp_path, clock=clock, ctx=40)

    assert sup.evaluate(track=track, act=True).status == "warned"

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1010.0 + MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))
    clock["t"] += 1.0
    sup.evaluate(track=track, act=True)

    assert _notices(fake=fake) == []
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )


def test_a_failed_notice_paste_leaves_the_notice_due_within_the_same_round(*, tmp_path):
    """A failed paste never un-opens the round and never consumes the single-notice
    bound: the notice is simply retried on a later observation."""
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track = _round_at(tmp_path=tmp_path, clock=clock, ctx=40)

    assert sup.evaluate(track=track, act=True).status == "warned"

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1010.0 + MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)

    fake.paste_ok = False
    clock["t"] += 1.0
    sup.evaluate(track=track, act=True)

    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert not record.expiry_notice_sent
    assert record.at == 1000.0

    fake.paste_ok = True
    clock["t"] += 1.0
    sup.evaluate(track=track, act=True)

    assert registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=sup.stamp_path
    ).expiry_notice_sent


def test_a_busy_pane_defers_the_notice_to_a_later_observation(*, tmp_path):
    """The notice is subject to the complete guarded-paste predicate, so a pane that is
    not a verified settled-idle prompt is never pasted into."""
    clock = {"t": 1000.0}
    repo, topic, session, fake, sup, track = _round_at(tmp_path=tmp_path, clock=clock, ctx=40)

    assert sup.evaluate(track=track, act=True).status == "warned"

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1010.0 + MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)

    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))
    clock["t"] += 1.0
    assert sup.evaluate(track=track, act=True).status == "working"
    assert _notices(fake=fake) == []

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock["t"] += 1.0
    sup.evaluate(track=track, act=True)

    assert len(_notices(fake=fake)) == 1
