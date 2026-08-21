"""Top-level regression tests for `supervisor.py start` launch diagnostics."""

import pytest
import registry
import supervisor
from test_supervisor_builders import idle_capture, isolate_store, make_plan, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


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
    assert registry.read_valid_mapping(store_path=store) == [
        mapped_track(repo=repo, topic=topic, session=session)
    ]
