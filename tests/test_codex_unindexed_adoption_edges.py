"""Fail-soft edges for unindexed Codex adoption diagnostics."""

from __future__ import annotations

import codex_sessions
from test_codex_sessions_fakes import ID_A, ID_B, fake_index, fake_rollout
from test_supervisor_builders import make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_map_unindexed_codex_sessions_skips_processes_that_cannot_be_joined(tmp_path):
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "named-topic")])

    def pids(*, comm):
        return [1, 2, 3, 4] if comm == codex_sessions.CODEX_COMM else []

    def fds(*, pid):
        return {
            1: ["/dev/null"],
            2: [fake_rollout(session_id=ID_A)],
            3: [fake_rollout(session_id=ID_B)],
            4: [fake_rollout(session_id=ID_B)],
        }.get(pid, [])

    def cwd(*, pid):
        return {1: "/repo", 2: "/repo", 4: "/repo"}.get(pid)

    assert (
        codex_sessions.map_unindexed_codex_sessions(
            pane_pid_to_session={},
            codex_home=home,
            pids_of_comm=pids,
            fd_targets_of=fds,
            cwd_of=cwd,
            ppid_of=lambda *, pid: {1: 100, 2: 200, 3: 300}.get(pid),
        )
        == []
    )


def test_map_unindexed_codex_sessions_accepts_the_default_codex_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert (
        codex_sessions.map_unindexed_codex_sessions(
            pane_pid_to_session={},
            pids_of_comm=lambda *, comm: [],
        )
        == []
    )


def test_unindexed_codex_row_skips_a_live_session_outside_the_watch_set(tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path, topic="adoption-gap")
    codex_home = fake_index(tmp_path=tmp_path, records=[])
    fake = FakeTmux()
    fake.pane_pids = {7001: "live-codex"}

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        codex_home=str(codex_home),
        codex_pids_of_comm=lambda *, comm: [9000] if comm == codex_sessions.CODEX_COMM else [],
        codex_fd_targets_of=lambda *, pid: [fake_rollout(session_id=ID_B)],
        codex_cwd_of=lambda *, pid: str(tmp_path / "outside"),
        ppid_of=lambda *, pid: {9000: 7001}.get(pid),
    )

    assert [row.status for row in sup.tick(act=True)] == ["unassigned"]
