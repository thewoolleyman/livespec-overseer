"""Beside-tests for supervisor.py — background subshell live.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import codex_sessions
import pytest
import registry
from test_supervisor_builders import (
    busy_capture,
    codex_idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_bg_shell_at_danger_is_warned_and_never_restarted(*, tmp_path):
    """A session deep in the danger band whose pane LOOKS idle, but which has a live
    background shell (a `Bash(run_in_background)` build/test still running), may receive
    the guarded wrap-up, but still never restarts. The pane text is indistinguishable
    from idle, so `ready` remains the only kill authorization."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=13, topic=topic), cmd="bun"
    )  # idle-LOOKING, deep in danger
    fake.pane_pid_map[session] = 100
    children = {100: [200], 200: [300]}
    comms = {200: "node", 300: "bash"}  # a LIVE background shell under the pane process
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
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "danger"
    assert not fake.has(method="respawn")  # the live background work was NOT killed


def test_bg_shell_sets_background_shell_note(*, tmp_path):
    """When a bg shell is the SOLE reason a pane isn't idle (pane text is idle, no
    blocked marker), the `working` row carries the note `background shell`."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=73, topic=topic), cmd="bun"
    )  # idle, high ctx (no inject)
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "bash"}  # a bg-command shell directly under the pane process
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
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    assert view.note == "background shell"


def test_codex_startup_mcp_launch_chain_can_reach_threshold_handling(*, tmp_path):
    """A session-lifetime MCP wrapper chain belongs to Codex startup, not task work.
    The fallback process walk must not starve threshold handling just because that
    long-lived launch chain remains alive."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40, topic=topic), cmd="bun"
    )
    fake.pane_pid_map[session] = 100
    children = {100: [200], 200: [300], 300: [400], 400: [500], 500: [600]}
    comms = {200: "codex", 300: "sh", 400: "op", 500: "bash", 600: "node"}
    starttimes = {200: "1000", 300: "1001", 400: "1002", 500: "1003", 600: "1004"}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=lambda *, pid: children.get(pid, []),
        comm_of=lambda *, pid: comms.get(pid),
        starttime_of=lambda *, pid: starttimes.get(pid),
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=321, name=topic, cwd=str(repo), session_id="codex-1"
        )
    }
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "warned"
    assert view.note is None
    assert fake.has(method="paste")


def test_textually_busy_pane_has_no_background_shell_note(*, tmp_path):
    """The note is `background shell` ONLY when a bg shell is the SOLE reason. A
    TEXTUALLY busy pane (spinner) is `working` with NO note, even when a descendant
    shell is also present — the note guard is `bg_shell and not is_busy(capture)`."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))  # actively generating
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "zsh"}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=lambda *, pid: children.get(pid, []),
        comm_of=lambda *, pid: comms.get(pid),
    )
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    assert view.note is None
