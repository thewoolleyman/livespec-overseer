"""Integration coverage for the terminal ``done`` session declaration."""

from __future__ import annotations

import importlib

from overseer import signals

__all__: list[str] = []


def test_overseer_declare_done_writes_a_valid_session_declaration(*, tmp_path, monkeypatch) -> None:
    module = importlib.import_module("overseer.declare")
    repo = tmp_path / "repo"
    topic = "finished-work"
    repo.mkdir()
    monkeypatch.setenv("OVERSEER_TOPIC", topic)

    try:
        code = module.main(argv=["done", "--repo", str(repo)])
    except SystemExit as exc:
        code = exc.code

    assert code == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == "done"
    assert signals.valid_session_token(token=state.token)


def test_overseer_declare_done_with_summary_writes_a_valid_session_declaration(
    *, tmp_path, monkeypatch
) -> None:
    module = importlib.import_module("overseer.declare")
    repo = tmp_path / "repo"
    topic = "finished-with-summary"
    repo.mkdir()
    monkeypatch.setenv("OVERSEER_TOPIC", topic)

    try:
        code = module.main(argv=["done:", "released", "and", "archived", "--repo", str(repo)])
    except SystemExit as exc:
        code = exc.code

    assert code == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_DONE
    assert state.detail == "released and archived"
    assert signals.valid_session_token(token=state.token)
