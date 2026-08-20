"""Regression coverage for daemon-supervised grooming entities."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
import registry
import signals
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "grooming_runtime.py"

__all__: list[str] = []


def grooming_runtime():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("grooming_runtime")


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_grooming_topic_contract_reserves_the_entity_suffix():
    assert signals.reserved_worker_suffix(topic="repo-grooming") == "-grooming"
    assert signals.is_grooming_topic(topic="repo-grooming") is True
    assert signals.topic_supervised_worker(topic="repo-grooming") is None
    with pytest.raises(ValueError, match="reserved -grooming topic has no supervised worker"):
        signals.supervisor_topic(entity_topic="repo-grooming")
    with pytest.raises(ValueError, match="repo-grooming"):
        registry.tmux_id(repo="/data/projects/repo", topic="repo-grooming")


def test_grooming_registration_self_adopts_and_preserves_fields(*, tmp_path):
    module = grooming_runtime()
    repo = tmp_path / "repo"
    repo.mkdir()
    grooming_topic = "repo-grooming"
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=registry.GroomingSeat(
            topic=grooming_topic,
            repo=str(repo),
            tmux="stale-grooming",
            epic="overseer-kept",
            ctx_threshold=41,
            observed_session_identity="claude:old",
        ),
        store_path=store,
    )
    registered = module.register_grooming_track(repo=repo, store_path=store)
    module.register_grooming_track(repo=repo, store_path=store)
    tracks = registry.read_valid_mapping(store_path=store)
    assert len(tracks) == 1
    assert registered.topic == grooming_topic
    assert tracks[0].kind == "grooming"
    assert tracks[0].tmux == grooming_topic
    assert tracks[0].epic == "overseer-kept"
    assert tracks[0].ctx_threshold == 41
    assert tracks[0].observed_session_identity == "claude:old"
    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "grooming"


def test_grooming_wrapup_is_not_worker_or_foreman_text(*, tmp_path):
    repo, worker_topic = make_plan(tmp_path=tmp_path, repo_name="repo", topic="plain")
    grooming_topic = "repo-grooming"
    foreman_topic = "repo-foreman"
    fake = FakeTmux()
    for session in (grooming_topic, foreman_topic, worker_topic):
        fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    grooming = registry.GroomingSeat(
        topic=grooming_topic,
        repo=str(repo),
        tmux=grooming_topic,
        epic=registry.unresolved_plan_epic(topic=grooming_topic),
    )
    foreman = registry.ForemanSeat(
        topic=foreman_topic,
        repo=str(repo),
        tmux=foreman_topic,
        epic=registry.unresolved_plan_epic(topic=foreman_topic),
    )
    worker = mapped_track(repo=repo, topic=worker_topic, session=worker_topic)

    sup.evaluate(track=grooming, act=True)
    sup.evaluate(track=foreman, act=True)
    sup.evaluate(track=worker, act=True)
    grooming_text, foreman_text, worker_text = fake.paste_texts()
    assert "complete the single ledger write" in grooming_text
    assert "record onto the relevant plan epic or item" in grooming_text
    assert "finish the drain" not in grooming_text.lower()
    assert "foreman handoff timeline" in foreman_text
    assert "Bring your OWN work" in worker_text


def test_grooming_restart_waits_for_ready_then_restarts_without_plan_epic(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    grooming_topic = "repo-grooming"
    ready_fake = FakeTmux()
    ready_fake.serve(session=grooming_topic, repo=repo, capture=idle_capture(ctx=13))
    ready_sup = make_supervisor(tmp_path=tmp_path, fake=ready_fake)
    grooming = registry.GroomingSeat(
        topic=grooming_topic,
        repo=str(repo),
        tmux=grooming_topic,
        epic=registry.unresolved_plan_epic(topic=grooming_topic),
    )
    assert ready_sup.evaluate(track=grooming, act=True).status == "danger"
    assert not ready_fake.has(method="respawn")
    registry.write_injection_stamp(
        repo=str(repo),
        topic=grooming_topic,
        ts=1000.0,
        session_identity=f"claude:{grooming_topic}:{grooming_topic}",
        stamp_path=ready_sup.stamp_path,
    )
    declare(repo=repo, topic=grooming_topic, value="ready", mtime=1001.0)

    view = ready_sup.evaluate(track=grooming, act=True)
    assert view.status == "restarting"
    assert ready_fake.has(method="respawn")
    assert "re-enter the grooming operation" in ready_fake.paste_texts()[-1]
