"""Regression coverage for the daemon's resume retry keystroke budget."""

import contextlib
import io as _io

import _supervisor_config
import _supervisor_launch
import pytest
import registry
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
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _enter_count(*, fake: FakeTmux) -> int:
    return len([call for call in fake.calls if call[0] == "keys" and call[2] == "Enter"])


def test_submit_retry_has_an_episode_keystroke_budget(*, tmp_path, monkeypatch):
    """A stranded resume may be retried, but one pending episode cannot send Enter forever."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=unsubmitted_resume_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
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
    requested_budgets: list[int] = []
    original = _supervisor_launch.resend_enter_budgeted

    def resend_enter_budgeted_spy(*, sup, target: str, max_enters: int):
        requested_budgets.append(max_enters)
        return original(sup=sup, target=target, max_enters=max_enters)

    monkeypatch.setattr(_supervisor_launch, "resend_enter_budgeted", resend_enter_budgeted_spy)

    for _ in range(12):
        with contextlib.redirect_stderr(_io.StringIO()):
            view = sup.evaluate(
                track=mapped_track(repo=repo, topic=topic, session=session), act=True
            )
        assert view.status == "restarting"

    assert _enter_count(fake=fake) == _supervisor_config.SUBMIT_MAX_ENTERS
    assert requested_budgets == [1] * _supervisor_config.SUBMIT_MAX_ENTERS
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )


def test_fresh_resume_pending_episode_gets_a_fresh_keystroke_budget(*, tmp_path):
    """The budget is scoped to the resume-pending episode, not inherited by the track."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=unsubmitted_resume_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
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

    for _ in range(12):
        with contextlib.redirect_stderr(_io.StringIO()):
            sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert _enter_count(fake=fake) == _supervisor_config.SUBMIT_MAX_ENTERS

    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=2000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=2001.0)
    registry.set_resume_pending(
        repo=str(repo),
        topic=topic,
        session_identity=f"claude:{session}:{topic}",
        stamp_path=sup.stamp_path,
    )
    fake.calls.clear()

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert _enter_count(fake=fake) == 1
