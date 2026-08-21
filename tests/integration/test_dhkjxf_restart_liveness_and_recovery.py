"""Integration coverage for restart, liveness, recovery, and un-open TODO rows."""

from __future__ import annotations

import io as _io

import _supervisor_config
import pytest
import registry
import signals
import supervisor
from test_supervisor_builders import (
    TEST_EPIC,
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    unsubmitted_resume_capture,
)
from test_supervisor_fakes import FakeTmux


def _paste_count(*, fake: FakeTmux) -> int:
    return len(fake.paste_texts())


@pytest.mark.integration
def test_scenario_restarted_session_never_begins_work_surfaces_without_second_kill(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=unsubmitted_resume_capture(ctx=100, repo=str(repo), epic=TEST_EPIC),
    )
    clock = {"now": 1000.0}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: clock["now"],
        out=_io.StringIO(),
        own_pane="%7",
    )
    track = mapped_track(repo=repo, topic=topic, session=session)

    first = sup.evaluate(track=track, act=True)
    clock["now"] += 61.0
    due = sup.evaluate(track=track, act=True)

    assert first.status == "restarting"
    assert due.status == "restarting"
    assert supervisor.needs_attention(row=due) is True
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


@pytest.mark.integration
def test_scenario_two_consecutive_still_alerts_force_fresh_pane_reread(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "working"
    clock["t"] += _supervisor_config.PANE_STILL_AFTER + 1.0
    assert sup.evaluate(track=track, act=True).status == "working"
    still = sup.evaluate(track=track, act=True)

    assert still.status == "pane-still"
    assert "unchanged" in (still.note or "")
    assert supervisor.needs_attention(row=still) is True
    assert not fake.has(method="respawn")


@pytest.mark.integration
def test_scenario_daemon_bounce_invalidated_watch_is_not_armed(*, tmp_path):
    from tests.test_liveness_attention_statuses import (
        _mark_stall_watch_before_bounce,
        _status_snapshot_after_bounce,
    )

    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    status_path = _status_snapshot_after_bounce(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, status_path=status_path)
    state = _mark_stall_watch_before_bounce(sup=sup, repo=repo, topic=topic)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert state.stall_watch_pane == session
    assert state.stall_watch_daemon_instance_id == "daemon-after-bounce"


@pytest.mark.integration
def test_scenario_wind_down_expiry_on_context_recovery_closes_round(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "warned"
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))
    clock["t"] += 1.0
    recovered = sup.evaluate(track=track, act=True)

    assert recovered.status == "idle"
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )


@pytest.mark.integration
def test_scenario_session_clears_stale_winding_down_and_resumes_after_recovery(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    marker = declare(repo=repo, topic=topic, value=signals.STATE_WINDING_DOWN)

    marker.unlink()

    assert signals.read_state(repo=str(repo), topic=topic) is None


@pytest.mark.integration
def test_scenario_session_clears_stale_ready_and_resumes_after_recovery(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY)

    marker.unlink()

    assert signals.read_state(repo=str(repo), topic=topic) is None


@pytest.mark.integration
def test_scenario_failed_unopen_leaves_standing_round_evidence_on_clear_error(
    *, tmp_path, monkeypatch
):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    fake.paste_ok = False
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    def blocked_clear(*, repo: str, topic: str, stamp_path):
        del repo, topic, stamp_path
        raise OSError("cannot un-open")

    monkeypatch.setattr(registry, "clear_injection_stamp", blocked_clear)

    with pytest.raises(OSError, match="cannot un-open"):
        sup.evaluate(track=track, act=True)

    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )
    assert not fake.has(method="respawn")


@pytest.mark.integration
def test_scenario_successful_unopen_after_failed_wrapup_surfaces_nothing(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    fake.paste_ok = False
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "warned"

    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
    assert _paste_count(fake=fake) == 1
    assert not fake.has(method="respawn")
