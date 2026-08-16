"""Integration edge coverage for ready activity after the retired void notice."""

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


def test_void_notice_in_the_danger_band_keeps_danger_attention(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=18))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    opened = sup.evaluate(track=track, act=True)
    assert opened.status == "danger"

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
    clock["t"] = 1190.0
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=18))
    assert sup.evaluate(track=track, act=True).status == "working"

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=18))
    noticed = sup.evaluate(track=track, act=True)

    assert noticed.status == "restarting"
