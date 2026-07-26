"""Beside-tests for supervisor.py — part 1: daemon-wide warn_percent vs. per-track ctx_threshold ov.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    arm_ready_marker,
    assert_no_tmux_scoping,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Part 1: daemon-wide warn_percent vs. per-track ctx_threshold override.
# --------------------------------------------------------------------------- #


def test_warn_percent_default_applies_to_track_without_override(tmp_path):
    """Supervisor(warn_percent=30): a track with ctx_threshold=None inherits the
    daemon-wide default, so it stays idle at ctx 40 (> 30) and warns at ctx 30."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=40))  # 40 > warn_percent 30
    sup = make_supervisor(tmp_path, fake, warn_percent=30)
    track = mapped_track(repo, topic, session)  # ctx_threshold defaults to None
    assert track.ctx_threshold is None
    view = sup.evaluate(track, act=True)
    # Above the inherited threshold (40 > 30) → a keep-going NUDGE, not a wind-down warn.
    assert view.status == "idle-with-context-left"
    assert wrapup_count(fake) == 0
    # Drop to the daemon-wide threshold → warns (wind-down wrap-up).
    fake.panes[session] = idle_capture(ctx=30)
    view = sup.evaluate(track, act=True)
    assert view.status == "warned"
    assert wrapup_count(fake) == 1


def test_explicit_ctx_threshold_overrides_warn_percent(tmp_path):
    """A per-track ctx_threshold=60 warns at 60 REGARDLESS of the daemon-wide
    warn_percent (30 here): ctx 55 warns even though 55 > 30 would not under the
    daemon default."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=55))
    sup = make_supervisor(tmp_path, fake, warn_percent=30)
    track = registry.Track(
        topic=topic,
        repo=str(repo),
        tmux=session,
        handoff=supervisor.default_handoff(str(repo), topic),
        resume=supervisor.default_resume(str(repo), topic),
        ctx_threshold=60,
    )
    view = sup.evaluate(track, act=True)
    assert view.status == "warned"  # 55 <= 60 override, despite warn_percent 30
    assert fake.has("paste")


def test_claude_launch_command_carries_no_tmux_scoping(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)

    command = supervisor.Supervisor._launch_command(mapped_track(repo, topic, session))

    assert_no_tmux_scoping(command)
    assert command == f"claude --dangerously-skip-permissions -n {topic}"


def test_codex_launch_command_carries_no_tmux_scoping():
    command = supervisor.Supervisor._codex_launch_command(
        "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        "read /tmp/repo/plan/topic/handoff.md and follow it",
    )

    assert_no_tmux_scoping(command)
    assert command.startswith("codex resume --dangerously-bypass-approvals-and-sandbox ")


def test_restart_fires_when_marker_valid_notbusy_idle(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"
    assert (
        "respawn",
        session,
        str(repo),
        f"claude --dangerously-skip-permissions -n {topic}",
    ) in fake.calls
    resume = supervisor.default_resume(str(repo), topic)
    assert resume in fake.paste_texts()
    # the ready marker was deleted AND the injection stamp cleared (round closed, B4)
    assert not marker.exists()
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) is None


def test_no_restart_when_busy_even_with_valid_marker(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture="esc to interrupt\n  Ctx: 30% left\n")  # busy
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert not fake.has("respawn")


# --------------------------------------------------------------------------- #
# Background subshell: a live `Bash(run_in_background)` command shell under the
# pane process ⇒ BUSY, suppressing BOTH injection and restart (never respawn -k
# a session with live background work), even when the pane text looks idle.
# --------------------------------------------------------------------------- #


def test_bg_shell_suppresses_restart(tmp_path):
    """Idle-looking pane + VALID ready marker, but a descendant shell in the
    process tree (a live `Bash(run_in_background)` command) ⇒ status `working`
    and NO respawn: the bg-shell makes it busy, so the atomic restart is
    suppressed and the live background work is protected."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))  # empty box → textually idle
    fake.pane_pid_map[session] = 100  # the pane's login-shell PID
    # 100 → 200 (node runtime) → 300 (node MCP server) + 400 (a bg-command shell).
    children = {100: [200], 200: [300, 400]}
    comms = {200: "node", 300: "node", 400: "zsh"}
    sup = make_supervisor(
        tmp_path,
        fake,
        children_of=lambda pid: children.get(pid, []),
        comm_of=comms.get,
    )
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)  # valid + fresh

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "working"  # bg-shell ⇒ busy ⇒ NOT restarted
    assert view.note == "background shell"  # operator sees WHY it isn't idle
    assert not fake.has("respawn")  # the live background work is protected
    assert marker.exists()  # a fresh marker is untouched by the busy void check


def test_no_bg_shell_allows_restart(tmp_path):
    """The counterpart: identical idle pane + valid ready marker, but NO descendant
    shell (only node/MCP) ⇒ the restart proceeds (`restarting`, respawn issued)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    fake.pane_pid_map[session] = 100
    children = {100: [200], 200: [300]}
    comms = {200: "node", 300: "node"}  # node runtime + MCP server, no shell
    sup = make_supervisor(
        tmp_path,
        fake,
        children_of=lambda pid: children.get(pid, []),
        comm_of=comms.get,
    )
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"
    assert (
        "respawn",
        session,
        str(repo),
        f"claude --dangerously-skip-permissions -n {topic}",
    ) in fake.calls
