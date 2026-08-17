"""RGR Red tests for Lane C supervisor entities."""

import contextlib
import io as _io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_offer
import registry
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
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
    write_fresh_supervisor_state(repo=repo, topic=f"{topic}-supervisor")
    arm_ready_marker(repo=repo, topic=topic)
    arm_ready_marker(repo=repo, topic=f"{topic}-supervisor")

    sup.tick(act=True)

    respawns = [call for call in fake.calls if call[0] == "respawn"]
    assert len(respawns) == 1
    assert respawns[0][1] == supervisor_session
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert (
        signals.read_state(repo=str(repo), topic=f"{topic}-supervisor").token
        == signals.STATE_RESTARTED
    )


def test_migrated_supervisor_ready_restarts_from_ledger_epic_shape(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "epic.md").write_text(
        "# Plan Epic\n\n"
        "Ledger epic: `overseer-test-epic`\n\n"
        "The supervisor binder is read from attributed ledger comments.\n"
    )
    supervisor_session = f"{topic}-supervisor"
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(ctx=80))
    fake.serve(session=supervisor_session, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=topic),
        store_path=sup.store_path,
        added_at="now",
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=f"{topic}-supervisor", ts=900.0, stamp_path=sup.stamp_path
    )
    write_fresh_supervisor_state(repo=repo, topic=f"{topic}-supervisor")
    arm_ready_marker(repo=repo, topic=f"{topic}-supervisor")

    sup.tick(act=True)

    respawns = [call for call in fake.calls if call[0] == "respawn"]
    assert len(respawns) == 1
    assert respawns[0][1] == supervisor_session
    resume = fake.paste_texts()[0]
    assert str(repo) in resume
    assert "overseer-test-epic" in resume
    assert f"{topic}-supervisor" in resume
    assert "supervisor-handoff.md" not in resume
    assert (
        signals.read_state(repo=str(repo), topic=f"{topic}-supervisor").token
        == signals.STATE_RESTARTED
    )


def test_migrated_supervisor_ready_without_recorded_epic_still_refuses(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "epic.md").write_text(
        "# Plan Epic\n\n"
        "Ledger epic: `overseer-test-epic`\n\n"
        "The supervisor binder is read from attributed ledger comments.\n"
    )
    supervisor_session = f"{topic}-supervisor"
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(ctx=80))
    fake.serve(session=supervisor_session, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=registry.Track(topic=topic, repo=str(repo), tmux=topic, epic=None),
        store_path=sup.store_path,
        added_at="now",
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=f"{topic}-supervisor", ts=900.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=f"{topic}-supervisor")

    sup.tick(act=True)

    assert [call for call in fake.calls if call[0] == "respawn"] == []
    assert signals.read_state(repo=str(repo), topic=f"{topic}-supervisor").token == "ready"


def test_migrated_epic_and_running_supervisor_is_silent_healthy_cell(*, tmp_path, monkeypatch):
    """The migrated ledger-backed binder is a durable supervisor prompt too."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "epic.md").write_text(
        f"Supervisor binder for ledger epic {TEST_EPIC}; read comment entries.\n",
        encoding="utf-8",
    )
    session = registry.tmux_id(repo=str(repo), topic=topic)
    supervisor_session = f"{session}-supervisor"
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    fake.serve(session=supervisor_session, repo=repo, capture=idle_capture(ctx=73), cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        _supervisor_offer.surface_supervision_offer(sup=sup, track=track, act=True)
        _supervisor_offer.surface_supervision_offer(sup=sup, track=track, act=False)
    assert sup.alerted == {}
    assert "supervisor" not in err.getvalue()


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
    assert (
        signals.ready_valid(
            repo=str(repo),
            topic=topic,
            certification_floor=0.0,
            round_session_identity="claude:s:t",
            live_session_identity="claude:s:t",
        )
        is False
    )
