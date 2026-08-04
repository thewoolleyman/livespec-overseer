"""Live Codex sessions that cannot be adopted must be visible."""

from __future__ import annotations

import codex_sessions
import pytest
import registry
import signals
from test_codex_sessions_fakes import ID_A, ID_B, fake_host, fake_index, fake_rollout
from test_supervisor_builders import (
    arm_ready_marker,
    codex_idle_capture,
    make_plan,
    make_supervisor,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


ID_C = "019fc714-beaa-7992-aedf-039091f6d94a"


@pytest.mark.parametrize(
    "fds",
    [
        [fake_rollout(session_id=ID_A), fake_rollout(session_id=ID_C)],
        [fake_rollout(session_id=ID_C), fake_rollout(session_id=ID_A)],
    ],
)
def test_live_codex_session_prefers_indexed_rollout_over_unindexed_fd_order(fds, tmp_path):
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "critical-path")])
    host = fake_host(
        comms={9000: codex_sessions.CODEX_COMM},
        cwds={9000: "/data/projects/livespec"},
        fds={9000: fds},
    )

    out = codex_sessions.read_live_codex_sessions(codex_home=home, **host)

    assert [(session.name, session.session_id) for session in out] == [("critical-path", ID_A)]


def test_process_holding_only_unindexed_rollouts_still_surfaces_as_unnamed(tmp_path):
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "some-other-topic")])
    host = fake_host(
        comms={9000: codex_sessions.CODEX_COMM},
        cwds={9000: "/data/projects/livespec"},
        fds={9000: [fake_rollout(session_id=ID_B), fake_rollout(session_id=ID_C)]},
    )

    assert codex_sessions.read_live_codex_sessions(codex_home=home, **host) == []
    unindexed = codex_sessions.map_unindexed_codex_sessions(
        codex_home=home,
        pane_pid_to_session={7001: "critical-path"},
        ppid_of=lambda *, pid: {9000: 7001}.get(pid),
        **host,
    )
    assert [(session.tmux_session, session.session_id) for session in unindexed] == [
        ("critical-path", ID_B)
    ]


def test_tick_surfaces_unindexed_live_codex_session_in_watched_repo(tmp_path):
    """A live Codex TUI with an open rollout but no index name must not disappear behind
    ``unassigned``. The daemon cannot adopt it to a plan topic, but it can show the
    operator the tmux session whose Codex thread is structurally unadoptable."""
    repo, _topic = make_plan(tmp_path=tmp_path, topic="adoption-gap")
    codex_home = fake_index(tmp_path=tmp_path, records=[(ID_A, "some-other-topic")])
    fake = FakeTmux()
    fake.pane_pids = {7001: "live-codex"}

    def pids(*, comm):
        return [9000] if comm == codex_sessions.CODEX_COMM else []

    def fds(*, pid):
        return [fake_rollout(session_id=ID_B)] if pid == 9000 else []

    def cwd(*, pid):
        return str(repo) if pid == 9000 else None

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        codex_home=str(codex_home),
        codex_pids_of_comm=pids,
        codex_fd_targets_of=fds,
        codex_cwd_of=cwd,
        ppid_of=lambda *, pid: {9000: 7001}.get(pid),
    )

    views = sup.tick(act=True)

    assert [(row.status, row.tmux, row.runtime) for row in views] == [
        ("unassigned", None, None),
        ("codex-unindexed", "live-codex", "codex"),
    ]
    assert registry.read_mapping(store_path=sup.store_path) == []
    out = sup.out.getvalue()
    assert "NEEDS YOU (1):" in out
    assert f"topic: codex:{ID_B[:8]} | tmux: live-codex (codex) | repo: repo" in out
    assert "no session_index thread_name" in out


def test_indexed_rollout_fd_makes_track_codex_and_routes_ready_restart(tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="critical-path")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    codex_home = fake_index(tmp_path=tmp_path, records=[(ID_A, topic)])
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40, topic=topic), cmd="bun"
    )
    fake.pane_pids = {7001: session}
    host = fake_host(
        comms={9000: codex_sessions.CODEX_COMM},
        cwds={9000: str(repo)},
        fds={9000: [fake_rollout(session_id=ID_C), fake_rollout(session_id=ID_A)]},
    )

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        codex_home=str(codex_home),
        codex_pids_of_comm=host["pids_of_comm"],
        codex_fd_targets_of=host["fd_targets_of"],
        codex_cwd_of=host["cwd_of"],
        ppid_of=lambda *, pid: {9000: 7001}.get(pid),
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    views = sup.tick(act=True)

    assert [(row.topic, row.runtime, row.status) for row in views] == [
        (topic, "codex", "restarting")
    ]
    assert signals.read_state(repo=str(repo), topic=topic) is None
    respawn_commands = [call[3] for call in fake.calls if call[0] == "respawn"]
    assert len(respawn_commands) == 1
    assert f"codex resume --dangerously-bypass-approvals-and-sandbox {ID_A}" in respawn_commands[0]
    assert ID_C not in respawn_commands[0]
