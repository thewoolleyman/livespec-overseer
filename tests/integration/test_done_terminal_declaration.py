"""Integration coverage for the terminal ``done`` session declaration."""

from __future__ import annotations

import importlib
import io as _io

from overseer import _supervisor_config, registry, signals, supervisor
from overseer.test_supervisor_builders import (
    FakeTmux,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)

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


def test_scenario_a_done_declaration_is_valid_and_never_restarts_the_session(*, tmp_path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: clock["t"],
        out=_io.StringIO(),
    )
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "warned"
    pastes_before_done = len(fake.paste_texts())
    round_before_done = registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=sup.stamp_path
    )
    declare(repo=repo, topic=topic, value="done: release complete", mtime=clock["t"] + 1)

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=5))
    clock["t"] += (
        max(
            _supervisor_config.ACK_STALE_AFTER,
            _supervisor_config.IDLE_NUDGE_AFTER,
        )
        + 1
    )
    danger_view = sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER * 2
    old_idle_view = sup.evaluate(track=track, act=True)

    assert danger_view.status == "done"
    assert old_idle_view.status == "done"
    assert danger_view.note == "release complete"
    assert len(fake.paste_texts()) == pastes_before_done
    assert not fake.has(method="respawn")
    assert supervisor.needs_attention(row=danger_view) is False
    assert (
        registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == round_before_done
    )
