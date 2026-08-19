"""Live Codex sessions that cannot be adopted must be visible."""

from __future__ import annotations

import io
import os
import subprocess
import time
from pathlib import Path

import codex_sessions
import pytest
import registry
import signals
import supervisor
import tmuxio
from test_codex_sessions_fakes import ID_A, ID_B, fake_host, fake_index, fake_rollout
from test_supervisor_builders import (
    arm_ready_marker,
    codex_busy_capture,
    codex_idle_capture,
    make_plan,
    make_supervisor,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


ID_C = "019fc714-beaa-7992-aedf-039091f6d94a"


def _mapped_unindexed_codex_supervisor(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="critical-path")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    codex_home = fake_index(tmp_path=tmp_path, records=[(ID_A, "some-other-topic")])
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40, topic=topic), cmd="bun"
    )
    fake.pane_pids = {7001: session}
    host = fake_host(
        comms={9000: codex_sessions.CODEX_COMM},
        cwds={9000: str(repo)},
        fds={9000: [fake_rollout(session_id=ID_B)]},
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
    registry.append_mapping(
        track=registry.Track(topic=topic, repo=str(repo), tmux=session, epic="overseer-test-epic"),
        store_path=sup.store_path,
        added_at="2026-08-19T00:00:00Z",
    )
    return repo, topic, session, fake, sup


def _tmux_socket_name(*, tmp_path: Path) -> str:
    return f"codex-unindexed-{os.getpid()}-{tmp_path.name}"


def _tmux_socket_path(*, tmp_path: Path) -> Path:
    base = Path(os.environ.get("TMUX_TMPDIR", "/tmp"))
    return base / f"tmux-{os.getuid()}" / _tmux_socket_name(tmp_path=tmp_path)


def _tmux_wrapper(*, tmp_path: Path) -> Path:
    socket = _tmux_socket_name(tmp_path=tmp_path)
    wrapper = tmp_path / "tmux-private"
    wrapper.write_text(f'#!/bin/sh\nexec /usr/bin/tmux -L {socket} "$@"\n', encoding="utf-8")
    wrapper.chmod(0o700)
    return wrapper


def _close_private_tmux(*, tmp_path: Path) -> None:
    subprocess.run(  # noqa: S603
        [str(_tmux_wrapper(tmp_path=tmp_path)), "kill-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    _tmux_socket_path(tmp_path=tmp_path).unlink(missing_ok=True)


def _session_with_real_tmux(*, inner: tmuxio.TmuxIO, session: str, repo: Path) -> None:
    assert inner.new_session(name=session, cwd=str(repo))
    for _attempt in range(100):
        if inner.session_exists(session=session):
            return
        time.sleep(0.05)
    raise AssertionError(f"tmux session {session} did not start")


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
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    out = sup.out.getvalue()
    assert "NEEDS YOU (1):" in out
    assert f"topic: codex:{ID_B[:8]} | tmux: live-codex (codex) | repo: repo" in out
    assert "no session_index thread_name" in out


def test_mapped_unindexed_codex_track_gets_wrapup_and_ready_restart(tmp_path):
    repo, topic, _session, fake, sup = _mapped_unindexed_codex_supervisor(tmp_path=tmp_path)

    def paste_lands_as_codex_busy(session, _text):
        fake.panes[session] = codex_busy_capture(ctx=40)

    fake.on_paste = paste_lands_as_codex_busy
    warned = sup.tick(act=True)

    assert [(row.topic, row.runtime, row.status, row.tmux) for row in warned] == [
        (topic, "codex", "warned", registry.tmux_id(repo=str(repo), topic=topic))
    ]
    assert any("Declare your state by writing ONE line" in text for text in fake.paste_texts())

    fake.on_paste = None
    fake.panes[registry.tmux_id(repo=str(repo), topic=topic)] = codex_idle_capture(
        ctx=40, topic=topic
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    restarted = sup.tick(act=True)

    assert [(row.topic, row.runtime, row.status) for row in restarted] == [
        (topic, "codex", "restarting")
    ]
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    respawn_commands = [call[3] for call in fake.calls if call[0] == "respawn"]
    assert len(respawn_commands) == 1
    assert f"codex resume --dangerously-bypass-approvals-and-sandbox {ID_B}" in respawn_commands[0]


def test_mapped_unindexed_codex_adoption_uses_a_real_tmux_session(tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="real-tmux-codex")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    inner = tmuxio.TmuxIO(tmux_bin=str(_tmux_wrapper(tmp_path=tmp_path)))
    try:
        _session_with_real_tmux(inner=inner, session=session, repo=repo)
        codex_home = fake_index(tmp_path=tmp_path, records=[])
        pane_pid = inner.pane_pid(session=session)
        assert pane_pid is not None
        sup = supervisor.Supervisor(
            tmux=inner,
            store_path=str(tmp_path / "map.jsonl"),
            stamp_path=str(tmp_path / "stamps.json"),
            status_path=str(tmp_path / "status.json"),
            watch_repos=[str(repo)],
            out=io.StringIO(),
            now=lambda: 1000.0,
            sleep=lambda _seconds: None,
            codex_home=str(codex_home),
            codex_pids_of_comm=lambda *, comm: [9000] if comm == codex_sessions.CODEX_COMM else [],
            codex_fd_targets_of=lambda *, pid: [fake_rollout(session_id=ID_B)]
            if pid == 9000
            else [],
            codex_cwd_of=lambda *, pid: str(repo) if pid == 9000 else None,
            ppid_of=lambda *, pid: {9000: pane_pid}.get(pid),
            proc_root=str(tmp_path),
            which=lambda _name: "/usr/bin/tmux",
            gitignore_check=lambda *, repo: True,
        )
        registry.append_mapping(
            track=registry.Track(topic=topic, repo=str(repo), tmux=session),
            store_path=sup.store_path,
            added_at="2026-08-19T00:00:00Z",
        )

        sup.refresh_codex_sessions()

        live = sup.live_codex.get((session, topic))
        assert live is not None
        assert live.session_id == ID_B
    finally:
        _close_private_tmux(tmp_path=tmp_path)


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
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"codex:{ID_A}",
        stamp_path=sup.stamp_path,
    )
    registry.append_mapping(
        track=registry.Track(topic=topic, repo=str(repo), tmux=session, epic="overseer-test-epic"),
        store_path=sup.store_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    views = sup.tick(act=True)

    assert [(row.topic, row.runtime, row.status) for row in views] == [
        (topic, "codex", "restarting")
    ]
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    respawn_commands = [call[3] for call in fake.calls if call[0] == "respawn"]
    assert len(respawn_commands) == 1
    assert f"codex resume --dangerously-bypass-approvals-and-sandbox {ID_A}" in respawn_commands[0]
    assert ID_C not in respawn_commands[0]
