"""Repo-level pairing coverage for stale declarations suppressing idle nudges."""

import contextlib
import io as _io

import _supervisor_config
import pytest
import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.mark.parametrize(
    ("stale_declaration", "expected_status"),
    [
        (signals.STATE_WINDING_DOWN, "idle"),
        (signals.STATE_READY, "ready-uncertifiable"),
    ],
)
def test_standing_stale_session_declaration_is_not_idle_nudge_absence(
    *, tmp_path, monkeypatch, stale_declaration, expected_status
):
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path, topic=stale_declaration)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    declare(repo=repo, topic=topic, value=stale_declaration, mtime=1.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.evaluate(track=track, act=True)
        clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
        view = sup.evaluate(track=track, act=True)

    assert view.status == expected_status
    assert nudge_count(fake=fake) == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == stale_declaration
