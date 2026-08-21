"""Root coverage for start cleanup diagnostics."""

import pytest
import registry
import supervisor
from test_supervisor_builders import make_plan
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_cli_start_reports_leftover_session_when_cleanup_after_launch_failure_fails(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.respawn_ok = False
    fake.kill_session_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    err = capsys.readouterr().err
    assert f"session={session}" in err
    assert "cleanup=leftover_session" in err


def test_cli_start_does_not_cleanup_a_session_it_did_not_create(*, tmp_path, monkeypatch, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, cmd="zsh")
    fake.respawn_ok = False
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    err = capsys.readouterr().err
    assert "cleanup=not_created" in err
    assert not fake.has(method="kill")
