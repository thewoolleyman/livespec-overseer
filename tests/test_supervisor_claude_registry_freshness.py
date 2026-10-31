"""Regression coverage for per-track Claude registry freshness."""

import contextlib
import io as _io

import _supervisor_discovery
import pytest
import registry
from test_supervisor_builders import (
    adopt_sup,
    arm_ready_marker,
    idle_capture,
    make_plan,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_evaluate_rereads_claude_registry_after_cycle_snapshot(*, tmp_path):
    """A ready session that went idle after discovery restarts in this same cycle."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = "sA"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="busy")
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    fake.pane_pids[50] = session
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 50},
        starttimes={100: "pt"},
        now=lambda: 1002.0,
    )
    sup._refresh_claude_status()
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"claude:100:pt:{topic}",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="idle")

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert fake.has(method="respawn")


def test_fresh_registry_read_fails_soft_when_its_pid_leaves_the_join(*, tmp_path):
    """A PID that no longer joins to this pane clears its stale registry gates."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = "sA"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="busy")
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    fake.pane_pids[50] = session
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 50},
        starttimes={100: "pt"},
    )
    sup._refresh_claude_status()
    sup.claude_pane_pid_to_session = {50: "other"}

    _supervisor_discovery.refresh_claude_track(sup=sup, session=session, topic=topic)

    assert session not in sup.claude_status_by_session
    assert (session, topic) not in sup.claude_identity_by_session


def test_fresh_registry_read_restores_a_missing_name_index(*, tmp_path):
    """A current registry read recreates its name index if a stale one vanished."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = "sA"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="busy")
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    fake.pane_pids[50] = session
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 50},
        starttimes={100: "pt"},
    )
    sup._refresh_claude_status()
    _ = sup.claude_names_by_session.pop(session)

    _supervisor_discovery.refresh_claude_track(sup=sup, session=session, topic=topic)

    assert sup.claude_names_by_session[session] == {topic}


class _FlipsRegistryAfterTargetResolution(FakeTmux):
    """Writes the idle registry status once the identity gate has read the pane."""

    def __init__(self, *, flip):
        super().__init__()
        self._flip = flip

    def pane_current_path(self, *, session):
        result = super().pane_current_path(session=session)
        self._flip()
        return result


def test_status_flip_between_target_resolution_and_capture_is_observed(*, tmp_path):
    """An idle write landing after target resolution is read before the row is judged."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = "sA"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="busy")
    fake = _FlipsRegistryAfterTargetResolution(
        flip=lambda: write_session(
            sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="idle"
        )
    )
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    fake.pane_pids[50] = session
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 50},
        starttimes={100: "pt"},
        now=lambda: 1002.0,
    )
    sup._refresh_claude_status()
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"claude:100:pt:{topic}",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert fake.has(method="respawn")
