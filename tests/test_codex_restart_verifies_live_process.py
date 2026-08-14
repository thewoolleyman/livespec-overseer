"""Regression tests for Codex restart post-respawn liveness verification."""

import contextlib
import io as _io

import codex_sessions
import signals
from test_supervisor_builders import adopt_codex_ready, mapped_track

__all__: list[str] = []


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
    assert signals.read_state(repo=str(repo), topic=topic) is None
