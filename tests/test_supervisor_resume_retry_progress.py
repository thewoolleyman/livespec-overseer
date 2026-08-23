"""Regression tests for resume retry behavior around progressing panes."""

from __future__ import annotations

import contextlib
import io as _io

import pytest
import registry
import signals
from test_supervisor_builders import (
    arm_ready_marker,
    make_plan,
    make_supervisor,
    mapped_track,
    unsubmitted_resume_capture,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)


def test_pending_resume_on_progressing_pane_closes_without_enter(*, tmp_path) -> None:
    """A resume-pending pane that is already progressing has submitted the resume."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=unsubmitted_resume_capture(ctx=90))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session[session] = "busy"
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    registry.set_resume_pending(
        repo=str(repo),
        topic=topic,
        session_identity=f"claude:{session}:{topic}",
        stamp_path=sup.stamp_path,
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert not any(call[0] == "keys" and call[2] == "Enter" for call in fake.calls)
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )
