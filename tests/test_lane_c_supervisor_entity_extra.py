"""Additional Lane C coverage for reservation and supervisor-entity branches."""

import contextlib
import io as _io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_prompts
import registry
import signals
import supervisor
from test_supervisor_builders import (
    TEST_EPIC,
    arm_ready_marker,
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_reserved_supervisor_topics_are_refused_by_discovery_and_collision(*, tmp_path):
    repo = tmp_path / "repo"
    good = repo / "plan" / "good"
    bad = repo / "plan" / "bad-supervisor"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)

    discovered = registry.discover_plans(watch_repos=[str(repo)])
    colliding = registry.colliding_topics(
        discovered=[(str(repo), "bad-supervisor"), (str(tmp_path / "other"), "good")]
    )
    assert discovered == [(str(repo), "good")]
    assert colliding == frozenset()
    with pytest.raises(ValueError, match="bad-supervisor"):
        registry.tmux_id(repo=str(repo), topic="bad-supervisor")


def test_supervisor_wrapup_text_targets_supervisor_ledger_state(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)

    text = _supervisor_prompts.supervisor_wrapup_message(
        remaining=45, repo=str(repo), topic=topic, epic=TEST_EPIC
    )

    assert f"tmp/overseer/{topic}-supervisor/.overseer-state" in text
    assert TEST_EPIC in text
    assert str(repo) in text
    assert "supervisor handoff entries attributed to that entity" in text
    assert "sanctioned plan" in text
    assert "supervisor-handoff.md" not in text
    assert "worktree add" not in text
    assert "cp " not in text


def test_foreman_low_context_uses_foreman_wrapup_with_shared_cardinal_body(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    foreman_topic = f"{topic}-foreman"
    session = foreman_topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=45))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=foreman_topic, session=session)

    assert "foreman_wrapup_message" in _supervisor_prompts.__all__
    expected_body = _supervisor_prompts._WRAPUP_BODY.format(
        marker_dir=str(signals.marker_dir(repo=str(repo), topic=foreman_topic)),
        state_file=str(signals.state_path(repo=str(repo), topic=foreman_topic)),
        read_first=(
            f"the foreman handoff timeline on ledger epic {TEST_EPIC} " f"in repository {repo}"
        ),
        resume=(
            f"resume foreman ledger epic {TEST_EPIC} in repository {repo}; "
            "read its ledger-held foreman handoff timeline"
        ),
    )

    view = sup.evaluate(track=track, act=True)

    pasted = "\n".join(fake.paste_texts())
    assert view.status == "warned"
    assert "foreman handoff timeline" in pasted
    assert "plan epic" not in pasted
    assert pasted.split("\n\n", 1)[1] == expected_body


def test_dead_supervisor_with_open_round_gets_attention_row(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=topic),
        store_path=sup.store_path,
        added_at="now",
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=f"{topic}-supervisor", ts=900.0, stamp_path=sup.stamp_path
    )

    views = sup.tick(act=True)

    row = {view.topic: view for view in views}[f"{topic}-supervisor"]
    assert row.status == "session-gone"
    assert row.note == "supervisor vanished during an open wind-down round"


def test_supervisor_low_context_uses_supervisor_wrapup_variant(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(ctx=80))
    fake.serve(session=f"{topic}-supervisor", repo=repo, capture=idle_capture(ctx=45))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(
        sessions_dir=sessions_dir,
        pid=100,
        name=f"{topic}-supervisor",
        cwd=str(repo),
        status="idle",
    )
    fake.pane_pids[50] = f"{topic}-supervisor"
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        sessions_dir=str(sessions_dir),
        ppid_of=lambda *, pid: 50 if pid == 100 else None,
        starttime_of=lambda *, pid: "pt" if pid == 100 else None,
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=topic),
        store_path=sup.store_path,
        added_at="now",
    )
    write_fresh_supervisor_state(repo=repo, topic=f"{topic}-supervisor")

    sup.tick(act=True)

    pasted = "\n".join(fake.paste_texts())
    assert TEST_EPIC in pasted
    assert f"tmp/overseer/{topic}-supervisor/.overseer-state" in pasted
    assert "supervisor handoff entries attributed to that entity" in pasted
    assert "supervisor-handoff.md" not in pasted
    assert "worktree add" not in pasted


def test_supervisor_ready_without_handoff_preserves_declaration(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(ctx=80))
    fake.serve(session=f"{topic}-supervisor", repo=repo, capture=idle_capture(ctx=80))
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

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        sup.tick(act=True)

    assert [call for call in fake.calls if call[0] == "respawn"] == []
    assert signals.read_state(repo=str(repo), topic=f"{topic}-supervisor").token == "ready"
    assert "supervisor-handoff.md is missing" in err.getvalue()


def test_supervisor_topic_helpers_cover_identity_edges(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    state = signals.state_path(repo=str(repo), topic="topic")
    state.parent.mkdir(parents=True)
    state.write_text("ready\n")

    class BrokenPath:
        def __init__(self, *, value: str):
            self.value = value

        def resolve(self):
            raise OSError("no resolve")

    def fake_state_path(*, repo: str, topic: str):
        return state

    def fake_path(*args):
        return BrokenPath(value=str(args[0]))

    monkeypatch.setattr(signals, "state_path", fake_state_path)
    monkeypatch.setattr(signals, "Path", fake_path)

    parsed = signals.read_state(repo=str(repo), topic="topic")

    assert signals.supervisor_topic(entity_topic="plain") == "plain"
    assert parsed is not None
    assert parsed.token == "state-path-mismatch"


def test_cli_refuses_reserved_supervisor_topic_for_track_commands(*, tmp_path, monkeypatch):
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = str(tmp_path / "repo")

    for command in ("add", "remove", "start"):
        with contextlib.redirect_stderr(_io.StringIO()) as err:
            rc = supervisor.main(argv=[command, "--repo", repo, "--topic", "topic-supervisor"])
        assert rc == 1
        assert "refusing reserved supervisor topic" in err.getvalue()
    assert not store.exists()


def test_read_only_dead_supervisor_open_round_renders_without_alert(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=topic),
        store_path=sup.store_path,
        added_at="now",
    )
    registry.write_injection_stamp(
        repo=str(repo), topic=f"{topic}-supervisor", ts=900.0, stamp_path=sup.stamp_path
    )

    views = sup.tick(act=False)

    assert {view.topic: view.status for view in views}[f"{topic}-supervisor"] == "session-gone"
    assert not fake.has(method="rename_window")


def test_supervisor_entity_idle_does_not_offer_supervisor_of_supervisor(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    entity_topic = f"{topic}-supervisor"
    fake = FakeTmux()
    fake.serve(session=entity_topic, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = registry.Track(
        topic=entity_topic,
        repo=str(repo),
        tmux=entity_topic,
        epic="overseer-test-epic",
        resume=_supervisor_prompts.supervisor_resume(repo=str(repo), topic=topic),
    )
    write_fresh_supervisor_state(repo=repo, topic=entity_topic)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)

    assert view.status == "idle-with-context-left"
    assert f"{entity_topic}-supervisor" not in err.getvalue()


def test_supervisor_entity_idle_nudge_points_at_dual_plan_shape(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    entity_topic = f"{topic}-supervisor"
    fake = FakeTmux()
    fake.serve(session=entity_topic, repo=repo, capture=idle_capture(ctx=80))
    clock = {"t": 5000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = registry.Track(
        topic=entity_topic,
        repo=str(repo),
        tmux=entity_topic,
        epic="overseer-test-epic",
        resume=_supervisor_prompts.supervisor_resume(
            repo=str(repo), topic=topic, epic="overseer-test-epic"
        ),
    )
    write_fresh_supervisor_state(repo=repo, topic=entity_topic)

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    clock["t"] += 3601.0
    view = sup.evaluate(track=track, act=True)

    assert view.status == "idle-with-context-left"
    pasted = "\n".join(fake.paste_texts())
    assert ".ai/supervisor-protocol.md" in pasted
    assert "supervisor handoff entries" in pasted
    assert "overseer-test-epic" in pasted
    assert f"tmp/overseer/{entity_topic}/.overseer-state" in pasted
    assert "handoff.md" not in pasted
    assert f"plan/{entity_topic}/handoff.md" not in pasted
