"""RGR Red tests for Lane C supervisor entities."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import registry
import signals
from test_supervisor_builders import (
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_supervisor_ready_restarts_supervisor_entity_not_worker(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    worker_session = topic
    supervisor_session = f"{topic}-supervisor"
    fake = FakeTmux()
    fake.serve(session=worker_session, repo=repo, capture=idle_capture(ctx=80))
    fake.serve(session=supervisor_session, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=worker_session),
        store_path=sup.store_path,
        added_at="now",
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=f"{topic}-supervisor", ts=900.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic)
    arm_ready_marker(repo=repo, topic=f"{topic}-supervisor")

    sup.tick(act=True)

    respawns = [call for call in fake.calls if call[0] == "respawn"]
    assert len(respawns) == 1
    assert respawns[0][1] == supervisor_session
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert signals.read_state(repo=str(repo), topic=f"{topic}-supervisor") is None


def test_symlinked_state_file_is_refused(*, tmp_path):
    repo = tmp_path / "repo"
    topic = "topic"
    outside = tmp_path / "outside-state"
    outside.write_text("ready\n")
    state = signals.state_path(repo=str(repo), topic=topic)
    state.parent.mkdir(parents=True)
    state.symlink_to(outside)

    parsed = signals.read_state(repo=str(repo), topic=topic)

    assert parsed is not None
    assert parsed.token == "state-path-mismatch"
    assert signals.ready_valid(repo=str(repo), topic=topic, injection_stamp=0.0) is False
