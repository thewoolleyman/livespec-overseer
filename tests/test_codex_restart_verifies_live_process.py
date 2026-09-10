"""Regression tests for Codex restart post-respawn liveness verification."""

import contextlib
import io as _io

import codex_sessions
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_codex_ready,
    mapped_track,
    on_respawn,
)

__all__: list[str] = []


def test_a_codex_restart_accepts_a_line_wrapped_resume_kick(tmp_path):
    """Rendered wrapping cannot turn a successful exact-session resume into failure."""
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    resume = (
        f"resume plan epic {TEST_EPIC} in repository {repo}; " "read its ledger-held plan state"
    )
    wrapped_resume = resume.replace(" in repository ", " in\nrepository ")
    assert resume not in wrapped_resume
    on_respawn(
        fake=fake,
        after=lambda target: fake.panes.__setitem__(target, wrapped_resume),
    )
    log = _io.StringIO()

    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED
    assert log.getvalue().count(f"restarted (codex) {repo}::{topic}") == 1

    fake.calls.clear()
    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert not fake.has(method="respawn")
    assert log.getvalue().count(f"restarted (codex) {repo}::{topic}") == 1


def test_a_codex_restart_with_no_post_respawn_live_process_is_not_success(tmp_path):
    """A loose Codex-looking foreground command is not enough after respawn."""
    repo, topic, session, _session_id, _fake, sup = adopt_codex_ready(tmp_path=tmp_path)

    def refresh_to_bare_shell() -> None:
        sup.live_codex = {}

    sup._refresh_codex_sessions = refresh_to_bare_shell
    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert signals.read_state(repo=str(repo), topic=topic) is not None
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert "no live Codex process" in log.getvalue()
    assert f"restarted (codex) {repo}::{topic}" not in log.getvalue()


def test_a_codex_restart_requires_post_respawn_live_process_before_success(tmp_path):
    """The success leg refreshes exact live Codex process evidence after respawn."""
    repo, topic, session, session_id, _fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    refreshed = {"called": False}

    def refresh_to_live_codex() -> None:
        refreshed["called"] = True
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=5150, name=topic, cwd=str(repo), session_id=session_id
            )
        }

    sup._refresh_codex_sessions = refresh_to_live_codex
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert refreshed["called"] is True
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED


def test_a_codex_restart_waits_for_delayed_post_respawn_live_process(tmp_path):
    """Codex may register its resumed process after the pane first renders."""
    repo, topic, session, session_id, _fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    refresh_calls = 0

    def refresh_to_delayed_codex() -> None:
        nonlocal refresh_calls
        refresh_calls += 1
        sup.live_codex = {}
        if refresh_calls >= 3:
            sup.live_codex[(session, topic)] = codex_sessions.CodexSession(
                pid=5150, name=topic, cwd=str(repo), session_id=session_id
            )

    sup._refresh_codex_sessions = refresh_to_delayed_codex
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert refresh_calls == 3
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED


def test_a_codex_restart_rejects_a_different_post_respawn_session_id(tmp_path):
    repo, topic, session, _session_id, _fake, sup = adopt_codex_ready(tmp_path=tmp_path)

    def refresh_to_different_codex() -> None:
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=5150,
                name=topic,
                cwd=str(repo),
                session_id="019f548d-6071-7893-9c2e-472cce81da02",
            )
        }

    sup._refresh_codex_sessions = refresh_to_different_codex
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_a_codex_restart_rejects_a_post_respawn_process_outside_the_repo(tmp_path):
    repo, topic, session, session_id, _fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    outside = tmp_path / "other"
    outside.mkdir()

    def refresh_to_wrong_cwd() -> None:
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=5150, name=topic, cwd=str(outside), session_id=session_id
            )
        }

    sup._refresh_codex_sessions = refresh_to_wrong_cwd
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
