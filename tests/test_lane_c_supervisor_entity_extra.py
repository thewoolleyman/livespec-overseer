"""Additional Lane C coverage for reservation and supervisor-entity branches."""

import contextlib
import io as _io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_prompts
import registry
import signals
import supervisor
from test_supervisor_builders import (
    arm_ready_marker,
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
    mapped_track,
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
        discovered=[(str(repo), "bad-supervisor", "x"), (str(tmp_path / "other"), "good", "x")]
    )
    derived = registry.tmux_id(repo=str(repo), topic="bad-supervisor")

    assert discovered == [(str(repo), "good", str(good / "handoff.md"))]
    assert colliding == frozenset()
    assert derived == "bad-supervisor"


def test_supervisor_wrapup_text_targets_supervisor_handoff(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)

    text = _supervisor_prompts.supervisor_wrapup_message(remaining=45, repo=str(repo), topic=topic)

    assert f"tmp/overseer/{topic}-supervisor/.overseer-state" in text
    assert f"plan/{topic}/supervisor-handoff.md" in text
    assert f"wrapup-{topic}-supervisor" in text
    assert f"$W/plan/{topic}/supervisor-handoff.md" in text


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
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    fake = FakeTmux()
    fake.serve(session=topic, repo=repo, capture=idle_capture(ctx=80))
    fake.serve(session=f"{topic}-supervisor", repo=repo, capture=idle_capture(ctx=45))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=topic),
        store_path=sup.store_path,
        added_at="now",
    )

    sup.tick(act=True)

    assert any(f"plan/{topic}/supervisor-handoff.md" in text for text in fake.paste_texts())
    assert all(f"plan/{topic}-supervisor/handoff.md" not in text for text in fake.paste_texts())


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
        resume=_supervisor_prompts.supervisor_resume(repo=str(repo), topic=topic),
    )

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)

    assert view.status == "idle-with-context-left"
    assert f"{entity_topic}-supervisor" not in err.getvalue()


def test_supervisor_entity_idle_nudge_points_at_supervisor_handoff(*, tmp_path):
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
        resume=_supervisor_prompts.supervisor_resume(repo=str(repo), topic=topic),
    )

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    clock["t"] += 3601.0
    view = sup.evaluate(track=track, act=True)

    assert view.status == "idle-with-context-left"
    pasted = "\n".join(fake.paste_texts())
    assert f"plan/{topic}/supervisor-handoff.md" in pasted
    assert f"tmp/overseer/{entity_topic}/.overseer-state" in pasted
    assert f"plan/{entity_topic}/handoff.md" not in pasted
