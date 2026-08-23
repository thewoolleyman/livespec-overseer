"""Regression coverage for stale blocked declarations retaining their reason."""

import contextlib
import io as _io

import pytest
import registry
import signals
from test_supervisor_builders import (
    busy_capture,
    declare,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_stale_blocked_void_preserves_reason_in_state_and_row(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture())
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    reason = "stopped by maintainer; do not resume until told otherwise"
    declare(repo=repo, topic=topic, value=f"blocked: {reason}", mtime=800.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert view.note is not None
    assert reason in view.note
    assert "voided" in view.note
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_BLOCKED_VOIDED
    assert reason in state.detail
    assert "voided" in state.detail


def test_stale_blocked_void_control_detects_discarded_reason(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    reason = "stopped by maintainer; do not resume"
    declare(
        repo=repo,
        topic=topic,
        value=(
            "blocked-voided: session resumed generating after 18917s; "
            "stale blocked declaration voided"
        ),
        mtime=800.0,
    )

    state = signals.read_state(repo=str(repo), topic=topic)

    assert state is not None and state.token == signals.STATE_BLOCKED_VOIDED
    assert reason not in state.detail


def test_stopped_session_answering_peer_message_does_not_void_blocked(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture())
    fake.input_provenance[session] = {
        "peer_injected": True,
        "sending_seat": "livespec-peer",
        "target_session": session,
        "delivery": "bracketed-paste",
        "recorded_at": "2026-08-23T00:00:00Z",
    }
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    reason = "stopped by maintainer; do not resume until told otherwise"
    declare(repo=repo, topic=topic, value=f"blocked: {reason}", mtime=800.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert view.note is not None and reason in view.note
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_BLOCKED
    assert state.detail == reason
