"""Edge coverage for supervisor-state freshness parsing."""

from __future__ import annotations

import importlib
from pathlib import Path

import _supervisor_config
import pytest
import registry
import signals
from test_supervisor_builders import make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _write_marker(*, repo, topic: str, body: str) -> None:
    supervisor_state = _import_supervisor_state_module()
    path = supervisor_state.supervisor_state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _import_supervisor_state_module():
    module_path = Path(__file__).parents[1] / "overseer" / "_supervisor_supervisor_state.py"
    assert module_path.is_file()
    return importlib.import_module("_supervisor_supervisor_state")


def _freshness(*, tmp_path, topic_suffix: str, body: str | None = None):
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    topic = f"{worker_topic}{topic_suffix}"
    if body is not None:
        _write_marker(repo=repo, topic=signals.supervisor_topic(entity_topic=topic), body=body)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 1000.0)
    track = mapped_track(repo=repo, topic=topic, session=topic)
    supervisor_state = _import_supervisor_state_module()
    return supervisor_state.observe_supervisor_state_freshness(sup=sup, track=track)


def _freshness_for_track(*, tmp_path, track):
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 1000.0)
    supervisor_state = _import_supervisor_state_module()
    return supervisor_state.observe_supervisor_state_freshness(sup=sup, track=track)


def test_non_supervisor_topic_does_not_require_supervisor_state(*, tmp_path):
    freshness = _freshness(tmp_path=tmp_path, topic_suffix="")

    assert freshness.stale is False
    assert freshness.age is None


def test_smart_constructed_supervisor_seat_reads_supervised_topic_marker(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0, raising=False)
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(
        repo=repo,
        topic=signals.supervisor_entity_topic(topic=worker_topic),
        session="supervisor-pane",
    )
    assert isinstance(track, registry.SupervisorSeat)
    _write_marker(
        repo=repo,
        topic=track.supervised_topic,
        body="topic: topic\nupdated_at: 1970-01-01T00:16:20Z\n",
    )

    freshness = _freshness_for_track(tmp_path=tmp_path, track=track)

    assert freshness.stale is False
    assert freshness.age == 20.0


def test_smart_constructed_plan_track_does_not_require_supervisor_state(*, tmp_path):
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=worker_topic, session="worker-pane")
    assert isinstance(track, registry.PlanTrack)

    freshness = _freshness_for_track(tmp_path=tmp_path, track=track)

    assert freshness.stale is False
    assert freshness.age is None


def test_loaded_plan_track_with_supervisor_suffix_follows_variant_not_topic_suffix(*, tmp_path):
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    track = registry.PlanTrack(
        repo=str(repo),
        topic=signals.supervisor_entity_topic(topic=worker_topic),
        tmux="worker-pane",
        epic="overseer-test-epic",
    )

    freshness = _freshness_for_track(tmp_path=tmp_path, track=track)

    assert freshness.stale is False
    assert freshness.age is None


def test_loaded_supervisor_seat_without_supervisor_suffix_follows_variant(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0, raising=False)
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    track = registry.SupervisorSeat(
        repo=str(repo),
        topic=worker_topic,
        tmux="supervisor-pane",
        epic="overseer-test-epic",
        supervised_topic=worker_topic,
    )
    _write_marker(
        repo=repo,
        topic=track.supervised_topic,
        body="topic: topic\nupdated_at: 1970-01-01T00:16:20Z\n",
    )

    freshness = _freshness_for_track(tmp_path=tmp_path, track=track)

    assert freshness.stale is False
    assert freshness.age == 20.0


def test_naive_quoted_updated_at_is_treated_as_utc(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0, raising=False)
    freshness = _freshness(
        tmp_path=tmp_path,
        topic_suffix="-supervisor",
        body="note: ignored\nupdated_at: '1970-01-01T00:16:20'\n",
    )

    assert freshness.stale is False
    assert freshness.age == 20.0


def test_inline_comment_after_updated_at_is_ignored(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0, raising=False)
    freshness = _freshness(
        tmp_path=tmp_path,
        topic_suffix="-supervisor",
        body=(
            "topic: topic-supervisor\n"
            "updated_at: 1970-01-01T00:16:20Z  "
            "# FRESH MEASUREMENT, not a touched timestamp. Still a clean stop.\n"
        ),
    )

    assert freshness.stale is False
    assert freshness.age == 20.0
    assert freshness.reason is None


@pytest.mark.parametrize("body", ["updated_at:\n", "topic: topic-supervisor\n"])
def test_empty_or_absent_updated_at_fails_soft_to_stale(*, tmp_path, body):
    freshness = _freshness(tmp_path=tmp_path, topic_suffix="-supervisor", body=body)

    assert freshness.stale is True
    assert freshness.reason == "missing or malformed marker"


def test_unparseable_updated_at_fails_soft(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0, raising=False)
    freshness = _freshness(
        tmp_path=tmp_path,
        topic_suffix="-supervisor",
        body="topic: topic-supervisor\nupdated_at: [\n",
    )

    assert freshness.stale is True
    assert freshness.reason == "missing or malformed marker"
