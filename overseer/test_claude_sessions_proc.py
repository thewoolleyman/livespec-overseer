"""Tests for real /proc reader boundaries."""

import os

import claude_sessions

__all__: list[str] = []


def test_proc_readers_on_this_process():
    # The real /proc readers, exercised against THIS process (safe, always present).
    assert claude_sessions.proc_ppid(pid=os.getpid()) == os.getppid()
    assert claude_sessions.proc_starttime(pid=os.getpid()) is not None
    # A PID that cannot exist → fail-soft None (never raises).
    assert claude_sessions.proc_ppid(pid=2**30) is None
    assert claude_sessions.proc_starttime(pid=2**30) is None


def test_proc_comm_and_children_on_this_process():
    # The real /proc readers, exercised against THIS process (safe, always present).
    comm = claude_sessions.proc_comm(pid=os.getpid())
    assert comm is not None and comm != ""
    children = claude_sessions.proc_children(pid=os.getpid())
    assert isinstance(children, list)
    assert all(isinstance(pid, int) for pid in children)
    # A PID that cannot exist → fail-soft (None / []), never raises.
    assert claude_sessions.proc_comm(pid=2**30) is None
    assert claude_sessions.proc_children(pid=2**30) == []
