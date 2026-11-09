"""Integration coverage for the dead-track conflicting-runtime-evidence scenario.

Tier: `tests.integration` is one of the documented default `scenario_tiers`
prefixes. The test drives the shipped `start` command through `supervisor.main`
over a real registry store and a hermetic Codex home, with a fake tmux that
records every mutation.
"""

from __future__ import annotations

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    FakeTmux,
    codex_home_with,
    isolate_store,
    make_plan,
    make_supervisor,
    mapped_track,
)

__all__: list[str] = []

STALE_CODEX_SESSION = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.mark.integration
def test_scenario_dead_track_with_conflicting_runtime_evidence_is_not_launched(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.append_mapping(track=track, store_path=store)
    fake = FakeTmux()
    fake.sessions.add(session)
    fake.cmds[session] = "zsh"
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        codex_home=str(
            codex_home_with(tmp_path=tmp_path, topic=topic, session_id=STALE_CODEX_SESSION)
        ),
    )
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)
    monkeypatch.setattr(supervisor, "Supervisor", lambda *, tmux: sup)
    monkeypatch.chdir(tmp_path)
    sessions_before = set(fake.sessions)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    err = capsys.readouterr().err
    assert "start REFUSED" in err
    assert "reason=ambiguous_runtime" in err
    assert "no durable session identity is recorded" in err
    assert f"the Codex index names session {STALE_CODEX_SESSION}" in err
    assert not fake.has(method="new")
    assert not fake.has(method="respawn")
    assert fake.sessions == sessions_before
    assert registry.read_valid_mapping(store_path=store) == [track]
