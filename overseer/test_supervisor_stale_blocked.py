"""Beside-tests for voiding stale blocked declarations."""

import contextlib
import io as _io

import pytest
import registry
import signals
from test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Voiding a stale `blocked:` declaration. A GENERATING session is, by observation,
# not waiting on a human — so a `blocked:` it has outlived is provably false, and a
# dead reason must not ride a `working` row nor fire a false `blocked:human` alert
# when the session next goes idle. Found live 2026-07-16: a fresh overseer-rewrite
# session rendered `working (awaiting maintainer next-step decision — Codex…)` — the
# PREVIOUS session's declaration, inherited because the pane was replaced out-of-band
# (so `_do_restart`'s `_clear_state` never ran).
# --------------------------------------------------------------------------- #


def test_stale_blocked_is_voided_when_the_session_resumes_generating(*, tmp_path):
    """Past the grace + a real generation spinner ⇒ the declaration is provably dead."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture())  # a real spinner: generating
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    declare(
        repo=repo,
        topic=topic,
        value="blocked: a reason from a session that has moved on",
        mtime=800.0,
    )
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    assert view.note is None  # the dead reason no longer rides the row
    assert signals.read_state(repo=str(repo), topic=topic) is None  # voided


def test_fresh_blocked_survives_the_declaring_turns_own_busy_tail(*, tmp_path):
    """RB1, for `blocked` as for `ready`: the declaring turn's final text keeps streaming
    for 10-60s AFTER the write, so a YOUNG declaration must survive a busy tick — else
    every legitimate declaration is destroyed before the pane ever goes idle."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    declare(
        repo=repo, topic=topic, value="blocked: I need your call", mtime=1001.0
    )  # younger than the grace
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_BLOCKED  # survived


def test_blocked_with_only_a_background_shell_is_never_voided(*, tmp_path):
    """The counter-case that bounds the rule. A session busy ONLY via a live
    `Bash(run_in_background)` command (Claude `shell`) is AT ITS PROMPT — it can be
    genuinely waiting on a human while a build runs, so its declaration is NOT provably
    stale and must survive however old it is. Only GENERATING voids."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))  # no spinner
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}  # busy via a background command only
    declare(
        repo=repo, topic=topic, value="blocked: need your call", mtime=800.0
    )  # old, but NOT stale
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "blocked:human"
    assert view.note == "3m: need your call; background shell"
    assert "blocked on human" in err.getvalue()
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_BLOCKED  # survived
