"""Regression tests for bounded, identity-scoped resume retry keystrokes."""

import contextlib
import io as _io
import json

import _supervisor_config
import _supervisor_view
import pytest
import registry
import supervisor
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


def _live_identity(*, session: str, topic: str) -> str:
    return f"claude:{session}:{topic}"


def test_submit_retry_is_bounded_to_one_failed_send_loop_per_episode(*, tmp_path):
    """One failed resume-submit belief may send at most ``SUBMIT_MAX_ENTERS`` Enters."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=unsubmitted_resume_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=_live_identity(session=session, topic=topic),
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    registry.set_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    with contextlib.redirect_stderr(_io.StringIO()):
        first = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert first.status == "restarting"
    assert first.note == _supervisor_view.RESUME_PENDING_NOTE
    assert len([c for c in fake.calls if c[0] == "keys" and c[2] == "Enter"]) == (
        _supervisor_config.SUBMIT_MAX_ENTERS
    )

    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        second = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert second.status == "restart-never-worked"
    assert second.note == (
        "resume retry budget exhausted after 1 failed tick "
        f"({_supervisor_config.SUBMIT_MAX_ENTERS} Enter keystrokes); inspect pane"
    )
    assert supervisor.needs_attention(row=second)
    assert not any(c[0] == "keys" for c in fake.calls)
    assert not fake.has(method="respawn")
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


@pytest.mark.parametrize(
    ("stamp_entry", "expected_note"),
    [
        (
            {"resume_pending": True},
            "resume retry refused: round session identity missing",
        ),
        (
            {
                "at": 1000.0,
                "bands": [],
                "resume_pending": True,
                "session_identity": "claude:dead:topic",
            },
            "resume retry refused: round session identity differs from live session",
        ),
    ],
)
def test_pending_resume_without_matching_round_identity_sends_no_enter(
    *, tmp_path, stamp_entry, expected_note
):
    """A resume-pending flag is not an authorization to keystroke an arbitrary successor."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=unsubmitted_resume_capture(ctx=90))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    (tmp_path / "stamps.json").write_text(
        json.dumps({f"{registry.norm(repo=str(repo))}\t{topic}": stamp_entry}),
        encoding="utf-8",
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restart-never-worked"
    assert view.note == expected_note
    assert supervisor.needs_attention(row=view)
    assert not any(c[0] == "keys" for c in fake.calls)
    assert not fake.has(method="respawn")
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
