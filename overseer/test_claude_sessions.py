"""Tests for Claude session-registry to tmux PID joins."""

import json

import claude_sessions

__all__: list[str] = []


def _write(*, directory, pid, name, cwd, proc_start, status="idle"):
    payload = {"pid": pid, "name": name, "cwd": cwd, "procStart": proc_start, "status": status}
    (directory / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_tmux_session_walks_parent_chain():
    # claude 100 → shell 50 (a pane PID of session "s") → init.
    ppid = {100: 50, 50: 1}
    got = claude_sessions.resolve_tmux_session(
        pid=100, pane_pid_to_session={50: "s"}, ppid_of=lambda *, pid: ppid.get(pid)
    )
    assert got == "s"


def test_resolve_tmux_session_pid_is_the_pane_itself():
    got = claude_sessions.resolve_tmux_session(
        pid=50, pane_pid_to_session={50: "s"}, ppid_of=lambda *, pid: None
    )
    assert got == "s"


def test_resolve_tmux_session_none_when_not_in_tmux():
    ppid = {100: 50, 50: 1, 1: 0}
    got = claude_sessions.resolve_tmux_session(
        pid=100, pane_pid_to_session={999: "other"}, ppid_of=lambda *, pid: ppid.get(pid)
    )
    assert got is None


def test_resolve_tmux_session_cycle_is_fail_soft():
    ppid = {100: 200, 200: 100}  # a cycle, and neither is a pane PID
    got = claude_sessions.resolve_tmux_session(
        pid=100, pane_pid_to_session={}, ppid_of=lambda *, pid: ppid.get(pid)
    )
    assert got is None


def test_map_named_sessions_joins_only_live_in_tmux(*, tmp_path):
    _write(
        directory=tmp_path, pid=100, name="alpha", cwd="/r/a", proc_start="111"
    )  # live, in tmux sA
    _write(
        directory=tmp_path, pid=300, name="gamma", cwd="/r/c", proc_start="333"
    )  # live, NOT in tmux
    _write(directory=tmp_path, pid=400, name="delta", cwd="/r/d", proc_start="444")  # dead
    starttimes = {100: "111", 300: "333"}  # 400 absent → dead
    ppid = {100: 50, 50: 1, 300: 60, 60: 1}
    pane_pid_to_session = {50: "sA"}  # only 100's chain reaches a pane PID

    mapped = claude_sessions.map_named_sessions(
        sessions_dir=tmp_path,
        pane_pid_to_session=pane_pid_to_session,
        ppid_of=lambda *, pid: ppid.get(pid),
        starttime_of=lambda *, pid: starttimes.get(pid),
    )
    assert mapped == [("sA", "alpha", "/r/a")]


def test_status_by_tmux_session_keys_status_by_tmux(*, tmp_path):
    _write(directory=tmp_path, pid=100, name="alpha", cwd="/r/a", proc_start="111", status="busy")
    _write(
        directory=tmp_path, pid=300, name="gamma", cwd="/r/c", proc_start="333", status="busy"
    )  # not in tmux
    starttimes = {100: "111", 300: "333"}
    ppid = {100: 50, 50: 1, 300: 60, 60: 1}
    pane_pid_to_session = {50: "sA"}  # only 100's chain reaches a pane PID

    status = claude_sessions.status_by_tmux_session(
        sessions_dir=tmp_path,
        pane_pid_to_session=pane_pid_to_session,
        ppid_of=lambda *, pid: ppid.get(pid),
        starttime_of=lambda *, pid: starttimes.get(pid),
    )
    assert status == {"sA": "busy"}  # gamma omitted (not held in any tmux pane)


def test_names_by_tmux_session_collects_all_names_per_tmux(*, tmp_path):
    """R2/SF5: the identity gate needs the SET of all live Claude names in a tmux session, so
    a HELPER Claude sharing the session cannot shadow the track's own name (a last-wins single
    would). Two live sessions in one tmux → both names; an out-of-tmux session is omitted."""
    _write(directory=tmp_path, pid=100, name="alpha", cwd="/r/a", proc_start="111")
    _write(
        directory=tmp_path, pid=200, name="helper", cwd="/r/a", proc_start="222"
    )  # a second Claude in sA
    _write(directory=tmp_path, pid=300, name="gamma", cwd="/r/c", proc_start="333")  # not in tmux
    starttimes = {100: "111", 200: "222", 300: "333"}
    # both 100 and 200 walk up to pane pids that map to the SAME tmux session `sA`.
    ppid = {100: 50, 50: 1, 200: 51, 51: 1, 300: 60, 60: 1}
    pane_pid_to_session = {50: "sA", 51: "sA"}

    names = claude_sessions.names_by_tmux_session(
        sessions_dir=tmp_path,
        pane_pid_to_session=pane_pid_to_session,
        ppid_of=lambda *, pid: ppid.get(pid),
        starttime_of=lambda *, pid: starttimes.get(pid),
    )
    assert names == {"sA": {"alpha", "helper"}}  # BOTH names kept; gamma (out of tmux) omitted
