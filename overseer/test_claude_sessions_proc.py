"""Tests for real /proc reader boundaries."""

import os
import threading

import claude_sessions

__all__: list[str] = []


def _fork_waiting_child() -> tuple[int, int]:
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(write_fd)
        os.read(read_fd, 1)
        os._exit(0)
    os.close(read_fd)
    return pid, write_fd


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


def test_proc_children_includes_a_child_spawned_by_a_running_worker_thread():
    worker_started = threading.Event()
    release_worker = threading.Event()
    worker_child: list[tuple[int, int]] = []
    main_child = _fork_waiting_child()

    def spawn_from_worker() -> None:
        worker_child.append(_fork_waiting_child())
        worker_started.set()
        release_worker.wait()

    worker = threading.Thread(target=spawn_from_worker)
    worker.start()
    try:
        assert worker_started.wait(timeout=5)
        children = claude_sessions.proc_children(pid=os.getpid())
        assert {main_child[0], worker_child[0][0]} <= set(children)
    finally:
        release_worker.set()
        worker.join(timeout=5)
        for child_pid, write_fd in [main_child, *worker_child]:
            os.write(write_fd, b"x")
            os.close(write_fd)
            os.waitpid(child_pid, 0)
