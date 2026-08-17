"""Supervisor-state freshness appears on snapshot and attention surfaces."""

from __future__ import annotations

import datetime as dt

import _supervisor_config
import _supervisor_snapshot
import _supervisor_supervisor_state
import pytest
import signals
import supervisor
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _supervisor_state_path(*, repo, topic):
    path = (
        signals.marker_dir(repo=str(repo), topic=signals.supervisor_topic(entity_topic=topic))
        / ".supervisor-state"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_supervisor_state(*, repo, topic, updated_at: str):
    _supervisor_state_path(repo=repo, topic=topic).write_text(
        f"topic: {topic}\nupdated_at: {updated_at}\nopen_obligations: []\n",
        encoding="utf-8",
    )


def _iso_at(*, seconds: float) -> str:
    return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _supervisor_track(*, tmp_path, now: float = 1000.0):
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80, topic=topic))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: now)
    track = mapped_track(repo=repo, topic=topic, session=session)
    return repo, topic, sup, track


def test_supervisor_state_updated_at_freshness_sets_snapshot_flag(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0)
    repo, topic, sup, track = _supervisor_track(tmp_path=tmp_path)

    _write_supervisor_state(repo=repo, topic=topic, updated_at=_iso_at(seconds=970.0))
    fresh = sup.evaluate(track=track, act=False)
    _write_supervisor_state(repo=repo, topic=topic, updated_at=_iso_at(seconds=900.0))
    stale = sup.evaluate(track=track, act=False)
    payload = _supervisor_snapshot.row_payload(sup=sup, row=stale)

    assert fresh.supervisor_state_stale is False
    assert fresh.status != "supervisor-state-stale"
    assert stale.status == "supervisor-state-stale"
    assert stale.supervisor_state_stale is True
    assert payload["supervisor_state_stale"] is True


@pytest.mark.parametrize("body", [None, "updated_at: not-a-timestamp\n"])
def test_missing_or_malformed_supervisor_state_is_stale(*, tmp_path, monkeypatch, body):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0)
    repo, topic, sup, track = _supervisor_track(tmp_path=tmp_path)
    if body is not None:
        _supervisor_state_path(repo=repo, topic=topic).write_text(body, encoding="utf-8")

    row = sup.evaluate(track=track, act=False)

    assert row.status == "supervisor-state-stale"
    assert row.supervisor_state_stale is True


def test_supervisor_state_stale_surfaces_distinct_from_plain_blocked_human(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0)
    repo, topic, sup, track = _supervisor_track(tmp_path=tmp_path)
    declare(repo=repo, topic=topic, value="blocked: waiting on maintainer")

    blocked = sup.evaluate(track=track, act=False)
    needs = render_of(sup=sup, views=[blocked]).split("NEEDS YOU")[1]

    assert blocked.status == "supervisor-state-stale"
    assert supervisor.needs_attention(row=blocked) is True
    assert "supervisor state stale" in (blocked.note or "")
    assert "supervisor-state-stale" in needs
    assert "blocked:human" not in needs


@pytest.mark.parametrize("body", ["# comment only\n\n", "not yaml\n", "updated_at: [\n"])
def test_supervisor_state_missing_or_unparseable_updated_at_is_stale(
    *, tmp_path, monkeypatch, body
):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0)
    repo, topic, sup, track = _supervisor_track(tmp_path=tmp_path)
    _supervisor_state_path(repo=repo, topic=topic).write_text(body, encoding="utf-8")

    freshness = _supervisor_supervisor_state.observe_supervisor_state_freshness(
        sup=sup, track=track
    )

    assert freshness.stale is True
    assert freshness.age is None
    assert freshness.reason == "missing or malformed marker"


def test_supervisor_state_ignores_yaml_scalar_text_while_reading_updated_at(
    *, tmp_path, monkeypatch
):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0)
    repo, topic, sup, track = _supervisor_track(tmp_path=tmp_path)
    _supervisor_state_path(repo=repo, topic=topic).write_text(
        "objective: keep the plan's tracks moving\n"
        "waiting_on: maintainer [review]\n"
        "updated_at: 1970-01-01T00:16:20Z\n",
        encoding="utf-8",
    )

    freshness = _supervisor_supervisor_state.observe_supervisor_state_freshness(
        sup=sup, track=track
    )

    assert freshness.stale is False
    assert freshness.age == 20.0


def test_supervisor_state_stale_alert_surfaces_when_acting(*, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(_supervisor_config, "SUPERVISOR_STATE_STALE_AFTER", 60.0)
    repo, topic, sup, track = _supervisor_track(tmp_path=tmp_path)

    row = sup.evaluate(track=track, act=True)
    err = capsys.readouterr().err

    assert row.status == "supervisor-state-stale"
    assert "supervisor state stale" in err
    assert "inspect and refresh tmp/overseer/<topic>/.supervisor-state" in err
    assert (str(repo), topic, "supervisor-state-stale") in sup.alerted


def test_supervisor_state_stale_note_defaults_unknown_reason():
    note = _supervisor_supervisor_state.supervisor_state_stale_note(
        freshness=_supervisor_supervisor_state.SupervisorStateFreshness(
            stale=True, age=None, reason=None
        )
    )

    assert note == "supervisor state stale: unknown freshness"
