"""Beside-tests for supervisor.py — warned stamp written.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

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
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize(
    "stale_declaration",
    [
        signals.STATE_WINDING_DOWN,
        signals.STATE_READY,
    ],
)
def test_session_cleared_stale_wind_down_declaration_re_enters_nudge_path(
    *, tmp_path, stale_declaration
):
    """Once v019's session-side expiry clears the stale token, the daemon sees no
    session declaration and the next long idle-above-threshold episode is nudged."""
    repo, topic = make_plan(tmp_path=tmp_path, repo_name="cleared", topic=stale_declaration)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    state_path = declare(repo=repo, topic=topic, value=stale_declaration, mtime=1.0)

    state_path.unlink()
    track = mapped_track(repo=repo, topic=topic, session=session)
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT


@pytest.mark.parametrize(
    ("stale_declaration", "uncleared_status"),
    [
        (signals.STATE_WINDING_DOWN, "idle"),
        (signals.STATE_READY, "ready-uncertifiable"),
    ],
)
def test_uncleared_stale_wind_down_declaration_suppresses_nudge(
    *, tmp_path, stale_declaration, uncleared_status
):
    """A stale declaration the session has not cleared is still standing state. The
    daemon deliberately does not reinterpret it as absent or auto-clear it."""
    repo, topic = make_plan(tmp_path=tmp_path, repo_name="uncleared", topic=stale_declaration)
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

    assert view.status == uncleared_status
    assert nudge_count(fake=fake) == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == stale_declaration
