"""Beside-tests for `codex_sessions` — the adoption twin and the /proc primitives.

Split from `test_codex_sessions.py`, which carried the whole surface and crossed the
250-LLOC hard ceiling. This module owns `map_codex_sessions` (emitting the SAME
(tmux_session, name, cwd) triple as the Claude twin so `adopt` consumes either
runtime through one code path), `codex_by_tmux_session`, and the injected /proc
readers underneath them.

Every /proc + filesystem coupling is injected, so these run with no codex process and
no real `~/.codex`.
"""

from __future__ import annotations

from pathlib import Path

import codex_session_index
import codex_sessions
from test_codex_sessions_fakes import (
    ID_A,
    ID_B,
    fake_host,
    fake_index,
    fake_rollout,
)

__all__: list[str] = []

# --------------------------------------------------------------------------- #
# map_codex_sessions — the twin of claude_sessions.map_named_sessions, emitting the
# SAME (tmux_session, name, cwd) triple so `adopt` can consume either runtime through
# one code path instead of growing a parallel Codex branch.
# --------------------------------------------------------------------------- #


def test_map_codex_sessions_emits_the_same_triple_as_the_claude_twin(*, tmp_path):
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "topic-a")])
    host = fake_host(
        comms={4242: "codex"},
        cwds={4242: "/data/projects/livespec"},
        fds={4242: [fake_rollout(session_id=ID_A)]},
    )
    mapped = codex_sessions.map_codex_sessions(
        codex_home=home,
        pane_pid_to_session={9000: "livespec3"},
        ppid_of=lambda *, pid: {4242: 9000}.get(pid),  # the codex pid's parent IS the pane pid
        **host,
    )
    assert mapped == [("livespec3", "topic-a", "/data/projects/livespec")]


def test_map_codex_sessions_omits_a_session_not_inside_tmux(*, tmp_path):
    """Mirrors the Claude twin: a codex session running outside tmux (a bare SSH shell)
    has no pane to drive, so it is omitted rather than mapped to nothing."""
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "topic-a")])
    host = fake_host(
        comms={4242: "codex"},
        cwds={4242: "/data/projects/livespec"},
        fds={4242: [fake_rollout(session_id=ID_A)]},
    )
    mapped = codex_sessions.map_codex_sessions(
        codex_home=home,
        pane_pid_to_session={},  # no tmux panes at all
        ppid_of=lambda *, pid: None,
        **host,
    )
    assert mapped == []


def test_map_codex_sessions_is_deterministic_across_sessions(*, tmp_path):
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "topic-a"), (ID_B, "topic-b")])
    host = fake_host(
        comms={20: "codex", 10: "codex"},
        cwds={10: "/data/projects/one", 20: "/data/projects/two"},
        fds={10: [fake_rollout(session_id=ID_A)], 20: [fake_rollout(session_id=ID_B)]},
    )
    mapped = codex_sessions.map_codex_sessions(
        codex_home=home,
        pane_pid_to_session={101: "s-one", 202: "s-two"},
        ppid_of=lambda *, pid: {10: 101, 20: 202}.get(pid),
        **host,
    )
    assert mapped == [  # pid order, like the Claude twin's sorted-registry order
        ("s-one", "topic-a", "/data/projects/one"),
        ("s-two", "topic-b", "/data/projects/two"),
    ]


# --------------------------------------------------------------------------- #
# codex_by_tmux_session — the twin of claude_sessions.status_by_tmux_session, and the
# LAST primitive the supervisor wiring needs. It is what lets a Codex track be
# identified EXACTLY rather than by pane-command string-matching: tmux reports a codex
# pane's command as `bun` (the launcher; the vendored codex binary is its child), and
# `bun` is generic — any bun app would match. Keying identity off a live session map
# instead is exact, self-correcting, and needs no stored `runtime` field.
# --------------------------------------------------------------------------- #


def test_codex_by_tmux_session_keys_live_sessions_by_tmux_session_and_name(*, tmp_path):
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "topic-a"), (ID_B, "topic-b")])
    host = fake_host(
        comms={10: "codex", 20: "codex"},
        cwds={10: "/data/projects/one", 20: "/data/projects/two"},
        fds={10: [fake_rollout(session_id=ID_A)], 20: [fake_rollout(session_id=ID_B)]},
    )
    by = codex_sessions.codex_by_tmux_session(
        pane_pid_to_session={101: "s-one", 202: "s-two"},
        codex_home=home,
        ppid_of=lambda *, pid: {10: 101, 20: 202}.get(pid),
        **host,
    )
    assert set(by) == {("s-one", "topic-a"), ("s-two", "topic-b")}
    assert by[("s-one", "topic-a")].pid == 10
    assert by[("s-two", "topic-b")].pid == 20


def test_codex_by_tmux_session_keeps_both_when_two_share_one_tmux_session(*, tmp_path):
    """#4: two codex sessions in ONE tmux session, each named for its own plan topic, must
    BOTH survive — keyed by (tmux, name) so neither shadows the other. A single value per
    tmux session would drop the second, silently losing its ctx reading, wrap-up, and
    restart (invisible in the table). The codex analogue of the set-valued
    `names_by_tmux_session` (R2 SF5)."""
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "topic-a"), (ID_B, "topic-b")])
    host = fake_host(
        comms={10: "codex", 20: "codex"},
        cwds={10: "/data/projects/one", 20: "/data/projects/one"},
        fds={10: [fake_rollout(session_id=ID_A)], 20: [fake_rollout(session_id=ID_B)]},
    )
    # Both codex pids resolve (via their pane pids) to the SAME tmux session "shared".
    by = codex_sessions.codex_by_tmux_session(
        pane_pid_to_session={101: "shared", 202: "shared"},
        codex_home=home,
        ppid_of=lambda *, pid: {10: 101, 20: 202}.get(pid),
        **host,
    )
    assert set(by) == {("shared", "topic-a"), ("shared", "topic-b")}
    assert by[("shared", "topic-a")].pid == 10
    assert by[("shared", "topic-a")].session_id == ID_A
    assert by[("shared", "topic-b")].pid == 20
    assert by[("shared", "topic-b")].session_id == ID_B


def test_codex_by_tmux_session_is_empty_with_no_codex_running(*, tmp_path):
    """The overwhelmingly common case — a fleet of Claude sessions and no codex at all.
    Must be an empty map, never an error, so `evaluate` can key off it unconditionally."""
    home = fake_index(tmp_path=tmp_path, records=[])
    by = codex_sessions.codex_by_tmux_session(
        pane_pid_to_session={}, codex_home=home, **fake_host()
    )
    assert by == {}


def test_codex_by_tmux_session_omits_sessions_outside_tmux(*, tmp_path):
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "topic-a")])
    host = fake_host(
        comms={10: "codex"}, cwds={10: "/x"}, fds={10: [fake_rollout(session_id=ID_A)]}
    )
    by = codex_sessions.codex_by_tmux_session(
        pane_pid_to_session={}, codex_home=home, ppid_of=lambda *, pid: None, **host
    )
    assert by == {}


def test_codex_by_tmux_session_keeps_the_first_on_a_same_tmux_same_name_collision(*, tmp_path):
    """Only a GENUINE collision — two codex processes for the SAME topic in the SAME tmux
    session — drops one, and the drop is deterministic: the first by pid order wins, so a
    stray duplicate can never flap the supervisor's view of that track between ticks."""
    home = fake_index(
        tmp_path=tmp_path, records=[(ID_A, "topic-a"), (ID_B, "topic-a")]
    )  # SAME thread_name
    host = fake_host(
        comms={10: "codex", 20: "codex"},
        cwds={10: "/data/projects/one", 20: "/data/projects/one"},
        fds={10: [fake_rollout(session_id=ID_A)], 20: [fake_rollout(session_id=ID_B)]},
    )
    by = codex_sessions.codex_by_tmux_session(
        pane_pid_to_session={101: "shared", 202: "shared"},
        codex_home=home,
        ppid_of=lambda *, pid: {10: 101, 20: 202}.get(pid),
        **host,
    )
    assert set(by) == {("shared", "topic-a")}
    assert by[("shared", "topic-a")].pid == 10  # the FIRST by pid order, not the last
    assert by[("shared", "topic-a")].session_id == ID_A


def test_rollout_exists_is_false_when_the_sessions_tree_cannot_be_walked(*, monkeypatch):
    """Fail-soft to False: an unwalkable sessions tree must read as "no rollout" — recovery
    then falls back to skip+surface (option b) instead of raising mid-tick. Stubbed rather
    than chmod'ed because `Path.rglob` swallows the ordinary EACCES case itself."""

    class _UnwalkableTree:
        def __truediv__(self, _other):
            return self

        def rglob(self, _pattern):
            raise OSError(5, "Input/output error")

    monkeypatch.setattr(codex_session_index, "Path", lambda _path: _UnwalkableTree())
    assert codex_sessions.rollout_exists(session_id=ID_A, codex_home="/somewhere") is False


# --------------------------------------------------------------------------- #
# The REAL /proc readers + the real `~/.codex` default. These are the host
# couplings every test above injects around, so nothing else in the suite runs
# them. They are driven here against a FAKE /proc tree (real dirs + real
# symlinks under tmp_path) with the module's hardcoded `/proc` prefix redirected
# at it, and against a HOME pointed at tmp_path — no live process, no real
# `~/.codex`.
# --------------------------------------------------------------------------- #


def _fake_proc(*, tmp_path, monkeypatch, present=True):
    """Point the module's hardcoded ``/proc`` reads at a tmp tree (absent if not ``present``)."""
    root = tmp_path / "proc"
    if present:
        root.mkdir(exist_ok=True)

    def _redirect(arg):
        text = str(arg)
        if text == "/proc":
            return root
        if text.startswith("/proc/"):
            return root / text[len("/proc/") :]
        return Path(text)

    monkeypatch.setattr(codex_sessions, "Path", _redirect)
    return root


def test_default_codex_home_is_dot_codex_under_the_users_home(*, tmp_path, monkeypatch):
    """The default that the injectable `codex_home` seam overrides everywhere else."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert codex_sessions.default_codex_home() == tmp_path / ".codex"


def test_proc_fd_targets_reads_the_open_fd_symlinks(*, tmp_path, monkeypatch):
    """The fd table IS the pid→session link: a real codex process holds its rollout open,
    so reading the fd targets and running the join over them recovers the session id."""
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fds = root / "4242" / "fd"
    fds.mkdir(parents=True)
    (fds / "0").symlink_to("/dev/null")
    (fds / "3").symlink_to(fake_rollout(session_id=ID_A))

    assert sorted(codex_sessions.proc_fd_targets(pid=4242)) == [
        "/dev/null",
        fake_rollout(session_id=ID_A),
    ]
    joined = codex_sessions.open_rollout_id(pid=4242, fd_targets_of=codex_sessions.proc_fd_targets)
    assert joined == ID_A


def test_proc_fd_targets_skips_an_entry_that_cannot_be_readlinked(*, tmp_path, monkeypatch):
    """An fd that closed underneath the scan (here: an entry that is not a symlink at all)
    is skipped per-ENTRY — the surviving fds still come back, so one racing close never
    blanks the whole fd read."""
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fds = root / "7" / "fd"
    fds.mkdir(parents=True)
    (fds / "0").symlink_to("/dev/null")
    (fds / "1").write_text("", encoding="utf-8")  # not a symlink → EINVAL on readlink
    assert codex_sessions.proc_fd_targets(pid=7) == ["/dev/null"]


def test_proc_fd_targets_is_empty_for_a_pid_that_is_gone(*, tmp_path, monkeypatch):
    _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    assert codex_sessions.proc_fd_targets(pid=999999) == []


def test_proc_cwd_reads_the_cwd_symlink_and_is_none_when_the_pid_is_gone(*, tmp_path, monkeypatch):
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    (root / "4242").mkdir()
    (root / "4242" / "cwd").symlink_to("/data/projects/livespec")
    assert codex_sessions.proc_cwd(pid=4242) == "/data/projects/livespec"
    assert codex_sessions.proc_cwd(pid=999999) is None


def test_proc_pids_of_comm_scans_proc_for_matching_processes(*, tmp_path, monkeypatch):
    """The scan keeps only NUMERIC `/proc` entries (so `self` / `cpuinfo` are skipped),
    keeps only pids whose comm matches exactly, and returns them sorted."""
    root = _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch)
    for name in ("20", "10", "30", "self", "cpuinfo"):
        (root / name).mkdir()
    monkeypatch.setattr(
        codex_sessions, "proc_comm", lambda *, pid: {10: "codex", 20: "bun", 30: "codex"}.get(pid)
    )

    assert codex_sessions.proc_pids_of_comm(comm="codex") == [10, 30]
    assert codex_sessions.proc_pids_of_comm(comm="bun") == [20]  # the launcher is NOT codex
    assert codex_sessions.proc_pids_of_comm(comm="node") == []


def test_proc_pids_of_comm_is_empty_when_proc_cannot_be_scanned(*, tmp_path, monkeypatch):
    """Fail-soft to []: no scannable `/proc` means "no codex running", never a raise."""
    _fake_proc(tmp_path=tmp_path, monkeypatch=monkeypatch, present=False)
    assert codex_sessions.proc_pids_of_comm(comm="codex") == []
