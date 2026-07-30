"""Beside-tests for supervisor.py — shell liveness attention."""

import _supervisor_config
import codex_sessions
import pytest
import registry
from test_supervisor_builders import (
    codex_idle_capture,
    idle_capture,
    key_for,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_above_threshold_shell_only_no_progress_surfaces_after_long_floor(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "shell"}
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "working"
    for _ in range(35):
        clock["t"] += 800.0
        assert sup.evaluate(track=track, act=True).status == "working"
    clock["t"] += 801.0
    view = sup.evaluate(track=track, act=True)

    assert view.status == "shell-prolonged"
    assert view.ctx == 73
    assert view.note == "background shell 8h"
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_above_threshold_shell_episode_resets_on_progress_or_idle(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "shell"}
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    sup.claude_status_by_session = {session: "busy"}
    clock["t"] += _supervisor_config.SHELL_PROLONGED_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "working"
    assert sup.inject[key_for(repo=repo, topic=topic)].shell_episode.since is None

    sup.claude_status_by_session = {session: "shell"}
    sup.evaluate(track=track, act=True)
    sup.claude_status_by_session = {session: "idle"}
    clock["t"] += _supervisor_config.SHELL_PROLONGED_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert sup.inject[key_for(repo=repo, topic=topic)].shell_episode.since is None


def test_claude_registry_miss_with_subshell_does_not_accrue_shell_episode(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "bash"}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=lambda *, pid: children.get(pid, []),
        comm_of=lambda *, pid: comms.get(pid),
    )
    track = mapped_track(repo=repo, topic=topic, session=session)

    view = sup.evaluate(track=track, act=True)
    assert view.status == "idle-with-context-left"
    assert sup.inject[key_for(repo=repo, topic=topic)].shell_episode.since is None


def test_codex_registry_miss_with_subshell_still_accrues_shell_episode(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=codex_idle_capture(ctx=73, topic=topic),
        cmd="bun",
    )
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "bash"}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=lambda *, pid: children.get(pid, []),
        comm_of=lambda *, pid: comms.get(pid),
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=321, name=topic, cwd=str(repo), session_id="codex-1"
        )
    }
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "working"
    assert sup.inject[key_for(repo=repo, topic=topic)].shell_episode.since == 1000.0
