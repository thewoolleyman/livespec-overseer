"""Integration coverage for malformed overseer state rejection."""

from __future__ import annotations

import signals

from overseer import registry
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux


def test_scenario_a_malformed_state_value_is_moved_aside_and_treated_as_undeclared(*, tmp_path):
    """A malformed declaration is preserved outside the declaration path on that tick."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    state = declare(repo=repo, topic=topic, value="working:\vhidden payload", mtime=1001.0)
    rejected = state.with_name(".overseer-state.rejected")
    rejected.write_text("earlier rejection\n", encoding="utf-8")

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert rejected.read_text(encoding="utf-8") == "working:\vhidden payload\n"
    assert not state.exists()
    assert view.status == "warned"
    expected = "working:hidden payload"
    assert view.note == f"BAD state file: {expected!r}"
    assert any(
        f"RECOVERY: rejected state value: {expected!r}." in text for text in fake.paste_texts()
    )
    assert not fake.has(method="respawn")


def test_malformed_state_is_left_when_a_valid_rewrite_wins_the_guard(*, tmp_path, monkeypatch):
    """The re-read guard never moves a state declaration that changed mid-tick."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    state = declare(repo=repo, topic=topic, value="working: invented token", mtime=1001.0)
    read_state = signals.read_state
    reads = 0

    def rewrite_before_guard(*, repo: str, topic: str):
        nonlocal reads
        reads += 1
        if reads == 2:
            state.write_text("ready\n", encoding="utf-8")
        return read_state(repo=repo, topic=topic)

    monkeypatch.setattr(signals, "read_state", rewrite_before_guard)

    _ = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert state.read_text(encoding="utf-8") == "ready\n"
    assert not state.with_name(".overseer-state.rejected").exists()
