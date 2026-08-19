"""Regression coverage for foreman ready certification at the restart boundary."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "overseer"))

import pytest
import registry
import signals
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_foreman_ready_without_epic_is_surfaced_without_respawn(*, tmp_path, monkeypatch):
    """A foreman declaration with no resolvable epic is surfaced, not respawned."""
    repo, _topic = make_plan(tmp_path=tmp_path)
    topic = "repo-foreman"
    session = topic
    epic_lookups: list[tuple[str, str]] = []

    def fake_epic_lookup(*, repo, topic):
        epic_lookups.append((str(repo), topic))

    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.epic_lookup = fake_epic_lookup
    monkeypatch.setattr(
        registry,
        "epic_from_plan_anchor",
        lambda *, repo, topic: pytest.fail("test escaped to the real registry epic lookup"),
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    declare(repo=repo, topic=topic, value="ready", mtime=1001.0)
    track = registry.ForemanSeat(
        topic=topic,
        repo=str(repo),
        tmux=session,
        epic=registry.unresolved_plan_epic(topic=topic),
    )

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "blocked:human"
    assert view.note == "ready cannot respawn: no foreman epic recorded"
    assert "ready cannot respawn: no foreman epic recorded" in err.getvalue()
    assert epic_lookups == [(str(repo), topic)]
    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic) is not None
