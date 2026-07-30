"""Beside-tests for supervisor.py — auto link repo.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import os

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    adopt_sup,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
    row_line,
    write_session,
)
from test_supervisor_fakes import (
    FakeTmux,
    TtyOut,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_auto_link_creates_mapping_when_cwd_in_repo(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.sessions.add(session)
    fake.paths[session] = str(repo / "plan" / topic)  # cwd inside the repo
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])

    unassigned = registry.Track.make_unassigned(repo=str(repo), topic=topic)
    linked = sup.auto_link(track=unassigned)
    assert linked is not None
    assert linked.tmux == session
    rows = registry.read_mapping(store_path=sup.store_path)
    assert [(r.repo, r.topic) for r in rows] == [(os.path.normpath(str(repo)), topic)]


# --------------------------------------------------------------------------- #
# live-outside-tmux: the mapped tmux session is gone, but a live Claude session
# for the topic is running in a NON-tmux terminal (e.g. a bare SSH shell) — alive
# and working but unmanageable, so NOT the alarming `session-gone`.
# --------------------------------------------------------------------------- #


def test_missing_session_with_live_out_of_tmux_claude_is_live_outside_tmux(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # mapped tmux session NOT added → session_exists False; no panes
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    # A live registry session named for the topic, cwd in the repo, whose pid walks up
    # to NO tmux pane (pane_pids empty, ppid chain terminates) → running outside tmux.
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=str(repo), status="busy")
    sup = adopt_sup(
        tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={100: "pt"}
    )
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "live-outside-tmux"
    assert view.note is not None
    assert "OUTSIDE tmux" in view.note
    assert "busy" in view.note  # the session's own self-reported status is surfaced
    assert not fake.has(method="capture")  # there is no pane to read


def test_missing_session_without_any_live_claude_is_still_session_gone(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    # A live registry session exists, but for a DIFFERENT topic — this track is gone.
    write_session(
        sessions_dir=sessions_dir, pid=100, name="some-other-topic", cwd=str(repo), status="busy"
    )
    sup = adopt_sup(
        tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={100: "pt"}
    )
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "session-gone"


def test_missing_session_with_the_claude_in_a_different_tmux_is_session_gone(*, tmp_path):
    """A live session for the topic that DOES resolve to a tmux session is a re-mapping
    concern, not out-of-tmux — it stays `session-gone` (this fix is scoped to no-tmux)."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # the mapped `session` is gone...
    fake.pane_pids = {4242: "some-other-tmux"}  # ...but the claude pid resolves to a live pane
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=str(repo), status="busy")
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 4242},
        starttimes={100: "pt"},
    )
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "session-gone"


def test_live_outside_tmux_is_not_an_attention_status():
    """It is informational — the work is fine, just unmanageable — so it must NOT land
    in the NEEDS YOU block."""
    view = supervisor.RowView(
        topic="t",
        repo="/r",
        tmux="s",
        ctx=None,
        status="live-outside-tmux",
        note="live Claude session (pid 100) running OUTSIDE tmux — daemon cannot manage it",
    )
    assert supervisor.needs_attention(row=view) is False
    assert "live-outside-tmux" not in supervisor.ATTENTION_STATUSES


def test_tty_render_leaves_live_outside_tmux_uncolored(*, tmp_path):
    """`live-outside-tmux` is informational, not an alarm — it keeps the terminal
    default color (never red like `session-gone`)."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), out=TtyOut())
    view = supervisor.RowView(topic="lo", repo="/r", tmux="s", ctx=None, status="live-outside-tmux")
    line = row_line(out=render_of(sup=sup, views=[view]), topic="lo")
    assert "\x1b[3" not in line  # no SGR color introducer at all


# --------------------------------------------------------------------------- #
# Claude registry `status` is the AUTHORITATIVE busy signal for an adopted
# Claude session (2026-07-15). Its vocabulary maps cleanly: `busy` (generating /
# in-process sub-agent) and `shell` (live `Bash(run_in_background)`) mean working;
# `idle` / `waiting` (at a prompt) mean not-working. For an adopted session the
# process-tree shell-walk is IGNORED — `status` sees sub-agents the walk missed
# (false-idle) and its `shell` value is a more accurate background-work signal than
# the walk, which false-fired on lingering/transient shells (false-working). The
# walk stays ONLY the runtime-agnostic FALLBACK for a session with no registry
# entry (Codex).
# --------------------------------------------------------------------------- #


def test_registry_busy_marks_working_despite_idle_pane(*, tmp_path):
    """A session running an in-process sub-agent looks idle — no spinner, no descendant
    shell — but Claude reports itself `busy`. That self-report must mark it `working`."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=73)
    )  # pane looks idle, high ctx
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "busy"}  # Claude's own live self-report
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    assert view.note == "sub-agent (Claude busy)"


def test_registry_shell_marks_working_with_background_shell_note(*, tmp_path):
    """Claude reports `shell` when a live `Bash(run_in_background)` command is running while
    the pane sits at the prompt — the daemon must show `working (background shell)`, so a
    real background dispatch is never mis-read as idle."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))  # pane at the prompt
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}  # Claude: a live background command
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    assert view.note == "background shell"


def test_adopted_claude_ignores_the_process_tree_shell_walk(*, tmp_path):
    """For an adopted Claude session the registry `status` is authoritative and the
    process-tree shell-walk is IGNORED: a lingering `sleep`/poll shell must not mask an
    at-prompt (`waiting`) session as working — the false-positive `working (background
    shell)` bug. (Claude would report `shell`, not `waiting`, if the shell were live work.)"""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))  # idle pane, high ctx
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "zsh"}  # a descendant shell the process-walk would flag
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=lambda *, pid: children.get(pid, []),
        comm_of=lambda *, pid: comms.get(pid),
    )
    sup.claude_status_by_session = {session: "waiting"}  # Claude: at a user prompt, not working
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "idle"  # NOT "working" — the process-walk is ignored for Claude
    assert view.note is None


def test_claude_registry_miss_does_not_fall_back_to_process_shell_walk(*, tmp_path):
    """A Claude-shaped session with a momentarily missing registry entry does not accrue
    a false background-shell episode from the process-tree fallback."""
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
    sup.claude_status_by_session = {}
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "idle-with-context-left"
    assert view.note is None


def test_registry_idle_is_idle_even_with_a_stray_descendant_shell(*, tmp_path):
    """`idle` (nothing pending) is not working; the process-walk is ignored for an adopted
    Claude session, so a stray descendant shell cannot flip it to working."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    fake.pane_pid_map[session] = 100
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=lambda *, pid: {100: [200]}.get(pid, []),
        comm_of=lambda *, pid: {200: "bash"}.get(pid),
    )
    sup.claude_status_by_session = {session: "idle"}
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    # Not "working" — the process-walk is ignored for Claude. (Idle above threshold with
    # no declaration is now nudged to keep going: `idle-with-context-left`, still not busy.)
    assert view.status == "idle-with-context-left"
    assert view.note is None
