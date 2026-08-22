"""Repo-level tests for blocked declaration age-band alerts."""

import contextlib
import io as _io

import registry
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_blocked_alerts_escalate_by_declaration_age_band(*, tmp_path, monkeypatch):
    """The blocked declaration is re-reported once per age band, keyed by mtime."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value="blocked: needs a human", mtime=1000.0)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        ages = (0.0, 60.0, 4 * 3600.0, 4 * 3600.0 + 60.0, 24 * 3600.0, 49 * 3600.0)
        for age in ages:
            clock["t"] = 1000.0 + age
            assert sup.evaluate(track=track, act=True).status == "blocked:human"
    lines = err.getvalue().splitlines()
    labels = [line.split("blocked on human (")[1].split("):")[0] for line in lines]
    assert labels == ["0m", "4h", "24h", "48h"]

    declare(repo=repo, topic=topic, value="blocked: second reason", mtime=clock["t"])
    restarted = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    declare(repo=repo, topic=topic, value="blocked: old reason", mtime=1000.0)
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        assert restarted.evaluate(track=track, act=True).status == "blocked:human"
        assert restarted.evaluate(track=track, act=True).status == "blocked:human"
    lines = err.getvalue().splitlines()
    assert len(lines) == 2
    assert "blocked on human (0m):" in lines[0]
    assert "blocked on human (48h):" in lines[1]
