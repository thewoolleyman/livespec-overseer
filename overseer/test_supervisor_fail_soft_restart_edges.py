"""Beside-tests for supervisor.py — fail soft marker.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_sup,
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    on_respawn,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_pane_that_vanishes_mid_tick_is_session_gone_and_never_acted_on(*, tmp_path):
    """RB3: the mapped session passes `session_exists` but dies before its pane id is
    resolved. With no pane id there is nothing safe to target — a bare `-t <name>` could
    fall back to a live SIBLING session and `respawn-pane -k` could kill IT — so the row
    degrades to `session-gone` and no pane op runs, even on a valid `ready`."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()  # no live Claude for the topic outside tmux either
    sup = adopt_sup(tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={})
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    exists = fake.session_exists

    def vanishing_exists(*, session):
        answer = exists(session=session)
        fake.sessions.discard(session)  # the pane dies right after we looked
        return answer

    fake.session_exists = vanishing_exists

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "session-gone"
    assert view.tmux is None  # never name a session that is not there
    assert not fake.has(method="respawn")  # nothing was targeted...
    assert not fake.has(method="paste")
    assert marker.exists()  # ...and the declaration survives for a later tick


def test_restart_keeps_the_marker_when_the_respawned_pane_never_becomes_claude(*, tmp_path):
    """B5: the respawn SUCCEEDS but the pane comes up as a bare shell (the launch died
    immediately). The round must NOT be closed — the daemon alerts and keeps the `ready`
    declaration + stamp so the restart retries, rather than reporting a launch it could
    not verify. The Claude twin of the Codex `never becomes codex` guard."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    on_respawn(fake=fake, after=lambda s: fake.cmds.__setitem__(s, "zsh"))  # comes up a shell
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert "respawned pane never became Claude" in err.getvalue()
    assert session in err.getvalue()  # the alert names where to go
    assert marker.exists()  # declaration preserved for the retry
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )
    assert supervisor.plan_epic_resume(repo=str(repo), epic=TEST_EPIC) not in fake.paste_texts()


def test_freshly_restarted_pane_on_a_gate_pends_the_resume_instead_of_keystroking_it(*, tmp_path):
    """Blocker #6: the fresh Claude came up on a trust/update/permissions PICKER. Pasting
    the resume line + Enter there would auto-accept the picker's default, so the daemon
    keystrokes NOTHING: it records a round-scoped `resume_pending`, alerts, and leaves the
    `ready` marker in place for the next tick to retry once the human clears the gate."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    gate = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    on_respawn(
        fake=fake, after=lambda s: fake.panes.__setitem__(s, gate)
    )  # fresh TUI opens on a gate
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert "freshly-restarted pane is on a gate" in err.getvalue()
    assert not fake.has(method="paste")  # NEVER keystroked the picker
    assert not any(c[0] == "keys" for c in fake.calls)
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )
    assert marker.exists()  # round left open for the retry
