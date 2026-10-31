"""Integration coverage for the session declaration command."""

from __future__ import annotations

from overseer import declare, signals

__all__: list[str] = []


def test_scenario_declaration_command_refuses_a_value_the_daemon_would_reject(*, tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = signals.state_path(repo=str(repo), topic="topic")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"ready\n")

    assert (
        declare.main(argv=["blocked", "bad\nreason", "--repo", str(repo), "--topic", "topic"]) == 2
    )
    assert "accepted forms" in capsys.readouterr().err
    assert path.read_bytes() == b"ready\n"


def test_scenario_declaration_command_clears_only_what_a_session_may_clear(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = signals.state_path(repo=str(repo), topic="topic")
    path.parent.mkdir(parents=True)
    path.write_text("idle-with-context-left\n", encoding="utf-8")

    assert declare.main(argv=["clear", "--repo", str(repo), "--topic", "topic"]) == 0
    assert not path.exists()
    path.write_text("ready-expired\n", encoding="utf-8")
    assert declare.main(argv=["clear", "--repo", str(repo), "--topic", "topic"]) == 0
    assert path.exists()
