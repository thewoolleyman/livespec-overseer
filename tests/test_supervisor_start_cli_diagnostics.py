"""Top-level regression tests for `supervisor.py start` launch diagnostics."""

import _supervisor_launch_profile
import pytest
import registry
import supervisor
from test_supervisor_builders import idle_capture, isolate_store, make_plan
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(claude.parent))


def test_cli_start_reports_session_create_failure_as_a_step_reason(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.new_session_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    assert "reason=session_create_failed" in capsys.readouterr().err
    assert registry.read_valid_mapping(store_path=store) == []


def test_cli_start_reports_claude_launch_failure_as_a_step_reason(*, tmp_path, monkeypatch, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.respawn_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    assert "reason=claude_launch_failed" in capsys.readouterr().err
    assert registry.read_valid_mapping(store_path=store) == []


def test_cli_start_resolves_claude_from_home_local_bin_when_path_is_sanitized(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    home = tmp_path / "home"
    claude = home / ".local" / "bin" / "claude"
    claude.parent.mkdir(parents=True)
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin")
    fake = FakeTmux()
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    respawns = [call for call in fake.calls if call[0] == "respawn"]
    assert len(respawns) == 1
    assert respawns[0][3].startswith(f"{claude} --model 'opus[1m]' ")
    assert f"{repo}::{topic}" in capsys.readouterr().out
    assert len(registry.read_valid_mapping(store_path=store)) == 1


def test_cli_start_refuses_before_respawn_when_claude_is_not_resolvable(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    fake = FakeTmux()
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    err = capsys.readouterr().err
    assert "reason=launch_binary_not_resolvable" in err
    assert "binary=claude" in err
    assert f"path={tmp_path / 'empty-bin'}" in err
    assert not fake.has(method="respawn")
    assert registry.read_valid_mapping(store_path=store) == []


def test_launch_preflight_rewrites_an_absolute_executable(*, tmp_path):
    binary = tmp_path / "claude"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)

    assert (
        _supervisor_launch_profile.preflight_launch_command(command=f"{binary} --version")
        == f"{binary} --version"
    )


def test_launch_preflight_rejects_empty_and_nonexecutable_absolute_commands(*, tmp_path):
    missing = tmp_path / "missing-claude"

    empty = _supervisor_launch_profile.preflight_launch_command(command="")
    nonexecutable = _supervisor_launch_profile.preflight_launch_command(command=str(missing))

    assert isinstance(empty, _supervisor_launch_profile.LaunchProfileProblem)
    assert "binary=" in empty.message
    assert isinstance(nonexecutable, _supervisor_launch_profile.LaunchProfileProblem)
    assert f"binary={missing}" in nonexecutable.message


def test_cli_start_reports_resume_submit_failure_as_a_step_reason(*, tmp_path, monkeypatch, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.paste_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    assert "reason=resume_submit_failed" in capsys.readouterr().err
    assert registry.read_valid_mapping(store_path=store) == []


def test_cli_start_cleans_up_a_created_session_after_launch_failure_so_retry_can_start(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.respawn_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1
    assert ("kill", session) in fake.calls
    assert not fake.session_exists(session=session)

    fake.respawn_ok = True
    fake.panes[session] = idle_capture()

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    streams = capsys.readouterr()
    assert "reason=claude_launch_failed" in streams.err
    assert f"started {repo}::{topic}" in streams.out
    rows = registry.read_valid_mapping(store_path=store)
    assert len(rows) == 1
    assert rows[0].repo == str(repo)
    assert rows[0].topic == topic
    assert rows[0].tmux == session
    assert rows[0].added_at is not None


def test_cli_start_ignores_nonmatching_existing_mapping(*, tmp_path, monkeypatch, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="other",
            repo=str(repo),
            tmux="other",
            epic="overseer-other",
        ),
        store_path=store,
        added_at="2026-08-21T00:00:00Z",
    )
    fake = FakeTmux()
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    assert f"{repo}::{topic}" in capsys.readouterr().out
    rows = registry.read_valid_mapping(store_path=store)
    assert {row.topic for row in rows} == {"other", topic}


def test_cli_start_force_respawns_existing_grooming_seat_mapping(*, tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    topic = "repo-grooming"
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=registry.GroomingSeat(
            topic=topic,
            repo=str(repo),
            tmux=topic,
            epic="overseer-grooming",
        ),
        store_path=store,
        added_at="2026-08-21T00:00:00Z",
    )
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(), cmd="node")
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--force", "--repo", str(repo), "--topic", topic]) == 0

    assert fake.has(method="respawn")
    assert f"started {repo}::{topic}" in capsys.readouterr().out
    rows = registry.read_valid_mapping(store_path=store)
    assert len(rows) == 1
    assert rows[0].kind == "grooming"
    assert rows[0].epic == "overseer-grooming"
