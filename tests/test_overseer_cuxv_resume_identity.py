"""Regression tests for resume-pending session identity safety."""

import contextlib
import importlib
import io as _io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERSEER = ROOT / "overseer"
if str(OVERSEER) not in sys.path:
    sys.path.insert(0, str(OVERSEER))

__all__: list[str] = []


def _stamp_key(*, repo: str, topic: str) -> str:
    return f"{repo}\t{topic}"


def _helpers():
    registry = importlib.import_module("registry")
    builders = importlib.import_module("test_supervisor_builders")
    fakes = importlib.import_module("test_supervisor_fakes")
    return registry, builders, fakes


def test_submit_retry_refuses_a_pending_identity_mismatch(*, tmp_path, monkeypatch):
    registry, builders, fakes = _helpers()
    monkeypatch.chdir(tmp_path)
    repo, topic = builders.make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = fakes.FakeTmux()
    fake.serve(session=session, repo=repo, capture=builders.unsubmitted_resume_capture(ctx=30))
    sup = builders.make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.stamp_path).write_text(
        json.dumps(
            {
                _stamp_key(repo=str(repo), topic=topic): {
                    "at": 1000.0,
                    "session_identity": f"claude:{session}:{topic}",
                    "resume_pending": True,
                    "resume_pending_session_identity": "claude:old-session:topic",
                }
            }
        ),
        encoding="utf-8",
    )
    builders.arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(
            track=builders.mapped_track(repo=repo, topic=topic, session=session), act=True
        )

    assert view.status == "blocked:human"
    assert not fake.has(method="respawn")
    assert not any(c[0] == "keys" and c[2] == "Enter" for c in fake.calls)
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )


def test_submit_retry_refuses_a_bare_pending_flag_without_identity(*, tmp_path, monkeypatch):
    registry, builders, fakes = _helpers()
    monkeypatch.chdir(tmp_path)
    repo, topic = builders.make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = fakes.FakeTmux()
    fake.serve(session=session, repo=repo, capture=builders.unsubmitted_resume_capture(ctx=30))
    sup = builders.make_supervisor(tmp_path=tmp_path, fake=fake)
    Path(sup.stamp_path).write_text(
        json.dumps({_stamp_key(repo=str(repo), topic=topic): {"resume_pending": True}}),
        encoding="utf-8",
    )
    builders.arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(
            track=builders.mapped_track(repo=repo, topic=topic, session=session), act=True
        )

    assert view.status == "blocked:human"
    assert not fake.has(method="respawn")
    assert not any(c[0] == "keys" and c[2] == "Enter" for c in fake.calls)
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )


def test_submit_retry_sends_enter_when_live_identity_matches_pending_identity(
    *, tmp_path, monkeypatch
):
    registry, builders, fakes = _helpers()
    monkeypatch.chdir(tmp_path)
    repo, topic = builders.make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    live_identity = f"claude:123:456:{topic}"
    fake = fakes.FakeTmux()
    fake.serve(session=session, repo=repo, capture=builders.unsubmitted_resume_capture(ctx=30))
    sup = builders.make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_identity_by_session[(session, topic)] = live_identity
    Path(sup.stamp_path).write_text(
        json.dumps(
            {
                _stamp_key(repo=str(repo), topic=topic): {
                    "at": 1000.0,
                    "session_identity": live_identity,
                    "resume_pending": True,
                    "resume_pending_session_identity": live_identity,
                }
            }
        ),
        encoding="utf-8",
    )
    builders.arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(
            track=builders.mapped_track(repo=repo, topic=topic, session=session), act=True
        )

    assert view.status == "restarting"
    assert not fake.has(method="respawn")
    assert any(c[0] == "keys" and c[2] == "Enter" for c in fake.calls)
