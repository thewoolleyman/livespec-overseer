"""Beside-tests for ``declare.py`` edge branches."""

from __future__ import annotations

import declare
import registry
import signals

__all__: list[str] = []


class FakeTmux:
    def __init__(self, *, session: str | None) -> None:
        self.session = session

    def pane_session_name(self, *, pane: str) -> str | None:
        assert pane == "%9"
        return self.session


def test_ready_uses_overseer_topic_env_before_tmux(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("OVERSEER_TOPIC", "env-topic")
    monkeypatch.setenv("TMUX_PANE", "%9")

    code = declare.main(argv=["ready", "--repo", str(repo)], tmux=FakeTmux(session="wrong"))

    assert code == 0
    assert signals.read_state(repo=str(repo), topic="env-topic").token == signals.STATE_READY


def test_ready_maps_collision_session_back_to_topic(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    store = tmp_path / "map.jsonl"
    monkeypatch.setenv("TMUX_PANE", "%9")
    monkeypatch.setattr(registry, "DEFAULT_STORE_PATH", store)
    registry.append_mapping(
        track=registry.Track(repo=str(repo), topic="topic", tmux="repo-topic"),
        store_path=store,
    )

    code = declare.main(argv=["ready", "--repo", str(repo)], tmux=FakeTmux(session="repo-topic"))

    assert code == 0
    assert signals.read_state(repo=str(repo), topic="topic").token == signals.STATE_READY


def test_ready_falls_back_to_session_name_when_mapping_has_no_match(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    store = tmp_path / "map.jsonl"
    monkeypatch.setenv("TMUX_PANE", "%9")
    monkeypatch.setattr(registry, "DEFAULT_STORE_PATH", store)
    registry.append_mapping(
        track=registry.Track(repo=str(repo), topic="other-topic", tmux="other-session"),
        store_path=store,
    )

    code = declare.main(argv=["ready", "--repo", str(repo)], tmux=FakeTmux(session="plain-topic"))

    assert code == 0
    assert signals.read_state(repo=str(repo), topic="plain-topic").token == signals.STATE_READY


def test_ready_uses_real_tmux_driver_when_no_driver_is_injected(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("TMUX_PANE", "%9")
    monkeypatch.setattr(declare.tmuxio, "TmuxIO", lambda: FakeTmux(session="default-topic"))

    code = declare.main(argv=["ready", "--repo", str(repo)])

    assert code == 0
    assert signals.read_state(repo=str(repo), topic="default-topic").token == signals.STATE_READY


def test_ready_reports_missing_topic_when_no_tmux_context(*, tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.delenv("OVERSEER_TOPIC", raising=False)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)

    code = declare.main(argv=["ready", "--repo", str(repo)])

    assert code == 2
    assert "cannot infer plan topic" in capsys.readouterr().err


def test_ready_reports_missing_topic_when_tmux_has_no_session_name(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.delenv("OVERSEER_TOPIC", raising=False)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setenv("TMUX_PANE", "%9")

    code = declare.main(argv=["ready", "--repo", str(repo)], tmux=FakeTmux(session=None))

    assert code == 2
