"""Tests for Claude registry-file parsing."""

import json

import claude_sessions

__all__: list[str] = []


def _write(*, directory, pid, name, cwd, proc_start, status="idle"):
    payload = {"pid": pid, "name": name, "cwd": cwd, "procStart": proc_start, "status": status}
    (directory / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_read_live_sessions_keeps_live_named_drops_stale(*, tmp_path):
    _write(
        directory=tmp_path, pid=100, name="alpha", cwd="/r/a", proc_start="111"
    )  # live (starttime matches)
    _write(
        directory=tmp_path, pid=200, name="beta", cwd="/r/b", proc_start="222"
    )  # dead (starttime None)
    _write(
        directory=tmp_path, pid=300, name="gamma", cwd="/r/c", proc_start="333"
    )  # PID reused (mismatch)
    _write(directory=tmp_path, pid=400, name="", cwd="/r/d", proc_start="444")  # no name → skip
    starttimes = {100: "111", 300: "999"}  # 100 matches; 300 mismatches; 200/400 absent

    live = claude_sessions.read_live_sessions(
        sessions_dir=tmp_path, starttime_of=lambda *, pid: starttimes.get(pid)
    )
    assert [(s.pid, s.name, s.cwd) for s in live] == [(100, "alpha", "/r/a")]


def test_read_live_sessions_skips_malformed_files(*, tmp_path):
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    _write(directory=tmp_path, pid=100, name="alpha", cwd="/r/a", proc_start="111")
    live = claude_sessions.read_live_sessions(
        sessions_dir=tmp_path, starttime_of=lambda *, pid: "111"
    )
    assert [s.name for s in live] == ["alpha"]


def test_read_live_sessions_missing_dir_is_empty(*, tmp_path):
    got = claude_sessions.read_live_sessions(
        sessions_dir=tmp_path / "nope", starttime_of=lambda *, pid: "x"
    )
    assert got == []


def test_read_live_sessions_carries_the_status_field(*, tmp_path):
    _write(directory=tmp_path, pid=100, name="alpha", cwd="/r/a", proc_start="111", status="busy")
    live = claude_sessions.read_live_sessions(
        sessions_dir=tmp_path, starttime_of=lambda *, pid: {100: "111"}.get(pid)
    )
    assert [(s.name, s.status) for s in live] == [("alpha", "busy")]


def test_read_live_sessions_missing_status_defaults_empty(*, tmp_path):
    # A registry file with no `status` key must not crash the read; status defaults to "".
    (tmp_path / "100.json").write_text(
        json.dumps({"pid": 100, "name": "alpha", "cwd": "/r/a", "procStart": "111"}),
        encoding="utf-8",
    )
    live = claude_sessions.read_live_sessions(
        sessions_dir=tmp_path, starttime_of=lambda *, pid: {100: "111"}.get(pid)
    )
    assert live[0].status == ""
