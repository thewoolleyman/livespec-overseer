"""Regression coverage for per-track Claude registry freshness."""

from __future__ import annotations

import contextlib
import importlib
import io as _io
from pathlib import Path
from types import SimpleNamespace

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


def test_ready_track_uses_idle_registry_status_written_after_discovery(*, tmp_path):
    """A ready track restarts when its already-joined registry file turns idle."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    ppid = {100: 50}
    starttimes = {100: "pt"}
    fake.pane_pids[50] = session
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="busy")
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid=ppid,
        starttimes=starttimes,
    )
    sup._refresh_claude_status()
    assert sup.claude_status_by_session[session] == "busy"
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity="claude:100:pt:topic",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="idle")

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert view.note is None
    assert fake.has(method="respawn")


def _freshness_sup(*, tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session, topic = "pane", "topic"
    sup = SimpleNamespace(
        claude_identity_by_session={},
        claude_status_by_session={session: "busy"},
        sessions_dir=sessions_dir,
        starttime_of=lambda *, pid: "pt" if pid == 100 else None,
        now=lambda: 17.25,
    )
    return sessions_dir, session, topic, sup


def _assert_unjoined_records(*, freshness, sup, session, topic):
    assert freshness.current_status(sup=sup, session=session, topic=topic) == ("busy", None)
    for identity in ("codex:100:pt:topic", "claude:not-a-pid:pt:topic"):
        sup.claude_identity_by_session[(session, topic)] = identity
        assert freshness.read_joined_registry(sup=sup, session=session, topic=topic) is None


def test_joined_registry_read_is_current_and_fail_soft(*, tmp_path):
    """The evaluation read validates only discovery's already-joined registry record."""
    module_path = (
        Path(__file__).parents[1] / "overseer" / "_supervisor_claude_registry_freshness.py"
    )
    assert module_path.is_file()
    freshness = importlib.import_module("_supervisor_claude_registry_freshness")
    sessions_dir, session, topic, sup = _freshness_sup(tmp_path=tmp_path)

    _assert_unjoined_records(freshness=freshness, sup=sup, session=session, topic=topic)

    sup.claude_identity_by_session[(session, topic)] = "claude:100:pt:topic"
    registry_path = sessions_dir / "100.json"
    registry_path.write_text("not-json", encoding="utf-8")
    unreadable = freshness.read_joined_registry(sup=sup, session=session, topic=topic)
    assert unreadable is not None and unreadable.session is None and unreadable.read_at == 17.25

    registry_path.write_text("[]", encoding="utf-8")
    malformed = freshness.read_joined_registry(sup=sup, session=session, topic=topic)
    assert malformed is not None and malformed.session is None

    write_session(
        sessions_dir=sessions_dir, pid=100, name="renamed", cwd=tmp_path, proc_start="wrong"
    )
    stale = freshness.read_joined_registry(sup=sup, session=session, topic=topic)
    assert stale is not None and stale.session is None

    write_session(sessions_dir=sessions_dir, pid=100, name="renamed", cwd=tmp_path, status="idle")
    current = freshness.read_joined_registry(sup=sup, session=session, topic=topic)
    assert current is not None and current.session is not None
    assert current.session.name == "renamed"
    assert freshness.current_status(sup=sup, session=session, topic=topic) == ("idle", 17.25)
    assert sup.claude_identity_by_session[(session, topic)] == "claude:100:pt:renamed"

    fake = FakeTmux()
    fake.serve(session=session, repo=tmp_path, capture=idle_capture(ctx=30))
    sup.tmux = fake
    sup.claude_names_by_session = {session: {topic}}
    observe = importlib.import_module("_supervisor_observe")
    assert not observe.pane_is_managed_claude(
        sup=sup, target=session, repo=str(tmp_path), topic=topic, session=session
    )


def test_status_never_falls_back_to_the_cycle_start_snapshot_for_a_joined_session(*, tmp_path):
    """A joined session whose registry file is unreadable yields no self-report."""
    freshness = importlib.import_module("_supervisor_claude_registry_freshness")
    sessions_dir, session, topic, sup = _freshness_sup(tmp_path=tmp_path)
    sup.claude_identity_by_session[(session, topic)] = "claude:100:pt:topic"

    assert freshness.current_status(sup=sup, session=session, topic=topic) == (None, 17.25)
    (sessions_dir / "100.json").write_text("not-json", encoding="utf-8")
    assert freshness.current_status(sup=sup, session=session, topic=topic) == (None, 17.25)

    sup.claude_identity_by_session.clear()
    sup.claude_identity_by_session[(session, "other")] = "claude:100:pt:other"
    write_session(sessions_dir=sessions_dir, pid=100, name="other", cwd=tmp_path, status="idle")
    assert freshness.current_status(sup=sup, session=session, topic=topic) == ("idle", 17.25)
    assert sup.claude_identity_by_session == {(session, "other"): "claude:100:pt:other"}
