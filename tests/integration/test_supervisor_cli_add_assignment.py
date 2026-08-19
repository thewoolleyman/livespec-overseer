"""Integration coverage for CLI-created track assignment rows."""

from __future__ import annotations

from overseer import registry, signals, supervisor
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
)
from overseer.test_supervisor_fakes import FakeTmux


def test_cli_add_accepts_epic_and_ctx_threshold_that_certify_ready_restart(
    *, tmp_path, monkeypatch
) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=45))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert (
        supervisor.main(
            argv=[
                "add",
                "--repo",
                str(repo),
                "--topic",
                topic,
                "--epic",
                "overseer-explicit",
                "--ctx-threshold",
                "65",
            ]
        )
        == 0
    )
    tracks = registry.read_valid_mapping(store_path=store)
    assert len(tracks) == 1
    track = tracks[0]
    assert track.epic == "overseer-explicit"
    assert track.ctx_threshold == 65

    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert fake.has(method="respawn")
    assert "overseer-explicit" in fake.paste_texts()[0]
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
